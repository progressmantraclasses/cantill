"""Raising a single purchase request, from the chat assistant or the manual form.

Every raised PR is appended to one standing "requests" batch and decided by the same engine as an uploaded batch,
so a PR raised by hand gets exactly the same policy treatment as a PR line in a CSV.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from .. import models as m
from . import batches as bsvc

PR_PREFIX = {"chat": "PR-CH", "form": "PR-MN"}
DEPARTMENT = {"chat": "Chat", "form": "Manual form"}
URGENCIES = ("Normal", "Emergency")
DECISION_FIELDS = ("route", "decision", "value", "group_id", "supplier_id", "supplier_name", "unit_price",
                   "suggested", "reason", "flags", "policy_version")


def _request_batch(session) -> m.Batch:
    batch = session.scalar(select(m.Batch).where(m.Batch.kind == "chat"))
    if batch is None:
        batch = m.Batch(name="Chat requests", kind="chat", created_by="chat", lines=[])
        session.add(batch)
        session.flush()
    return batch


def raise_pr(session, card: dict, requester: str, channel: str) -> dict:
    """Append one PR line built from `card`, re-decide the batch and return the decision for that PR."""
    batch = _request_batch(session)
    n = len(batch.lines) + 1
    pr_no = f"{PR_PREFIX[channel]}-{n:04d}"
    line = {"pr_no": pr_no, "pr_line": 1, "plant": card["plant"],
            "item_code": "" if card["is_new"] else card["item_code"], "description": card["description"],
            "uom": card["uom"], "department": DEPARTMENT[channel], "requester": requester,
            "urgency": card["urgency"], "quantity": card["quantity"], "estimated_unit_price": card["est_unit_price"],
            "errors": [], "row": n, "force_new": card["is_new"],
            "created_at": bsvc.now_ist().isoformat(sep=" "), "need_by": card["need_by"]}
    batch.lines = list(batch.lines) + [line]
    flag_modified(batch, "lines")
    result = bsvc.run_batch(session, batch)
    req = next(r for r in result["requirements"] if any(ln["pr_no"] == pr_no for ln in r["lines"]))
    return {"pr_no": pr_no, "batch_id": batch.id, "requirement": req,
            "decision": {k: req.get(k) for k in DECISION_FIELDS}}


def decision_reply(pr_no: str, req: dict) -> str:
    return (f"Raised **{pr_no}**. Procurement policy v{req['policy_version']} says: "
            f"**{req['route'].replace('_', ' ')}** for the whole requirement worth ₹{req['value']:,.0f}. {req['reason']}")


def _number(v, name: str, errors: list, *, required: bool, positive: bool = False) -> float | None:
    if v in (None, ""):
        if required:
            errors.append(f"{name} is required.")
        return None
    try:
        x = float(str(v).replace(",", ""))
    except ValueError:
        errors.append(f"{name} must be a number.")
        return None
    if (positive and x <= 0) or x < 0:
        errors.append(f"{name} must be greater than zero." if positive else f"{name} cannot be negative.")
        return None
    return x


def card_from_form(body: dict, items: dict, plants: dict, today: date) -> tuple[dict | None, list[str]]:
    """Validate the manual PR form. Returns (card, errors); card is None when there are errors."""
    errors: list[str] = []
    is_new = bool(body.get("is_new"))
    item = None
    if is_new:
        description = str(body.get("description") or "").strip()
        if len(description) < 3:
            errors.append("Describe the new item (at least 3 characters).")
        uom = str(body.get("uom") or "NOS").strip().upper()[:16]
    else:
        code = str(body.get("item_code") or "").strip().upper()
        item = items.get(code)
        if not item:
            errors.append("Choose an item from the item master, or mark it as a new item." if not code
                          else f"{code} is not in the item master.")
        description, uom = (item["description"], item["uom"]) if item else ("", "")
    quantity = _number(body.get("quantity"), "Quantity", errors, required=True, positive=True)
    est = _number(body.get("est_unit_price"), "Estimated unit price", errors, required=False)
    plant = str(body.get("plant") or "").strip().upper()
    if plant not in plants:
        errors.append(f"Plant must be one of {', '.join(plants)}.")
    need_by = None
    try:
        need_by = date.fromisoformat(str(body.get("need_by") or ""))
        if need_by < today:
            errors.append("Need-by date cannot be in the past.")
    except ValueError:
        errors.append("Need-by date is required (YYYY-MM-DD).")
    urgency = body.get("urgency") or "Normal"
    if urgency not in URGENCIES:
        errors.append(f"Urgency must be {' or '.join(URGENCIES)}.")
    if errors:
        return None, errors
    return {"item_code": item["item_code"] if item else "NEW", "description": description, "uom": uom,
            "quantity": quantity, "plant": plant, "need_by": need_by.isoformat(), "urgency": urgency,
            "est_unit_price": est, "is_new": is_new}, []
