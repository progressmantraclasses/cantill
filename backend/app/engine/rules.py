"""Generic rule evaluator. Rules are DATA (policy JSON); this module has no business constants."""
from __future__ import annotations

OPS = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
    "between": lambda a, b: b[0] <= a <= b[1],
}

FACT_CATALOGUE = [
    "item_code", "item_type", "category", "plant", "department", "uom", "quantity", "value",
    "is_emergency", "is_new_item", "contract_usable", "applicable_contract_count",
    "days_since_active_purchase", "po_count_365", "need_by_lead_days",
    "preferred_supplier_count", "line_count",
]


def evaluate(cond: dict, facts: dict) -> bool:
    if "all" in cond:
        return all(evaluate(c, facts) for c in cond["all"])
    if "any" in cond:
        return any(evaluate(c, facts) for c in cond["any"])
    if "not" in cond:
        return not evaluate(cond["not"], facts)
    fact, op = cond["fact"], cond["op"]
    actual = facts.get(fact)
    if op == "exists":
        return (actual is not None) == bool(cond.get("value", True))
    if actual is None:  # unknown fact never satisfies a comparison
        return False
    try:
        return bool(OPS[op](actual, cond["value"]))
    except TypeError:
        return False


def inr(v: float) -> str:
    """Indian digit grouping (display only): 1000000 -> ₹10,00,000."""
    n = f"{abs(v):.0f}" if float(v).is_integer() else f"{abs(v):.2f}"
    whole, _, frac = n.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return "₹" + whole + ("." + frac if frac else "")


FACT_LABELS = {
    "item_type": "the item type", "category": "the item category", "plant": "the plant", "department": "the department",
    "item_code": "the item", "uom": "the unit", "quantity": "the total quantity", "value": "the requirement value",
    "days_since_active_purchase": "days since it was last bought from an Active supplier",
    "po_count_365": "the number of POs in the last 365 days", "need_by_lead_days": "days until the need-by date",
    "applicable_contract_count": "the number of applicable contracts", "preferred_supplier_count": "the number of preferred suppliers",
    "line_count": "the number of PR lines",
}
BOOL_PHRASES = {
    ("is_new_item", True): "the item is not in the item master", ("is_new_item", False): "the item is in the item master",
    ("contract_usable", True): "a rate contract can be used", ("contract_usable", False): "no rate contract can be used",
    ("is_emergency", True): "the requirement is an Emergency", ("is_emergency", False): "the requirement is not an Emergency",
}
OP_WORDS = {"eq": "is", "ne": "is not", "lt": "is below", "lte": "is at most", "gt": "is above", "gte": "is at least",
            "in": "is one of", "not_in": "is not one of", "between": "is between"}


def describe(cond: dict) -> str:
    """Plain-language rendering of a condition tree (used by the policy UI and diffs). Display only."""
    if "all" in cond:
        parts = [describe(c) for c in cond["all"]]
        return " and ".join(parts) if parts else "always"
    if "any" in cond:
        return "(" + " or ".join(describe(c) for c in cond["any"]) + ")"
    if "not" in cond:
        return "not (" + describe(cond["not"]) + ")"
    fact, op, v = cond["fact"], cond["op"], cond.get("value")
    if isinstance(v, bool) and op == "eq" and (fact, v) in BOOL_PHRASES:
        return BOOL_PHRASES[(fact, v)]
    label = FACT_LABELS.get(fact, fact.replace("_", " "))
    if op == "exists":
        return f"{label} is known" if v in (None, True) else f"{label} is not known"
    if fact == "value":
        v = [inr(x) for x in v] if isinstance(v, list) else inr(v)
    elif isinstance(v, list):
        v = ", ".join(map(str, v))
    return f"{label} {OP_WORDS.get(op, op)} {v}"


def run_rules(rules: list[dict], facts: dict, can_apply) -> tuple[dict | None, list[str]]:
    """First matching rule wins. `can_apply(rule)` lets the caller reject a matched rule that cannot be
    carried out (e.g. a PO rule with no eligible supplier); the runner then falls through to the next."""
    skipped: list[str] = []
    for rule in rules:
        if rule.get("enabled", True) is False:
            continue
        if evaluate(rule["when"], facts):
            ok, why = can_apply(rule)
            if ok:
                return rule, skipped
            skipped.append(f"{rule['id']} matched but {why}")
    return None, skipped
