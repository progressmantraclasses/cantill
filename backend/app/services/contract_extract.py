"""Extract a rate contract from a signed PDF. Template parse first; LLM fallback if the template does not fit."""
from __future__ import annotations

import io
import re
from datetime import date

REQUIRED = ["contract_id", "supplier_id", "start_date", "end_date", "value_cap", "lines"]


def pdf_text(data: bytes) -> str:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_text(text: str) -> dict:
    out: dict = {"warnings": []}
    if m := re.search(r"Contract\s*No\.?\s*([A-Z]{2}-\d{4}-\d{3,4})", text):
        out["contract_id"] = m.group(1)
    if m := re.search(r"Supplier\s*ID\s*(S\d{3})", text):
        out["supplier_id"] = m.group(1)
    if m := re.search(r"valid\s+from\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", text, re.I):
        out["start_date"], out["end_date"] = m.group(1), m.group(2)
    if m := re.search(r"(?:INR|Rs\.?|₹)\s*([\d,]+(?:\.\d+)?)", text):
        out["value_cap"] = _num(m.group(1))
    lines = {}
    for m in re.finditer(r"^\s*\d+\s+(ITM-\d{4})\s+.+?\s+([A-Z]{2,4})\s+([\d,]+\.\d{1,2})\s*$", text, re.M):
        lines[m.group(1)] = _num(m.group(3))
    out["lines"] = lines
    out["consumed_value"] = 0.0
    for k in REQUIRED:
        if not out.get(k):
            out["warnings"].append(f"could not read {k}")
    return out


def extract(data: bytes, llm=None) -> dict:
    text = pdf_text(data)
    out = parse_text(text)
    if out["warnings"] and llm is not None and llm.available():
        try:
            j = llm.json_call(
                "Extract this rate contract. Return JSON with keys contract_id, supplier_id, start_date (YYYY-MM-DD), "
                "end_date (YYYY-MM-DD), value_cap (number, INR), lines (object item_code -> rate number).\n\n" + text)
            for k in REQUIRED:
                if j.get(k) and not out.get(k):
                    out[k] = j[k]
            out["warnings"] = [w for w in out["warnings"] if not out.get(w.replace("could not read ", ""))]
            out["warnings"].append("some fields were read by the AI assistant: please check them")
        except Exception as e:  # noqa: BLE001
            out["warnings"].append(f"AI fallback failed: {e}")
    out["text_preview"] = text[:600]
    return out


def to_contract_fields(x: dict) -> dict:
    return {"contract_id": x["contract_id"], "supplier_id": x["supplier_id"],
            "start_date": date.fromisoformat(x["start_date"]), "end_date": date.fromisoformat(x["end_date"]),
            "value_cap": float(x["value_cap"]), "consumed_value": float(x.get("consumed_value") or 0.0),
            "lines": {k: float(v) for k, v in x["lines"].items()}}
