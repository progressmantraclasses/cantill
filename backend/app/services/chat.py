"""Chat intake. Replies are templated and item matching is deterministic, so the assistant can never invent an item.
The LLM (when configured) is used only to pull slots out of free text; a regex parser is the fallback."""
from __future__ import annotations

import re
from datetime import date, timedelta

from ..engine import matching

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
PLANT_WORDS = {"CHK1": ["chk1", "chakan"], "PUN1": ["pun1", "bhosari", "pune"]}
URGENT_WORDS = ["emergency", "urgent", "asap", "breakdown", "line down", "line is down", "stoppage", "immediately"]
UNITS = r"(?:nos|no|pcs|pc|pieces|piece|kg|kgs|mtr|mtrs|meters|metres|ltr|ltrs|litres|liters|pair|pairs|set|sets|ream|reams|cyl|rol|brl|bkt|job|jobs|mon|qtr|units?)"


def parse_date(phrase: str, today: date) -> date | None:
    p = (phrase or "").strip().lower()
    if not p:
        return None
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", p):
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    if "day after tomorrow" in p:
        return today + timedelta(days=2)
    if "tomorrow" in p:
        return today + timedelta(days=1)
    if "today" in p or "eod" in p:
        return today
    if m := re.search(r"(?:in|within)\s+(\d+)\s+(day|week)s?", p):
        return today + timedelta(days=int(m[1]) * (7 if m[2] == "week" else 1))
    if "next week" in p:
        return today + timedelta(days=7)
    if "end of month" in p or "month end" in p:
        nxt = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        return nxt - timedelta(days=1)
    for i, w in enumerate(WEEKDAYS):
        if re.search(rf"\b{w[:3]}\w*\b", p) and re.search(rf"\b{w}\b|\b{w[:3]}\b", p):
            ahead = (i - today.weekday()) % 7
            if "next" in p:
                ahead = ahead + 7 if ahead else 7
            elif ahead == 0:
                ahead = 7
            return today + timedelta(days=ahead)
    if m := re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s*(?:of\s*)?([a-z]{3})[a-z]*(?:\s*,?\s*(\d{4}))?", p):
        if m[2] in MONTHS:
            return _mk(today, int(m[1]), MONTHS[m[2]], m[3])
    if m := re.search(r"([a-z]{3})[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?(?:\s*,?\s*(\d{4}))?", p):
        if m[1] in MONTHS:
            return _mk(today, int(m[2]), MONTHS[m[1]], m[3])
    if m := re.search(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", p):
        y = m[3]
        return _mk(today, int(m[1]), int(m[2]), ("20" + y) if y and len(y) == 2 else y)
    return None


def _mk(today: date, d: int, mo: int, y: str | None) -> date | None:
    try:
        if y:
            return date(int(y), mo, d)
        cand = date(today.year, mo, d)
        return cand if cand >= today else date(today.year + 1, mo, d)
    except ValueError:
        return None


def regex_extract(text: str) -> dict:
    t = text.strip()
    low = t.lower()
    out: dict = {}
    for plant, words in PLANT_WORDS.items():
        if any(re.search(rf"\b{w}\b", low) for w in words):
            out["plant"] = plant
            break
    if any(w in low for w in URGENT_WORDS):
        out["urgency"] = "Emergency"
    if re.search(r"\bnot urgent\b|\bnormal\b|\bno rush\b|\bnot an emergency\b", low):
        out["urgency"] = "Normal"
    num = r"(\d[\d,]*(?:\.\d+)?)"
    price = (re.search(r"(?<![a-z0-9])(?:rs\.?|₹|inr)\s*" + num, low)
             or re.search(r"(?<![a-z0-9@])(?:@|at)\s*" + num, low)
             or re.search(r"est(?:imated)?\.?\s*(?:unit\s*)?price(?: of)?\s*" + num, low))
    if price:
        out["est_unit_price"] = float(price[1].replace(",", ""))
        low_noprice = low[:price.start()] + " " + low[price.end():]
    else:
        low_noprice = low
    when = None
    if m := re.search(r"\b(?:by|before|on|due(?: on| by)?|latest(?: by)?)\s+(.+?)(?:\s+for\b|\s+at\b|[.,;]|$)", low):
        when = m[1]
    if when is None and re.search(r"\b(tomorrow|today|next \w+|in \d+ (?:day|week)s?)\b", low):
        when = low
    if when:
        out["need_by_phrase"] = when
    # take the first number that is not part of a date or plant code or spec like 6205
    for m in re.finditer(rf"\b(\d[\d,]*(?:\.\d+)?)\s*({UNITS})?\b", low_noprice):
        start = m.start()
        if m[2] or re.match(r"\s*(?:x|of|nos|pcs)\b", low_noprice[m.end():m.end() + 6]) or start < 3:
            out["quantity"] = float(m[1].replace(",", ""))
            break
    if "quantity" not in out:
        if m := re.search(r"\b(?:need|want|require|buy|order|get|qty|quantity|raise)\s+(?:a\s+)?(\d[\d,]*(?:\.\d+)?)\b", low):
            out["quantity"] = float(m[1].replace(",", ""))
    # item text: remove everything that is not the item
    item = t
    item = re.sub(r"(?i)\b(?:by|before|on|due|latest)\s+(.+?)(?=\s+for\b|[.,;]|$)", " ", item)
    item = re.sub(r"(?i)\b(?:i\s+)?(?:need|want|require|please|pls|raise|a pr for|pr for|order|buy|get|me|us|some)\b", " ", item)
    item = re.sub(r"(?i)\bfor\s+(?:the\s+)?(?:chakan|pune|bhosari|chk1|pun1)(?:\s+plant)?\b", " ", item)
    item = re.sub(r"(?i)\b(?:chakan|pune|bhosari|chk1|pun1)(?:\s+plant)?\b", " ", item)
    item = re.sub(r"(?i)\b(?:urgent(?:ly)?|asap|emergency|immediately|not urgent|normal)\b", " ", item)
    if price:  # drop the price phrase (and a trailing "each") from the item text
        item = re.sub(r"(?i)(?<![a-z0-9])(?:@|at|est(?:imated)?\.?\s*(?:unit\s*)?price(?: of)?)?\s*(?:rs\.?|₹|inr)?\s*"
                      + re.escape(price[1]) + r"(?:\s*(?:/-|each|per\s+\w+))?", " ", item, count=1)
    if "quantity" in out:
        q = f"{out['quantity']:g}"
        item = re.sub(rf"(?i)(?<![\w.]){re.escape(q)}(?:,\d+)*\s*{UNITS}?\b", " ", item, count=1)
    item = re.sub(r"(?i)\b(?:of|the|to)\b", " ", item)
    item = re.sub(r"[,;.]", " ", item)
    item = re.sub(r"\s+", " ", item).strip(" -")
    if item and len(item) > 1:
        out["item_text"] = item
    return out


def extract(text: str, today: date, llm=None) -> dict:
    out = regex_extract(text)
    if llm is not None and llm.available():
        try:
            j = llm.json_call(
                "Extract purchase request details from the user's message. Return JSON with keys: item_text (what they "
                "want to buy, as they wrote it, no quantity/plant/date words), quantity (number or null), plant "
                "(PUN1 for Pune/Bhosari, CHK1 for Chakan, or null), need_by_phrase (the date words as written, or "
                "null), urgency (Emergency only if they say it is urgent/emergency/breakdown, else Normal or null), "
                "est_unit_price (number or null). Never invent values that are not in the message.\n\nMessage: " + text,
                system="You extract fields from purchase request messages. Output JSON only.")
            for k in ("item_text", "quantity", "plant", "need_by_phrase", "urgency", "est_unit_price"):
                v = j.get(k)
                if v not in (None, "", "null"):
                    out[k] = v
        except Exception:  # noqa: BLE001
            pass  # the regex result is the fallback
    if out.get("quantity") is not None:
        try:
            out["quantity"] = float(out["quantity"])
        except (TypeError, ValueError):
            out.pop("quantity")
    if out.get("plant") not in (None, "PUN1", "CHK1"):
        out.pop("plant")
    if out.get("need_by_phrase"):
        d = parse_date(str(out["need_by_phrase"]), today)
        if d:
            out["need_by"] = d.isoformat()
    return out


def fmt_qty(q: float) -> str:
    return f"{q:g}"


def next_step(slots: dict, items: dict, params: dict, today: date) -> dict:
    """Decide the assistant's next message from the slots. Returns {reply, state, options?, card?}."""
    # 1. item
    if not slots.get("item_code") and not slots.get("is_new"):
        text = slots.get("item_text")
        if not text:
            return {"reply": "What do you need to buy? Tell me the item (a code like ITM-1022 or a description).",
                    "state": "need_item"}
        cands = matching.candidates(text, items, params, top=3)
        best = cands[0] if cands else None
        only = matching.contained(text, items, params)
        if len(only) == 1:
            slots["item_code"] = only[0]
        elif best and best[1] >= 0.85 and (len(cands) == 1 or best[1] - cands[1][1] >= 0.15):
            slots["item_code"] = best[0]
        elif best and best[1] >= 0.4:
            opts = [{"item_code": c, "description": items[c]["description"], "uom": items[c]["uom"]} for c, _ in cands]
            lines = "\n".join(f"{i + 1}. {o['item_code']} — {o['description']} ({o['uom']})" for i, o in enumerate(opts))
            return {"reply": f"I found a few items that could match “{text}”. Which one do you mean? "
                             f"Reply 1–{len(opts)}, or say “none” if it is something else.\n{lines}",
                    "state": "choose_item", "options": opts}
        else:
            return {"reply": f"I can't find “{text}” in the item master, so I won't guess. I can raise it as a "
                             f"**new item** for sourcing. If so, reply “new item” (and give an estimated unit price "
                             f"in ₹ if you know it), or rephrase the item name.",
                    "state": "unknown_item", "options": []}
    it = items.get(slots.get("item_code")) if slots.get("item_code") else None
    # 2. quantity
    if not slots.get("quantity") or slots["quantity"] <= 0:
        uom = f" ({it['uom']})" if it else ""
        what = it["description"] if it else slots.get("item_text", "the item")
        return {"reply": f"How many {what}{uom} do you need?", "state": "need_quantity"}
    # 3. plant
    if not slots.get("plant"):
        return {"reply": "Which plant is this for: **PUN1** (Pune - Bhosari) or **CHK1** (Chakan)?",
                "state": "need_plant", "options": [{"plant": "PUN1"}, {"plant": "CHK1"}]}
    # 4. need-by
    if not slots.get("need_by"):
        return {"reply": "By when do you need it? (e.g. “next Friday”, “25 Nov”, or 2026-12-01)", "state": "need_date"}
    if date.fromisoformat(slots["need_by"]) < today:
        slots.pop("need_by")
        return {"reply": "That date is in the past. By which date do you need it?", "state": "need_date"}
    # 5. new item needs a description + estimate
    if slots.get("is_new") and slots.get("est_unit_price") is None and not slots.get("est_asked"):
        slots["est_asked"] = True
        return {"reply": "For a new item, sourcing starts from your estimate. What is the estimated unit price in ₹? "
                         "(reply “unknown” if you have no idea; the buyer will estimate it)", "state": "need_estimate"}
    # 6. urgency: default Normal, shown on the card
    slots.setdefault("urgency", "Normal")
    card = {"item_code": slots.get("item_code") or "NEW",
            "description": it["description"] if it else slots.get("item_text"),
            "uom": it["uom"] if it else (slots.get("uom") or "NOS"), "quantity": slots["quantity"],
            "plant": slots["plant"], "need_by": slots["need_by"], "urgency": slots["urgency"],
            "est_unit_price": slots.get("est_unit_price"), "is_new": bool(slots.get("is_new"))}
    return {"reply": "Please check this request. Is it correct? Press **Confirm PR** to raise it, or tell me what to "
                     "change (for example “make it 300”, “Chakan plant”, “urgent”).",
            "state": "confirm", "card": card}
