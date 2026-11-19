"""Validation of a policy document. A draft that fails here can never be approved."""
from __future__ import annotations

from datetime import date

import jsonschema

from ..engine.rules import FACT_CATALOGUE, OPS

ROUTES = ["CONTRACT_PO", "EMERGENCY_PO", "SPOT_PO", "RFQ", "RFP", "CAPEX_SOURCING", "NEW_ITEM_SOURCING"]

POLICY_SCHEMA = {
    "type": "object",
    "required": ["version", "effective_from", "params", "rules"],
    "properties": {
        "version": {"type": "string", "minLength": 1},
        "effective_from": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
        "params": {"type": "object", "required": ["clubbing", "preferred", "consolidation"]},
        "rules": {"type": "array", "minItems": 1, "items": {
            "type": "object", "required": ["id", "when", "then"],
            "properties": {
                "id": {"type": "string"},
                "then": {"type": "object", "required": ["decision", "route"], "properties": {
                    "decision": {"enum": ["PO", "SOURCING_REQUEST"]},
                    "route": {"type": "string"},
                    "supplier": {"enum": ["contract", "preferred_1", "none"]},
                    "suggest": {"type": "integer", "minimum": 0, "maximum": 10},
                }},
            }}},
    },
}


def _check_cond(cond, where: str, errors: list[str]):
    if not isinstance(cond, dict):
        errors.append(f"{where}: condition must be an object")
        return
    for k in ("all", "any"):
        if k in cond:
            for c in cond[k]:
                _check_cond(c, where, errors)
            return
    if "not" in cond:
        _check_cond(cond["not"], where, errors)
        return
    if cond.get("fact") not in FACT_CATALOGUE:
        errors.append(f"{where}: unknown fact '{cond.get('fact')}' (known: {', '.join(FACT_CATALOGUE)})")
    if cond.get("op") not in OPS and cond.get("op") != "exists":
        errors.append(f"{where}: unknown operator '{cond.get('op')}'")


def validate(doc: dict) -> list[str]:
    errors: list[str] = []
    try:
        jsonschema.validate(doc, POLICY_SCHEMA)
    except jsonschema.ValidationError as e:
        errors.append(f"structure: {e.message} at {'/'.join(map(str, e.absolute_path)) or 'root'}")
        return errors
    try:
        date.fromisoformat(doc["effective_from"])
    except ValueError:
        errors.append("effective_from is not a valid date")
    ids = [r["id"] for r in doc["rules"]]
    if len(ids) != len(set(ids)):
        errors.append("rule ids must be unique")
    for r in doc["rules"]:
        _check_cond(r["when"], f"rule {r['id']}", errors)
        if r["then"]["route"] not in ROUTES:
            errors.append(f"rule {r['id']}: unknown route '{r['then']['route']}' (known: {', '.join(ROUTES)})")
        if r["then"]["decision"] == "PO" and r["then"].get("supplier", "none") == "none":
            errors.append(f"rule {r['id']}: a PO rule needs supplier 'contract' or 'preferred_1'")
    return errors
