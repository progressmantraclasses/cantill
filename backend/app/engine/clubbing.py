"""Policy 2: club similar PR lines into requirements (no splitting)."""
from __future__ import annotations


def club(lines: list[dict], params: dict) -> list[dict]:
    """`lines` need: item (resolved code or None), plant, created_at, need_by, pr_no, pr_line, urgency.
    Returns requirements in creation order. A requirement = {'lines': [...], 'first': line, ...}."""
    # `params` is a dict, or a callable(first_line) -> dict so each requirement is clubbed under the
    # policy version in force on its own first-line date.
    params_for = params if callable(params) else (lambda _l: params)
    ordered = sorted(lines, key=lambda l: (l["created_at"], l["pr_no"], l["pr_line"]))
    reqs: list[dict] = []
    for ln in ordered:
        placed = None
        if ln["resolved_item"] is not None:  # new items are never clubbed (1.2)
            for r in reqs:
                f = r["first"]
                if f["resolved_item"] is None:
                    continue
                pp = params_for(f)
                keys = pp.get("keys", ["item_code", "plant"])
                max_created = pp.get("created_within_days", 14)
                max_need = pp.get("need_by_within_days", 7)
                if any(_key(f, k) != _key(ln, k) for k in keys):
                    continue
                if (ln["created_at"].date() - f["created_at"].date()).days > max_created:
                    continue
                if abs((ln["need_by"] - f["need_by"]).days) > max_need:
                    continue
                placed = r  # earliest qualifying requirement
                break
        if placed is None:
            reqs.append({"first": ln, "lines": [ln]})
        else:
            placed["lines"].append(ln)
    for r in reqs:
        r["created_at"] = r["first"]["created_at"]
        r["date"] = r["first"]["created_at"].date()
        r["is_emergency"] = any(l["urgency"].strip().lower() == "emergency" for l in r["lines"])
        r["quantity"] = sum(l["quantity"] for l in r["lines"])
    return reqs


def _key(line: dict, k: str):
    return line["resolved_item"] if k == "item_code" else line.get(k)
