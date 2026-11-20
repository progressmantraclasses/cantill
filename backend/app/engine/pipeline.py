"""Decision pipeline: PR lines + master data + policy versions -> decisions. Pure; no DB, Flask or LLM."""
from __future__ import annotations

from datetime import date, timedelta

from . import clubbing, consolidation, contracts as ctr, matching, preferred as pref, rules as rules_mod

OUTPUT_COLUMNS = ["pr_no", "pr_line", "resolved_item_code", "group_id", "po_id", "decision", "route", "supplier_id",
                  "unit_price", "group_value_inr", "suggested_supplier_ids", "policy_version", "reason"]


def select_policy(policies: list[dict], on: date, override: str | None = None) -> dict:
    """Latest approved version whose effective_from <= date (earliest version if none qualifies)."""
    if override:
        for p in policies:
            if p["version"] == override:
                return p
        raise ValueError(f"unknown policy version {override}")
    ordered = sorted(policies, key=lambda p: (p["effective_from"], p["version"]))
    chosen = ordered[0]
    for p in ordered:
        if p["effective_from"] <= on:
            chosen = p
    return chosen


def _fmt_inr(v: float) -> str:
    s = f"{abs(v):,.0f}"
    # Indian digit grouping
    digits = s.replace(",", "")
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        digits = ",".join(parts) + "," + tail
    return "₹" + digits


def validate_lines(lines: list[dict], md) -> tuple[list[dict], list[dict]]:
    ok, bad, seen = [], [], set()
    for ln in lines:
        errs = list(ln.get("errors", []))
        if ln.get("quantity") is not None and ln["quantity"] <= 0:
            errs.append(f"quantity is {ln['quantity']:g}; it must be greater than zero")
        if ln["plant"] not in md.plants:
            errs.append(f"plant '{ln['plant']}' is not in the plant master ({', '.join(md.plants)})")
        if not ln["pr_no"]:
            errs.append("pr_no is missing")
        if not ln["item_code"] and not ln["description"]:
            errs.append("neither item code nor description given")
        key = (ln["pr_no"], ln["pr_line"])
        if key in seen:
            errs.append("duplicate pr_no + pr_line in this batch")
        seen.add(key)
        if errs:
            ln["reject_reason"] = "; ".join(errs)
            bad.append(ln)
        else:
            ok.append(ln)
    return ok, bad


def process(lines: list[dict], md, policies: list[dict], override_version: str | None = None) -> dict:
    """Returns {'rows': [...per input line...], 'requirements': [...], 'pos': [...]}."""
    ok, bad = validate_lines(lines, md)

    def pol_for(day: date) -> dict:
        return select_policy(policies, day, override_version)

    # 1. match items (policy of each line's creation date)
    for ln in ok:
        pol = pol_for(ln["created_at"].date())
        if ln.get("force_new"):  # requester confirmed in chat that this is not a catalogue item
            code, method, score, alts = None, "declared_new", 0.0, []
        else:
            code, method, score, alts = matching.match_item(ln["item_code"], ln["description"], md.items,
                                                            pol["params"].get("matching"))
        ln["resolved_item"], ln["match_method"], ln["match_score"], ln["match_alts"] = code, method, score, alts

    # 2. club into requirements
    reqs = clubbing.club(ok, lambda first: pol_for(first["created_at"].date())["params"]["clubbing"])
    for i, r in enumerate(reqs, 1):
        r["group_id"] = f"REQ-{i:04d}"

    # 3. decide each requirement in date order (ledger depends on order)
    ledger = ctr.Ledger(md.contracts)
    for r in reqs:
        _decide(r, md, pol_for(r["date"]), ledger)

    # 4. consolidate POs (policy of the PO's first requirement)
    cons_params = pol_for(reqs[0]["date"])["params"]["consolidation"] if reqs else {}
    pos = consolidation.consolidate(reqs, cons_params)

    # 5. output rows in input order
    by_line = {}
    for r in reqs:
        for ln in r["lines"]:
            by_line[id(ln)] = r
    rows = []
    for ln in lines:
        if "reject_reason" in ln:
            rows.append({"pr_no": ln["pr_no"], "pr_line": ln["pr_line"], "resolved_item_code": "", "group_id": "",
                         "po_id": "", "decision": "", "route": "NOT_PROCESSED", "supplier_id": "", "unit_price": "",
                         "group_value_inr": "", "suggested_supplier_ids": "",
                         "policy_version": pol_for(ln["created_at"].date())["version"] if ln.get("created_at") else "",
                         "reason": "Not processed: " + ln["reject_reason"]})
            continue
        r = by_line[id(ln)]
        rows.append({
            "pr_no": ln["pr_no"], "pr_line": ln["pr_line"],
            "resolved_item_code": r["item_code"] or "NEW", "group_id": r["group_id"], "po_id": r.get("po_id", ""),
            "decision": r["decision"], "route": r["route"], "supplier_id": r["supplier_id"] or "",
            "unit_price": "" if r["unit_price"] is None or r["decision"] != "PO" else round(r["unit_price"], 2),
            "group_value_inr": round(r["value"], 2),
            "suggested_supplier_ids": ";".join(s["supplier_id"] for s in r["suggested"]),
            "policy_version": r["policy_version"], "reason": r["reason"],
        })
    return {"rows": rows, "requirements": reqs, "pos": pos, "rejected": bad}


def _decide(r: dict, md, pol: dict, ledger: ctr.Ledger):
    params = pol["params"]
    statuses = tuple(params.get("eligible_supplier_statuses", ["Active"]))
    first = r["first"]
    code = first["resolved_item"]
    r["plant"], r["policy_version"], r["item_code"] = first["plant"], pol["version"], code
    r["flags"], r["contract_report"], r["preferred"] = [], [], []
    item = md.items.get(code) if code else None
    r["item"] = item
    for ln in r["lines"]:
        if ln["match_method"] == "description_fallback":
            r["flags"].append(f"item code {ln['item_code']} not in item master; matched by description")
        if "urgent" in ln["description"].lower() and not r["is_emergency"]:
            r["flags"].append("description says 'urgent' but the urgency field is not Emergency (field used)")
    lines = sorted(r["lines"], key=lambda l: (l["created_at"], l["pr_no"], l["pr_line"]))
    for a, b in zip(lines, lines[1:]):
        if abs((b["created_at"] - a["created_at"]).total_seconds()) <= 900 and a["plant"] == b["plant"]:
            r["flags"].append(f"{a['pr_no']}/{a['pr_line']} and {b['pr_no']}/{b['pr_line']} raised within 15 minutes: possible duplicate")
            break

    applicable, chosen = [], None
    if item is None:  # new item (1.2): qty x requester estimate
        ests = [l["estimated_unit_price"] for l in r["lines"] if l["estimated_unit_price"] is not None]
        unit = first["estimated_unit_price"] if first["estimated_unit_price"] is not None else (ests[0] if ests else None)
        if unit is None:
            r["flags"].append("no estimated unit price given: value taken as 0, buyer must estimate")
        r["unit_price"], r["price_source"], r["price_ref"] = (unit or 0.0), "requester estimate", None
        r["value"] = r["quantity"] * (unit or 0.0)
        facts_days, po_count, pref_list = None, 0, []
        r["item_description"] = first["description"]
    else:
        applicable = ctr.applicable_contracts(code, r["date"], md, statuses)
        chosen, r["contract_report"] = ctr.pick_contract(applicable, r["quantity"], ledger, code)
        unit, src, ref = ctr.value_requirement(item, r["quantity"], r["date"], md, chosen, applicable,
                                               params.get("valuation", {}))
        r["unit_price"], r["price_source"], r["price_ref"] = unit, src, ref
        r["value"] = r["quantity"] * unit
        win = params.get("valuation", {}).get("last_po_window_days", 365)
        facts_days = ctr.days_since_active_purchase(code, r["date"], md, win, statuses)
        po_count = sum(1 for p in md.pos if p["item_code"] == code and r["date"] - timedelta(days=win) <= p["po_date"] <= r["date"])
        pref_list = pref.preferred_list(code, r["date"], md, params.get("preferred", {}), statuses)
        r["item_description"] = item["description"]
    r["preferred"] = pref_list

    facts = {
        "item_code": code, "item_type": item["item_type"] if item else None,
        "category": item["category"] if item else None, "plant": r["plant"],
        "department": first.get("department"), "uom": item["uom"] if item else first.get("uom"),
        "quantity": r["quantity"], "value": r["value"], "is_emergency": r["is_emergency"],
        "is_new_item": item is None, "contract_usable": chosen is not None,
        "applicable_contract_count": len(applicable), "days_since_active_purchase": facts_days,
        "po_count_365": po_count, "need_by_lead_days": (min(l["need_by"] for l in r["lines"]) - r["date"]).days,
        "preferred_supplier_count": len(pref_list), "line_count": len(r["lines"]),
    }
    r["facts"] = facts

    def can_apply(rule):
        sup = rule["then"].get("supplier", "none")
        if rule["then"]["decision"] == "PO":
            if sup == "contract" and chosen is None:
                return False, "no usable contract"
            if sup == "preferred_1" and not pref_list:
                return False, "there is no eligible preferred supplier"
        return True, ""

    rule, skipped = rules_mod.run_rules(pol["rules"], facts, can_apply)
    r["skipped_rules"] = skipped
    if rule is None:
        r.update(decision="SOURCING_REQUEST", route="RFQ", supplier_id=None, suggested=[], rule_id="none")
        r["reason"] = "No policy rule matched; defaulted to RFQ for buyer review."
        r["flags"].append("no rule matched")
        return
    then = rule["then"]
    r["rule_id"], r["rule_title"] = rule["id"], rule.get("title", "")
    r["decision"], r["route"] = then["decision"], then["route"]
    r["flags"] += then.get("flags", [])
    r["suggested"], r["supplier_id"], r["relied_on"] = [], None, None
    sup_mode = then.get("supplier", "none")
    if r["decision"] == "PO":
        if sup_mode == "contract":
            r["supplier_id"] = chosen["supplier_id"]
            r["relied_on"] = f"contract {chosen['id']}"
            ledger.consume(chosen["id"], r["value"])
        else:
            top = pref_list[0]
            r["supplier_id"], r["unit_price"] = top["supplier_id"], top["reference_price"]
            # group value stays the 3.1 valuation (last PO price); the PO itself is priced at the reference price
            r["relied_on"] = f"preferred #1 {top['supplier_id']} via {top['reference_source']}"
            r["price_source"], r["price_ref"] = top["reference_source"], top["reference_source"]
    else:
        n = then.get("suggest", 0)
        r["suggested"] = pref.suggest_suppliers(item, pref_list, n, md, params.get("preferred", {}), statuses)
    r["reason"] = _reason(r, pol, rule)


def _reason(r: dict, pol: dict, rule: dict) -> str:
    v = pol["version"]
    head = f"Policy v{v} rule {rule['id']}"
    val = _fmt_inr(r["value"])
    n_lines = len(r["lines"])
    club = f" Clubbed {n_lines} PR lines into one requirement (2.2)." if n_lines > 1 else ""
    price = f" Valued at {val} using {r['price_source']}."
    if r["route"] == "CONTRACT_PO":
        body = f"{head}: contract {r['relied_on'].split()[-1]} usable (valid on {r['date']}, supplier Active, ceiling available): PO to {r['supplier_id']} at contract rate {r['unit_price']:,.2f}."
        others = [c for c in r["contract_report"] if not c["usable"]]
        if others:
            body += " Skipped for ceiling: " + ", ".join(c["contract_id"] for c in others) + "."
    elif r["decision"] == "PO":
        body = f"{head}: {rule.get('title', '')}. PO to 1st preferred supplier {r['supplier_id']} at reference price {r['unit_price']:,.2f} ({r['price_source']})."
    elif r["route"] == "NEW_ITEM_SOURCING":
        body = f"{head}: '{r['item_description']}' is not in the item master; sourcing request, buyer to find suppliers."
    elif r["route"] == "CAPEX_SOURCING":
        body = f"{head}: Capex item; sourcing with capex approval needed. Suggested: " + ", ".join(s["supplier_id"] for s in r["suggested"]) + "."
    else:
        body = f"{head}: {rule.get('title', '')}. Suggested: " + (", ".join(s["supplier_id"] for s in r["suggested"]) or "none") + "."
        if r["contract_report"] and not any(c["usable"] for c in r["contract_report"]):
            body += " Contract ceiling exhausted for " + ", ".join(c["contract_id"] for c in r["contract_report"]) + "."
    return body + price + club
