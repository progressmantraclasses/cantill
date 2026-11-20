"""Turn an amendment document or a chat instruction into a proposed new policy JSON (a DRAFT a human must approve)."""
from __future__ import annotations

import io
import json
import re

from ..engine.rules import FACT_CATALOGUE
from .schema import ROUTES

SYSTEM = """You maintain a procurement policy stored as JSON ("policy as data"). A procurement user gives you an
amendment (document text or a chat instruction). Return the COMPLETE updated policy JSON, changing ONLY what the
amendment says and keeping everything else identical.

Policy JSON shape (same as the current policy you are given):
- "version" (string), "effective_from" (YYYY-MM-DD), "params" (clubbing, valuation, preferred, consolidation,
  matching, eligible_supplier_statuses), "rules" (ordered list, FIRST MATCHING RULE WINS).
- A rule: {"id","title","when","then"}. "when" is a condition tree: {"fact","op","value"} or {"all":[...]},
  {"any":[...]}, {"not":{...}}. Operators: eq ne lt lte gt gte in not_in between exists.
- Facts you may use: %(facts)s
  (item_type is Material/Service/Capex; category e.g. "Safety & PPE"; plant is PUN1 or CHK1; value is INR;
  days_since_active_purchase is days since the last PO to an Active supplier, null if none.)
- "then": {"decision": "PO"|"SOURCING_REQUEST", "route": one of %(routes)s,
  "supplier": "contract"|"preferred_1"|"none", "suggest": integer number of suppliers to suggest}.
  A PO rule must have supplier "contract" or "preferred_1".
- Changing a limit = change the "value" in the matching condition. A new kind of rule (for example only for one plant,
  one category, one urgency) = a new rule object inserted at the right position in the ordered list, with a new id
  such as "5.3a". Rule ORDER matters: put a more specific rule before the general rule it should override.
- Set "version" to the version in the amendment if it names one, otherwise increment the minor number of the current
  version. Set "effective_from" to the date in the amendment (YYYY-MM-DD); if none is given use the value supplied
  in the request.
Return JSON only: {"policy": <full policy JSON>, "notes": "<one sentence on anything ambiguous you had to decide>"}"""


def extract_text(filename: str, data: bytes) -> tuple[str, bytes | None]:
    """Returns (text, pdf_bytes_if_text_was_empty)."""
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages).strip()
        return text, (data if not text else None)
    if name.endswith(".docx"):
        try:
            import docx
            d = docx.Document(io.BytesIO(data))
            parts = [p.text for p in d.paragraphs]
            for t in d.tables:
                for row in t.rows:
                    parts.append(" | ".join(c.text for c in row.cells))
            return "\n".join(parts), None
        except ImportError:
            import zipfile
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf8", "ignore")
            return re.sub(r"<[^>]+>", " ", xml), None
    return data.decode("utf-8", "ignore"), None


def propose(current_doc: dict, instruction_text: str, default_effective: str, llm, pdf: bytes | None = None) -> dict:
    if not llm.available():
        raise RuntimeError("AI policy reader is not configured (GEMINI_API_KEY missing). "
                           "Use the manual editor to change the policy instead.")
    system = SYSTEM % {"facts": ", ".join(FACT_CATALOGUE), "routes": ", ".join(ROUTES)}
    prompt = (f"CURRENT POLICY JSON:\n{json.dumps(current_doc, indent=1)}\n\n"
              f"DEFAULT EFFECTIVE DATE if the amendment gives none: {default_effective}\n\n"
              f"AMENDMENT:\n{instruction_text or '(see attached PDF)'}")
    out = llm.json_call(prompt, system=system, pdf=pdf)
    doc = out.get("policy", out)
    return {"policy": doc, "notes": out.get("notes", "")}


def bump_version(version: str, existing: set[str]) -> str:
    parts = version.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except ValueError:
        return version + ".1"
    v = f"{major}.{minor + 1}"
    while v in existing:
        minor += 1
        v = f"{major}.{minor + 1}"
    return v
