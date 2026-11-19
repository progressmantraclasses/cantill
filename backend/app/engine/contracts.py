"""Policy 4 (contracts + ceilings) and 3.1 (valuation)."""
from __future__ import annotations

from datetime import timedelta


class Ledger:
    """Consumed value per contract for ONE batch run. Starts at the register baseline, so runs are reproducible."""

    def __init__(self, contracts: list[dict]):
        self.consumed = {c["id"]: c["consumed"] for c in contracts}

    def consume(self, contract_id: str, amount: float):
        self.consumed[contract_id] += amount


def applicable_contracts(item_code: str, req_date, md, statuses=("Active",)) -> list[dict]:
    """4.1: covers the item, date within start..end inclusive, supplier Active."""
    out = []
    for c in md.contracts:
        sup = md.suppliers.get(c["supplier_id"])
        if item_code in c["lines"] and c["start"] <= req_date <= c["end"] and sup and sup["status"] in statuses:
            out.append(c)
    return out


def pick_contract(applicable: list[dict], qty: float, ledger: Ledger, item_code: str):
    """4.2 + 4.3. Returns (chosen | None, candidates_report)."""
    report = []
    usable = []
    for c in applicable:
        rate = c["lines"][item_code]
        value = qty * rate
        left = c["cap"] - ledger.consumed[c["id"]]
        ok = ledger.consumed[c["id"]] + value <= c["cap"] + 1e-9
        report.append({"contract_id": c["id"], "rate": rate, "ceiling_left": round(left, 2),
                       "needs": round(value, 2), "usable": ok})
        if ok:
            usable.append(c)
    if not usable:
        return None, report
    best = min(usable, key=lambda c: (c["lines"][item_code], c["id"]))
    return best, report


def last_po_price(item_code: str, req_date, md, window_days: int):
    start = req_date - timedelta(days=window_days)
    cands = [p for p in md.pos if p["item_code"] == item_code and start <= p["po_date"] <= req_date]
    if not cands:
        return None
    return max(cands, key=lambda p: (p["po_date"], p["po_number"]))


def days_since_active_purchase(item_code: str, req_date, md, window_days: int, statuses=("Active",)):
    start = req_date - timedelta(days=window_days)
    best = None
    for p in md.pos:
        sup = md.suppliers.get(p["supplier_id"])
        if p["item_code"] == item_code and start <= p["po_date"] <= req_date and sup and sup["status"] in statuses:
            if best is None or p["po_date"] > best:
                best = p["po_date"]
    return None if best is None else (req_date - best).days


def value_requirement(item: dict, qty: float, req_date, md, chosen, applicable, params: dict):
    """3.1 → (unit_price, source_text, ref)."""
    if chosen is not None:
        return chosen["lines"][item["item_code"]], f"contract {chosen['id']} rate", chosen["id"]
    if applicable:  # every applicable contract is out of ceiling -> lowest applicable rate
        low = min(applicable, key=lambda c: (c["lines"][item["item_code"]], c["id"]))
        return low["lines"][item["item_code"]], f"lowest applicable contract rate ({low['id']}, out of ceiling)", low["id"]
    po = last_po_price(item["item_code"], req_date, md, params.get("last_po_window_days", 365))
    if po:
        return po["unit_price"], f"last PO {po['po_number']} ({po['po_date']})", po["po_number"]
    return item["standard_price"], "item master standard price", None
