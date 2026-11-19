"""Policy 1.1: match a PR line to the item master. Deterministic, no LLM."""
from __future__ import annotations

import re

DEFAULT_PARAMS = {"min_score": 0.6, "abbreviations": {}, "noise_phrases": []}


def normalise(text: str, params: dict | None = None) -> list[str]:
    p = {**DEFAULT_PARAMS, **(params or {})}
    t = (text or "").lower().replace("×", "x").replace("”", '"').replace("“", '"')
    for phrase in p["noise_phrases"]:
        t = re.sub(r"(^|[\s\-(])" + re.escape(phrase.lower()) + r"($|[\s)])", " ", t)
    t = re.sub(r"(\d)\s*\"", r"\1 inch ", t)           # 24" -> 24 inch
    t = re.sub(r"[()\",;\-]", " ", t)                  # hyphens split tokens: 6308-ZZ == 6308 ZZ
    tokens = [x for x in t.split() if x]
    return [p["abbreviations"].get(x, x) for x in tokens]


def _spec(tokens: list[str]) -> set[str]:
    return {x for x in tokens if any(ch.isdigit() for ch in x)}


def score(query: list[str], target: list[str]) -> float:
    if not query or not target:
        return 0.0
    q, t = set(query), set(target)
    dice = 2 * len(q & t) / (len(q) + len(t))
    qs, ts = _spec(query), _spec(target)
    if qs and ts and not (qs <= ts):  # a size/grade in the request that the item does not have
        return dice * 0.5
    return dice


def candidates(description: str, items: dict[str, dict], params: dict | None = None, top: int = 3):
    q = normalise(description, params)
    scored = [(score(q, normalise(it["description"], params)), code) for code, it in items.items()]
    scored.sort(key=lambda s: (-s[0], s[1]))
    return [(code, round(s, 3)) for s, code in scored[:top] if s > 0]


def contained(description: str, items: dict[str, dict], params: dict | None = None) -> list[str]:
    """Items whose name contains EVERY word the requester typed (needs 2+ words, so 'gloves' alone stays ambiguous)."""
    q = set(normalise(description, params))
    if len(q) < 2:
        return []
    return sorted(code for code, it in items.items() if q <= set(normalise(it["description"], params)))


def match_item(item_code: str | None, description: str, items: dict[str, dict], params: dict | None = None):
    """Returns (item_code | None, method, score, alternatives)."""
    p = {**DEFAULT_PARAMS, **(params or {})}
    code = (item_code or "").strip()
    if code and code in items:
        return code, "item_code", 1.0, []
    method_prefix = "description_fallback" if code else "description"
    cands = candidates(description, items, p)
    if cands and cands[0][1] >= p["min_score"]:
        # a clear winner only: a tie at the top is still resolved deterministically (lowest code) but reported
        return cands[0][0], method_prefix, cands[0][1], cands[1:]
    return None, "no_match", cands[0][1] if cands else 0.0, cands
