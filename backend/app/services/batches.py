"""Run the pure engine against DB state, serialise results, and handle approve / override."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select

from .. import models as m
from ..engine import loader, pipeline
from ..seed import load_master_from_db, load_policies_from_db

IST = timezone(timedelta(hours=5, minutes=30))


def now_ist() -> datetime:
    return datetime.now(IST).replace(tzinfo=None, microsecond=0)


def dehydrate(ln: dict) -> dict:
    keys = ["pr_no", "pr_line", "plant", "item_code", "description", "uom", "department", "requester", "urgency",
            "quantity", "estimated_unit_price", "errors", "row", "force_new"]
    d = {k: ln.get(k) for k in keys}
    d["created_at"] = ln["created_at"].isoformat(sep=" ") if ln.get("created_at") else None
    d["need_by"] = ln["need_by"].isoformat() if ln.get("need_by") else None
    return d


def hydrate(d: dict) -> dict:
    ln = dict(d)
    ln["created_at"] = datetime.fromisoformat(d["created_at"]) if d.get("created_at") else None
    ln["need_by"] = date.fromisoformat(d["need_by"]) if d.get("need_by") else None
    ln["errors"] = list(d.get("errors") or [])
    return ln


def req_key(r: dict) -> str:
    return "|".join(sorted(f"{l['pr_no']}/{l['pr_line']}" for l in r["lines"]))


def _ser_req(r: dict, md) -> dict:
    sup = lambda sid: md.suppliers.get(sid, {}).get("name", "")
    return {
        "key": req_key(r), "group_id": r["group_id"], "item_code": r["item_code"] or "NEW",
        "item_description": r.get("item_description"), "category": (r["item"] or {}).get("category"),
        "item_type": (r["item"] or {}).get("item_type"), "uom": (r["item"] or {}).get("uom"),
        "plant": r["plant"], "date": r["date"].isoformat(), "created_at": r["created_at"].isoformat(sep=" "),
        "is_emergency": r["is_emergency"], "quantity": r["quantity"],
        "lines": [{"pr_no": l["pr_no"], "pr_line": l["pr_line"], "created_at": l["created_at"].isoformat(sep=" "),
                   "quantity": l["quantity"], "need_by": l["need_by"].isoformat(), "urgency": l["urgency"],
                   "description": l["description"], "requester": l.get("requester"), "department": l.get("department"),
                   "item_code_given": l["item_code"] or None, "match_method": l["match_method"],
                   "match_score": l["match_score"]} for l in r["lines"]],
        "decision": r["decision"], "route": r["route"], "supplier_id": r["supplier_id"],
        "supplier_name": sup(r["supplier_id"]) if r["supplier_id"] else None,
        "unit_price": r["unit_price"], "price_source": r["price_source"], "value": round(r["value"], 2),
        "suggested": [{**s, "name": sup(s["supplier_id"]), "status": md.suppliers[s["supplier_id"]]["status"]}
                      for s in r["suggested"]],
        "po_id": r.get("po_id"), "rule_id": r.get("rule_id"), "rule_title": r.get("rule_title"),
        "policy_version": r["policy_version"], "reason": r["reason"], "relied_on": r.get("relied_on"),
        "flags": list(dict.fromkeys(r["flags"])), "contract_report": r["contract_report"],
        "skipped_rules": r.get("skipped_rules", []),
        "facts": {k: v for k, v in r["facts"].items()},
        "preferred": [{k: (v.isoformat() if isinstance(v, date) else v) for k, v in p.items()} for p in r["preferred"][:5]],
    }


def run_batch(session, batch: m.Batch, override: str | None = None) -> dict:
    md = load_master_from_db(session)
    policies = load_policies_from_db(session)
    lines = [hydrate(d) for d in batch.lines]
    bad_dates = [l for l in lines if not l.get("created_at") or not l.get("need_by")]
    good = [l for l in lines if l not in bad_dates]
    out = pipeline.process(good, md, policies, override or batch.policy_override)
    rows = {(r["pr_no"], r["pr_line"]): r for r in out["rows"]}
    ordered = []
    for l in lines:
        if l in bad_dates:
            ordered.append({"pr_no": l["pr_no"], "pr_line": l["pr_line"], "resolved_item_code": "", "group_id": "",
                            "po_id": "", "decision": "", "route": "NOT_PROCESSED", "supplier_id": "", "unit_price": "",
                            "group_value_inr": "", "suggested_supplier_ids": "", "policy_version": "",
                            "reason": "Not processed: " + "; ".join(l["errors"])})
        else:
            ordered.append(rows[(l["pr_no"], l["pr_line"])])
    reqs = [_ser_req(r, md) for r in out["requirements"]]
    summary = {"lines": len(ordered), "requirements": len(reqs), "pos": len(out["pos"]),
               "routes": {}, "policy_versions": sorted({r["policy_version"] for r in reqs})}
    for r in ordered:
        summary["routes"][r["route"]] = summary["routes"].get(r["route"], 0) + 1
    batch.result = {"rows": ordered, "requirements": reqs, "summary": summary}
    batch.processed_at = now_ist()
    return batch.result


def create_batch_from_csv(session, name: str, data: bytes, actor: str, override: str | None = None) -> m.Batch:
    lines, _ = loader.parse_pr_csv(data)
    b = m.Batch(name=name, kind="upload", created_by=actor, lines=[dehydrate(l) for l in lines],
                policy_override=override)
    session.add(b)
    session.flush()
    run_batch(session, b)
    return b


def csv_text(rows: list[dict]) -> str:
    import csv, io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=pipeline.OUTPUT_COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in pipeline.OUTPUT_COLUMNS})
    return buf.getvalue()


def audit(session, actor: str, role: str, action: str, entity: str | None = None, comment: str | None = None,
          detail: dict | None = None):
    session.add(m.AuditLog(at=now_ist(), actor=actor or "unknown", role=role or "", action=action, entity=entity,
                           comment=comment, detail=detail))
