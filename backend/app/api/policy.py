from __future__ import annotations

import copy
from collections import Counter
from datetime import date

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from .. import models as m
from ..engine import pipeline
from ..models import Session
from ..policy import amend, diff as pdiff, normalise_policy, schema
from ..seed import load_master_from_db, load_policies_from_db
from ..services import batches as bsvc
from ..services.llm import llm
from .common import actor, err, require_role

bp = Blueprint("policy", __name__, url_prefix="/api/policies")


def _doc_of(pv: m.PolicyVersion) -> dict:
    d = dict(pv.document)
    d["version"], d["effective_from"] = pv.version, pv.effective_from.isoformat()
    return d


def _active_version(policies: list[m.PolicyVersion], today: date):
    ok = [p for p in policies if p.status == "approved" and p.effective_from <= today]
    return max(ok, key=lambda p: (p.effective_from, p.id)) if ok else None


def _render(doc: dict) -> list[dict]:
    return [{"id": r["id"], "title": r.get("title", ""), "text": pdiff.rule_text(r), "route": r["then"]["route"]}
            for r in doc["rules"]]


def _ser(pv: m.PolicyVersion, active_id=None, full=False):
    d = {"id": pv.id, "version": pv.version, "effective_from": pv.effective_from, "status": pv.status,
         "source_kind": pv.source_kind, "base_version": pv.base_version, "created_by": pv.created_by,
         "approved_by": pv.approved_by, "created_at": pv.created_at, "approved_at": pv.approved_at,
         "is_active": pv.id == active_id, "change_count": len(pv.changes or [])}
    if full:
        d.update({"document": _doc_of(pv), "rules_text": _render(pv.document), "changes": pv.changes or [],
                  "impact": pv.impact, "source_text": pv.source_text})
    return d


@bp.get("")
def list_versions():
    pvs = list(Session.scalars(select(m.PolicyVersion).order_by(m.PolicyVersion.effective_from.desc(),
                                                                m.PolicyVersion.id.desc())))
    act = _active_version(pvs, bsvc.now_ist().date())
    return jsonify([_ser(p, act.id if act else None) for p in pvs])


@bp.get("/active")
def active():
    pvs = list(Session.scalars(select(m.PolicyVersion)))
    act = _active_version(pvs, bsvc.now_ist().date())
    return jsonify(_ser(act, act.id, full=True))


@bp.get("/<int:pid>")
def get_version(pid):
    pv = Session.get(m.PolicyVersion, pid)
    if not pv:
        return err("policy version not found", 404)
    pvs = list(Session.scalars(select(m.PolicyVersion)))
    act = _active_version(pvs, bsvc.now_ist().date())
    return jsonify(_ser(pv, act.id if act else None, full=True))


def _impact(draft_doc: dict) -> dict | None:
    """Re-run the most recent uploaded batch under current policies vs current + draft."""
    b = Session.scalar(select(m.Batch).where(m.Batch.kind == "upload").order_by(m.Batch.id.desc()).limit(1))
    if not b:
        return None
    md = load_master_from_db(Session)
    current = load_policies_from_db(Session)
    draft = normalise_policy(draft_doc)
    current = [p for p in current if p["version"] != draft["version"]]
    run = lambda pols: pipeline.process([bsvc.hydrate(d) for d in b.lines if d.get("created_at") and d.get("need_by")],
                                        md, pols)["rows"]
    before, after = run(current), run(current + [draft])
    key = lambda r: (r["pr_no"], r["pr_line"])
    bmap = {key(r): r for r in before}
    moves, changed = Counter(), 0
    examples = []
    for a in after:
        o = bmap[key(a)]
        if (o["route"], o["supplier_id"], o["suggested_supplier_ids"]) != (a["route"], a["supplier_id"], a["suggested_supplier_ids"]):
            changed += 1
            moves[f"{o['route']} → {a['route']}"] += 1
            if len(examples) < 8:
                examples.append({"pr_no": a["pr_no"], "pr_line": a["pr_line"], "from": o["route"], "to": a["route"]})
    return {"batch_id": b.id, "batch_name": b.name, "lines": len(after), "lines_changed": changed,
            "moves": dict(moves), "examples": examples}


def _build_draft(doc: dict, who: str, kind: str, source_text: str | None, notes: str = "", keep: m.PolicyVersion | None = None):
    errors = schema.validate(doc)
    pvs = list(Session.scalars(select(m.PolicyVersion)))
    result = {"errors": errors, "notes": notes}
    if errors:
        return None, result
    eff = date.fromisoformat(doc["effective_from"])
    approved = [normalise_policy({**_doc_of(p)}) for p in pvs if p.status == "approved"]
    base = pipeline.select_policy(approved, eff)
    base_doc = next(_doc_of(p) for p in pvs if p.version == base["version"] and p.status == "approved")
    changes = pdiff.diff(base_doc, doc)
    same = [p for p in pvs if p.version == doc["version"] and (keep is None or p.id != keep.id)]
    if same:
        errors.append(f"Version {doc['version']} already exists. Use a new version number.")
        return None, result
    try:
        impact = _impact(doc)
    except Exception as e:  # noqa: BLE001
        impact = {"error": f"impact preview failed: {e}"}
    if keep is None:
        keep = m.PolicyVersion(version=doc["version"], status="draft", created_by=who)
        Session.add(keep)
    keep.version, keep.effective_from, keep.document = doc["version"], eff, doc
    keep.source_kind, keep.source_text, keep.changes, keep.impact, keep.base_version = kind, source_text, changes, impact, base["version"]
    Session.flush()
    return keep, result


@bp.post("/drafts")
def create_draft():
    """Multipart 'file' (PDF/DOCX/TXT), or JSON {text} (describe a change in chat), or JSON {document} (manual)."""
    denied = require_role("Procurement")
    if denied:
        return denied
    who, role = actor()
    pvs = list(Session.scalars(select(m.PolicyVersion)))
    act = _active_version(pvs, bsvc.now_ist().date()) or pvs[0]
    body = request.get_json(silent=True) or {}
    f = request.files.get("file")
    default_eff = (request.form.get("effective_from") or body.get("effective_from") or bsvc.now_ist().date().isoformat())
    notes, text, kind = "", None, "manual"
    if "document" in body:
        doc = body["document"]
        kind = "manual"
    else:
        pdf = None
        if f:
            text, pdf = amend.extract_text(f.filename, f.read())
            kind = "upload"
        else:
            text, kind = (body.get("text") or request.form.get("text") or "").strip(), "chat"
        if not text and not pdf:
            return err("Upload an amendment document or describe the change.")
        try:
            out = amend.propose(_doc_of(act), text, default_eff, llm, pdf)
        except Exception as e:  # noqa: BLE001
            return err(f"The AI policy reader could not process this: {e}. You can enter the change in the manual editor.", 502)
        doc, notes = out["policy"], out["notes"]
        if not isinstance(doc, dict):
            return err("The AI reader did not return a policy document.", 502)
    if isinstance(doc.get("effective_from"), date):
        doc["effective_from"] = doc["effective_from"].isoformat()
    pv, result = _build_draft(doc, who, kind, text, notes)
    if pv is None:
        Session.rollback()
        return jsonify({"error": "The proposed policy is not valid.", **result}), 422
    bsvc.audit(Session, who, role, "policy_draft_created", f"v{pv.version}", detail={"source": kind})
    Session.commit()
    return jsonify({**_ser(pv, full=True), "warnings": result["notes"]})


@bp.patch("/drafts/<int:pid>")
def edit_draft(pid):
    denied = require_role("Procurement")
    if denied:
        return denied
    pv = Session.get(m.PolicyVersion, pid)
    if not pv or pv.status != "draft":
        return err("draft not found", 404)
    doc = (request.get_json(force=True) or {}).get("document")
    if not isinstance(doc, dict):
        return err("send {document: <policy json>}")
    who, role = actor()
    new, result = _build_draft(doc, who, pv.source_kind, pv.source_text, keep=pv)
    if new is None:
        Session.rollback()
        return jsonify({"error": "The edited policy is not valid.", **result}), 422
    bsvc.audit(Session, who, role, "policy_draft_edited", f"v{pv.version}")
    Session.commit()
    return jsonify(_ser(pv, full=True))


@bp.post("/drafts/<int:pid>/approve")
def approve_draft(pid):
    denied = require_role("Procurement")
    if denied:
        return denied
    pv = Session.get(m.PolicyVersion, pid)
    if not pv or pv.status != "draft":
        return err("draft not found or already decided", 404)
    errors = schema.validate({**pv.document, "version": pv.version, "effective_from": pv.effective_from.isoformat()})
    if errors:
        return jsonify({"error": "Draft is not valid", "errors": errors}), 422
    who, role = actor()
    pv.status, pv.approved_by, pv.approved_at = "approved", who, bsvc.now_ist()
    bsvc.audit(Session, who, role, "policy_approved", f"v{pv.version}",
               detail={"effective_from": pv.effective_from.isoformat(), "changes": len(pv.changes or [])})
    Session.commit()
    return jsonify(_ser(pv, full=True))


@bp.post("/drafts/<int:pid>/reject")
def reject_draft(pid):
    denied = require_role("Procurement")
    if denied:
        return denied
    pv = Session.get(m.PolicyVersion, pid)
    if not pv or pv.status != "draft":
        return err("draft not found", 404)
    who, role = actor()
    pv.status = "rejected"
    bsvc.audit(Session, who, role, "policy_rejected", f"v{pv.version}")
    Session.commit()
    return jsonify(_ser(pv))


@bp.get("/catalogue")
def catalogue():
    """What a rule can refer to: lets the manual editor offer valid facts, operators and routes."""
    from ..engine.rules import FACT_CATALOGUE, OPS
    return jsonify({"facts": FACT_CATALOGUE, "operators": list(OPS) + ["exists"], "routes": schema.ROUTES,
                    "suppliers": ["contract", "preferred_1", "none"]})
