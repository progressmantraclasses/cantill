"""Policy 6: preferred supplier list, ranking, reference price, suggestions."""
from __future__ import annotations

from datetime import date, timedelta

DEFAULT_PREF = {
    "po_window_days": 548,
    "recency_bands": [[90, 1.0], [365, 0.5]],
    "weights": {"po_count": 0.30, "recency": 0.25, "contract": 0.20, "on_time": 0.10, "quality": 0.15},
    "topup_weights": {"on_time": 0.5, "quality": 0.5},
}


def _pref(params: dict) -> dict:
    return {**DEFAULT_PREF, **(params or {})}


def recency_score(days: int | None, bands) -> float:
    if days is None:
        return 0.0
    for limit, val in bands:
        if days <= limit:
            return val
    return 0.0


def preferred_list(item_code: str, as_of: date, md, params: dict, statuses=("Active",)) -> list[dict]:
    """Ranked list (best first) with every score component, so the UI can explain the rank."""
    p = _pref(params)
    window = timedelta(days=p["po_window_days"])
    pos: dict[str, list[dict]] = {}
    for po in md.pos:
        if po["item_code"] == item_code and as_of - window <= po["po_date"] <= as_of:
            pos.setdefault(po["supplier_id"], []).append(po)
    contracts: dict[str, list[dict]] = {}
    for c in md.contracts:
        if item_code in c["lines"] and c["start"] <= as_of:
            contracts.setdefault(c["supplier_id"], []).append(c)

    ids = set(pos) | set(contracts)
    rows = []
    for sid in ids:
        sup = md.suppliers.get(sid)
        if not sup or sup["status"] not in statuses:
            continue
        sp = sorted(pos.get(sid, []), key=lambda x: (x["po_date"], x["po_number"]))
        last = sp[-1] if sp else None
        days = (as_of - last["po_date"]).days if last else None
        sc = sorted(contracts.get(sid, []), key=lambda c: (c["start"], c["id"]))
        last_contract = sc[-1] if sc else None
        if last:
            ref_price, ref_src = last["unit_price"], f"PO {last['po_number']} ({last['po_date']})"
        else:
            ref_price, ref_src = last_contract["lines"][item_code], f"contract {last_contract['id']}"
        rows.append({
            "supplier_id": sid, "name": sup["name"], "status": sup["status"],
            "po_count": len(sp), "last_po_date": last["po_date"] if last else None, "days_since_last_po": days,
            "recency": recency_score(days, p["recency_bands"]), "has_contract": bool(sc),
            "contract_id": last_contract["id"] if last_contract else None,
            "on_time_pct": sup["on_time_pct"], "quality": sup["quality_rating"],
            "reference_price": ref_price, "reference_source": ref_src,
        })
    max_count = max((r["po_count"] for r in rows), default=0) or 1
    w = p["weights"]
    for r in rows:
        comp = {
            "po_count": w["po_count"] * r["po_count"] / max_count,
            "recency": w["recency"] * r["recency"],
            "contract": w["contract"] * (1.0 if r["has_contract"] else 0.0),
            "on_time": w["on_time"] * r["on_time_pct"] / 100.0,
            "quality": w["quality"] * r["quality"] / 5.0,
        }
        r["components"] = {k: round(v, 4) for k, v in comp.items()}
        r["score"] = round(sum(comp.values()), 4)
    rows.sort(key=lambda r: (-r["score"], -(r["last_po_date"].toordinal() if r["last_po_date"] else 0), r["supplier_id"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def suggest_suppliers(item: dict | None, preferred: list[dict], n: int, md, params: dict,
                      statuses=("Active",)) -> list[dict]:
    """Policy 6.4. Returns [{supplier_id, source}] with at most n entries."""
    if n <= 0 or item is None:
        return []
    out = [{"supplier_id": r["supplier_id"], "source": "preferred list"} for r in preferred[:n]]
    if len(out) < n:
        tw = _pref(params)["topup_weights"]
        have = {o["supplier_id"] for o in out}
        pool = [s for s in md.suppliers.values()
                if s["status"] in statuses and item["category"] in s["category_list"] and s["supplier_id"] not in have]
        pool.sort(key=lambda s: (-(tw["on_time"] * s["on_time_pct"] / 100 + tw["quality"] * s["quality_rating"] / 5),
                                 s["supplier_id"]))
        for s in pool[: n - len(out)]:
            out.append({"supplier_id": s["supplier_id"], "source": "category top-up"})
    return out
