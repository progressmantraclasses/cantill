"""Deterministic diff between two policy documents, rendered in plain language (we never trust an LLM summary)."""
from __future__ import annotations

from ..engine.rules import describe

SUPPLIER_TEXT = {"contract": "PO to the contract supplier at contract rate",
                 "preferred_1": "PO to the 1st preferred supplier at its reference price", "none": ""}


def rule_text(rule: dict) -> str:
    t = rule["then"]
    out = f"when {describe(rule['when'])} → {t['route']}"
    if t["decision"] == "PO":
        out += f" ({SUPPLIER_TEXT.get(t.get('supplier'), '')})"
    elif t.get("suggest"):
        out += f" (suggest {t['suggest']} suppliers)"
    return out


def _leaves(d, prefix=""):
    if isinstance(d, dict):
        for k, v in d.items():
            yield from _leaves(v, f"{prefix}{k}.")
    else:
        yield prefix[:-1], d


def diff(old: dict, new: dict) -> list[dict]:
    changes: list[dict] = []
    if old["effective_from"] != new["effective_from"]:
        changes.append({"kind": "changed", "area": "effective date",
                        "text": f"Effective date: {old['effective_from']} → {new['effective_from']}"})
    old_p, new_p = dict(_leaves(old["params"])), dict(_leaves(new["params"]))
    for k in sorted(set(old_p) | set(new_p)):
        if old_p.get(k) != new_p.get(k):
            kind = "added" if k not in old_p else "removed" if k not in new_p else "changed"
            changes.append({"kind": kind, "area": "parameter", "path": k,
                            "text": f"Setting '{k.replace('.', ' › ')}': {old_p.get(k, '(none)')} → {new_p.get(k, '(removed)')}"})
    old_r, new_r = {r["id"]: r for r in old["rules"]}, {r["id"]: r for r in new["rules"]}
    for rid, r in new_r.items():
        if rid not in old_r:
            changes.append({"kind": "added", "area": "rule", "rule": rid, "text": f"New rule {rid}: {rule_text(r)}"})
        elif r != old_r[rid]:
            changes.append({"kind": "changed", "area": "rule", "rule": rid,
                            "text": f"Rule {rid} changed.\n  was: {rule_text(old_r[rid])}\n  now: {rule_text(r)}"})
    for rid in old_r:
        if rid not in new_r:
            changes.append({"kind": "removed", "area": "rule", "rule": rid,
                            "text": f"Rule {rid} removed (was: {rule_text(old_r[rid])})"})
    old_order = [r["id"] for r in old["rules"] if r["id"] in new_r]
    new_order = [r["id"] for r in new["rules"] if r["id"] in old_r]
    if old_order != new_order:
        changes.append({"kind": "changed", "area": "rule order",
                        "text": "Rule order changed: " + " → ".join(new_order)})
    return changes
