"""Policy 7: combine PO-bound requirements into multi-line POs."""
from __future__ import annotations

from datetime import timedelta


def consolidate(reqs: list[dict], params: dict) -> list[dict]:
    """`reqs` are decided requirements (any decision). Mutates each PO-bound one with po_id; returns POs."""
    keys = params.get("keys", ["supplier_id", "plant", "route"])
    window = timedelta(hours=params.get("window_hours", 24))
    pos: list[dict] = []
    for r in sorted(reqs, key=lambda r: (r["created_at"], r["first"]["pr_no"], r["first"]["pr_line"])):
        if r["decision"] != "PO":
            continue
        target = None
        for po in pos:  # earliest open PO it qualifies for
            if all(po["key"][k] == r[k] for k in keys) and r["created_at"] - po["created_at"] <= window:
                target = po
                break
        if target is None:
            target = {"key": {k: r[k] for k in keys}, "created_at": r["created_at"], "requirements": [],
                      "po_id": f"PO-{len(pos) + 1:04d}"}
            pos.append(target)
        target["requirements"].append(r)
        r["po_id"] = target["po_id"]
    return pos
