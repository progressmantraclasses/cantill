from __future__ import annotations

import csv
import io
from datetime import date

from flask import Blueprint, Response, jsonify, request
from sqlalchemy import select

from .. import models as m
from ..engine import preferred as pref
from ..database import Session
from ..repository import load_master_from_db, policy_on
from ..services import batches as bsvc
from ..services import contract_extract as ce
from ..services.llm import llm
from .common import actor, err, json_body, require_role

BUYER_ROLES = ("Buyer", "Procurement")

bp = Blueprint("core", __name__, url_prefix="/api")

OVERRIDE_ROUTES = {"CONTRACT_PO": "PO", "EMERGENCY_PO": "PO", "SPOT_PO": "PO", "RFQ": "SOURCING_REQUEST",
                   "RFP": "SOURCING_REQUEST", "CAPEX_SOURCING": "SOURCING_REQUEST",
                   "NEW_ITEM_SOURCING": "SOURCING_REQUEST"}


@bp.get("/health")
def health():
    return {"ok": True, "llm": llm.available()}


# ---------- master data ----------
@bp.get("/items")
def items():
    return jsonify([{"item_code": i.item_code, "description": i.description, "uom": i.uom, "category": i.category,
                     "item_type": i.item_type, "standard_price": i.standard_price}
                    for i in Session.scalars(select(m.Item).order_by(m.Item.item_code))])


@bp.get("/suppliers")
def suppliers():
    return jsonify([{"supplier_id": s.supplier_id, "name": s.name, "city": s.city, "categories": s.categories,
                     "status": s.status, "on_time_pct": s.on_time_pct, "quality_rating": s.quality_rating}
                    for s in Session.scalars(select(m.Supplier).order_by(m.Supplier.supplier_id))])


@bp.get("/plants")
def plants():
    return jsonify([{"code": p.code, "name": p.name} for p in Session.scalars(select(m.Plant))])


# ---------- batches ----------
@bp.post("/process-batch")
def process_batch():
    """Takes a PR batch CSV (multipart field 'file', or the raw body) and returns the decisions."""
    f = request.files.get("file")
    data = f.read() if f else request.get_data()
    if not data.strip():
        return err("No CSV received. Send multipart field 'file' or the CSV as the request body.")
    name = (f.filename if f else None) or request.args.get("name") or "API batch"
    who, role = actor()
    try:
        b = bsvc.create_batch_from_csv(Session, name, data, who, request.args.get("policy_version"))
    except ValueError as e:
        Session.rollback()
        return err(str(e))
    bsvc.audit(Session, who, role, "process_batch", f"batch {b.id}", detail=b.result["summary"])
    Session.commit()
    if request.args.get("format") == "csv":
        return Response(bsvc.csv_text(b.result["rows"]), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=decisions_batch_{b.id}.csv"})
    return jsonify({"batch_id": b.id, "summary": b.result["summary"], "decisions": b.result["rows"]})


@bp.get("/batches")
def list_batches():
    out = []
    for b in Session.scalars(select(m.Batch).order_by(m.Batch.id.desc())):
        out.append({"id": b.id, "name": b.name, "kind": b.kind, "created_at": b.created_at, "created_by": b.created_by,
                    "processed_at": b.processed_at, "policy_override": b.policy_override,
                    "summary": (b.result or {}).get("summary")})
    return jsonify(out)


@bp.get("/batches/<int:bid>")
def get_batch(bid):
    b = Session.get(m.Batch, bid)
    if not b or not b.result:
        return err("batch not found", 404)
    return jsonify({"id": b.id, "name": b.name, "kind": b.kind, "processed_at": b.processed_at,
                    "summary": b.result["summary"], "decisions": b.result["rows"]})


@bp.post("/batches/<int:bid>/reprocess")
def reprocess(bid):
    b = Session.get(m.Batch, bid)
    if not b:
        return err("batch not found", 404)
    who, role = actor()
    body = request.get_json(silent=True) or {}
    if "policy_version" in body:          # "" means: back to choosing by effective date
        b.policy_override = body["policy_version"] or None
    elif request.args.get("policy_version"):
        b.policy_override = request.args["policy_version"]
    bsvc.run_batch(Session, b)
    bsvc.audit(Session, who, role, "reprocess_batch", f"batch {b.id}", detail=b.result["summary"])
    Session.commit()
    return jsonify({"batch_id": b.id, "summary": b.result["summary"], "decisions": b.result["rows"]})


@bp.get("/batches/<int:bid>/export.csv")
def export_batch(bid):
    b = Session.get(m.Batch, bid)
    if not b or not b.result:
        return err("batch not found", 404)
    return Response(bsvc.csv_text(b.result["rows"]), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=decisions_batch_{bid}.csv"})


# ---------- buyer workspace ----------
def _reviews(bid):
    return {r.req_key: r for r in Session.scalars(select(m.Review).where(m.Review.batch_id == bid))}


def _ser_review(r):
    return None if r is None else {"status": r.status, "comment": r.comment, "document_id": r.document_id,
                                   "actor": r.actor, "at": r.at, "override": r.override, "original": r.original}


@bp.get("/requirements")
def requirements():
    bid = request.args.get("batch_id", type=int)
    if bid is None:
        latest = Session.scalar(select(m.Batch).order_by(m.Batch.id.desc()).limit(1))
        if not latest:
            return jsonify({"batch_id": None, "requirements": []})
        bid = latest.id
    b = Session.get(m.Batch, bid)
    if not b or not b.result:
        return err("batch not found", 404)
    rv = _reviews(bid)
    out = []
    for r in b.result["requirements"]:
        row = dict(r)
        row["review"] = _ser_review(rv.get(r["key"]))
        row["status"] = row["review"]["status"] if row["review"] else "pending"
        out.append(row)
    return jsonify({"batch_id": bid, "batch_name": b.name, "summary": b.result["summary"], "requirements": out})


def _find_req(bid, key):
    if not isinstance(bid, int) or not key:
        return None, None
    b = Session.get(m.Batch, bid)
    if not b or not b.result:
        return None, None
    return b, next((r for r in b.result["requirements"] if r["key"] == key), None)


@bp.post("/requirements/approve")
def approve():
    if denied := require_role(*BUYER_ROLES):
        return denied
    body = json_body()
    who, role = actor()
    b, r = _find_req(body.get("batch_id"), body.get("key"))
    if r is None:
        return err("requirement not found (the batch may have been reprocessed)", 404)
    if Session.scalar(select(m.Review).where(m.Review.batch_id == b.id, m.Review.req_key == r["key"])):
        return err("this requirement has already been actioned", 409)
    if r["decision"] == "PO" and r["supplier_id"]:
        sup = Session.get(m.Supplier, r["supplier_id"])
        if not sup or sup.status != "Active":
            return err("Policy 5.7: a Blocked or Inactive supplier can never receive a PO.", 422)
    doc = f"B{b.id}-{r['po_id']}" if r["decision"] == "PO" else f"{r['route']}-B{b.id}-{r['group_id']}"
    Session.add(m.Review(batch_id=b.id, req_key=r["key"], status="approved", comment=body.get("comment"),
                         original=_decision_view(r), document_id=doc, actor=who, at=bsvc.now_ist()))
    kind = "PO" if r["decision"] == "PO" else ("capex sourcing request" if r["route"] == "CAPEX_SOURCING" else r["route"])
    bsvc.audit(Session, who, role, "approve", f"{r['group_id']} (batch {b.id})", body.get("comment"),
               {"document": doc, "kind": kind, "policy_version": r["policy_version"], "rule": r["rule_id"]})
    Session.commit()
    return {"ok": True, "document_id": doc, "kind": kind}


def _decision_view(r):
    return {"decision": r["decision"], "route": r["route"], "supplier_id": r["supplier_id"],
            "unit_price": r["unit_price"], "value": r["value"], "policy_version": r["policy_version"],
            "rule_id": r["rule_id"], "reason": r["reason"], "suggested": [s["supplier_id"] for s in r["suggested"]]}


@bp.post("/requirements/override")
def override():
    if denied := require_role(*BUYER_ROLES):
        return denied
    body = json_body()
    who, role = actor()
    comment = (body.get("comment") or "").strip()
    if len(comment) < 5:
        return err("An override needs a written reason (policy 8.1).", 422)
    route = body.get("route")
    if route not in OVERRIDE_ROUTES:
        return err(f"route must be one of {', '.join(OVERRIDE_ROUTES)}", 422)
    b, r = _find_req(body.get("batch_id"), body.get("key"))
    if r is None:
        return err("requirement not found", 404)
    decision = OVERRIDE_ROUTES[route]
    supplier = body.get("supplier_id") or None
    if decision == "PO":
        sup = Session.get(m.Supplier, supplier) if supplier else None
        if not sup:
            return err("A PO override needs a supplier.", 422)
        if sup.status != "Active":
            return err(f"Policy 5.7: {sup.name} is {sup.status}; it can never receive a PO.", 422)
    existing = Session.scalar(select(m.Review).where(m.Review.batch_id == b.id, m.Review.req_key == r["key"]))
    if existing:
        return err("this requirement has already been actioned", 409)
    doc = f"B{b.id}-{r['po_id'] or r['group_id']}" if decision == "PO" else f"{route}-B{b.id}-{r['group_id']}"
    ov = {"decision": decision, "route": route, "supplier_id": supplier}
    Session.add(m.Review(batch_id=b.id, req_key=r["key"], status="overridden", comment=comment,
                         original=_decision_view(r), override=ov, document_id=doc, actor=who, at=bsvc.now_ist()))
    bsvc.audit(Session, who, role, "override", f"{r['group_id']} (batch {b.id})", comment,
               {"from": _decision_view(r), "to": ov})
    Session.commit()
    return {"ok": True, "document_id": doc}


# ---------- preferred suppliers ----------
@bp.get("/preferred-suppliers")
def preferred_suppliers():
    try:
        as_of = date.fromisoformat(request.args.get("as_of") or bsvc.now_ist().date().isoformat())
    except ValueError:
        return err("as_of must be YYYY-MM-DD")
    md = load_master_from_db(Session)
    pol = policy_on(Session, as_of, request.args.get("policy_version"))
    params = pol["params"]
    statuses = tuple(params.get("eligible_supplier_statuses", ["Active"]))
    item_filter = request.args.get("item_code")
    top = request.args.get("top", default=3, type=int)
    rows, detail = [], {}
    for code in sorted(md.items):
        if item_filter and code != item_filter:
            continue
        lst = pref.preferred_list(code, as_of, md, params.get("preferred", {}), statuses)
        detail[code] = [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in p.items()} for p in lst]
        for p in lst[:top]:
            rows.append({"item_code": code, "rank": p["rank"], "supplier_id": p["supplier_id"],
                         "reference_price": round(p["reference_price"], 2)})
    if request.args.get("format") == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=["item_code", "rank", "supplier_id", "reference_price"], lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename=preferred_suppliers_{as_of}.csv"})
    return jsonify({"as_of": as_of.isoformat(), "policy_version": pol["version"],
                    "weights": params.get("preferred", {}).get("weights"), "rows": rows, "detail": detail,
                    "items": {c: {"description": i["description"], "category": i["category"]} for c, i in md.items.items()}})


# ---------- contracts ----------
def _ser_contract(c: m.Contract):
    return {"contract_id": c.contract_id, "supplier_id": c.supplier_id, "start_date": c.start_date,
            "end_date": c.end_date, "value_cap": c.value_cap, "consumed_value": c.consumed_value,
            "source": c.source, "lines": c.lines, "added_by": c.added_by}


@bp.get("/contracts")
def contracts():
    sup = {s.supplier_id: s for s in Session.scalars(select(m.Supplier))}
    out = []
    for c in Session.scalars(select(m.Contract).order_by(m.Contract.contract_id)):
        d = _ser_contract(c)
        d["supplier_name"] = sup[c.supplier_id].name if c.supplier_id in sup else ""
        d["supplier_status"] = sup[c.supplier_id].status if c.supplier_id in sup else ""
        out.append(d)
    return jsonify(out)


@bp.post("/contracts/extract")
def contract_extract():
    f = request.files.get("file")
    if not f:
        return err("Upload the signed contract PDF as multipart field 'file'.")
    try:
        x = ce.extract(f.read(), llm)
    except Exception as e:  # noqa: BLE001
        return err(f"Could not read that PDF: {e}", 422)
    exists = Session.get(m.Contract, x.get("contract_id") or "")
    x["already_loaded"] = bool(exists)
    return jsonify(x)


@bp.post("/contracts")
def add_contract():
    if denied := require_role(*BUYER_ROLES):
        return denied
    body = json_body()
    who, role = actor()
    try:
        f = ce.to_contract_fields(body)
    except (KeyError, ValueError, TypeError) as e:
        return err(f"Contract is incomplete or invalid: {e}", 422)
    if not f["lines"]:
        return err("Add at least one item rate.", 422)
    if f["end_date"] < f["start_date"]:
        return err("End date is before start date.", 422)
    if f["value_cap"] <= 0:
        return err("The value ceiling must be greater than zero.", 422)
    if not 0 <= f["consumed_value"] <= f["value_cap"]:
        return err("Consumed value must be between zero and the value ceiling.", 422)
    if any(rate <= 0 for rate in f["lines"].values()):
        return err("Every item rate must be greater than zero.", 422)
    if Session.get(m.Contract, f["contract_id"]):
        return err(f"{f['contract_id']} is already loaded.", 409)
    if not Session.get(m.Supplier, f["supplier_id"]):
        return err(f"Unknown supplier {f['supplier_id']}.", 422)
    missing = [i for i in f["lines"] if not Session.get(m.Item, i)]
    if missing:
        return err(f"Unknown item code(s): {', '.join(missing)}", 422)
    Session.add(m.Contract(**f, source=body.get("source", "manual"), added_by=who))
    bsvc.audit(Session, who, role, "add_contract", f["contract_id"], detail={"source": body.get("source", "manual")})
    Session.commit()
    return {"ok": True, "contract_id": f["contract_id"]}


# ---------- audit ----------
@bp.get("/audit")
def audit_log():
    rows = Session.scalars(select(m.AuditLog).order_by(m.AuditLog.id.desc()).limit(500))
    return jsonify([{"id": a.id, "at": a.at, "actor": a.actor, "role": a.role, "action": a.action,
                     "entity": a.entity, "comment": a.comment, "detail": a.detail} for a in rows])
