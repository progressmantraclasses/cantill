"""CSV -> plain dict structures consumed by the pure engine. Also used by the DB seeder and tests."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path


def pdate(s: str) -> date:
    return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()


def pdatetime(s: str) -> datetime:
    s = s.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"bad datetime: {s!r}")


@dataclass
class MasterData:
    items: dict = field(default_factory=dict)
    suppliers: dict = field(default_factory=dict)
    pos: list = field(default_factory=list)
    contracts: list = field(default_factory=list)   # each: id, supplier_id, start, end, cap, consumed, lines{item: rate}
    plants: dict = field(default_factory=dict)


def _read(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_master(data_dir: str | Path, extra_contracts: list[dict] | None = None) -> MasterData:
    d = Path(data_dir)
    md = MasterData()
    for r in _read(d / "master_data" / "item_master.csv"):
        r["standard_price"] = float(r["standard_price"])
        md.items[r["item_code"]] = r
    for r in _read(d / "master_data" / "supplier_master.csv"):
        r["on_time_pct"] = float(r["on_time_pct"])
        r["quality_rating"] = float(r["quality_rating"])
        r["category_list"] = [c.strip() for c in r["categories"].split(";") if c.strip()]
        md.suppliers[r["supplier_id"]] = r
    for r in _read(d / "master_data" / "po_history.csv"):
        md.pos.append({
            "po_number": r["po_number"], "po_date": pdate(r["po_date"]), "supplier_id": r["supplier_id"],
            "item_code": r["item_code"], "quantity": float(r["quantity"]), "unit_price": float(r["unit_price"]),
            "plant": r["plant"], "on_time": r["delivered_on_time"].strip().lower() == "true",
        })
    for r in _read(d / "master_data" / "plants.csv"):
        md.plants[r["plant"]] = r["name"]
    lines: dict[str, dict] = {}
    for r in _read(d / "contracts" / "contract_lines.csv"):
        lines.setdefault(r["contract_id"], {})[r["item_code"]] = float(r["rate"])
    for r in _read(d / "contracts" / "contract_register.csv"):
        md.contracts.append({
            "id": r["contract_id"], "supplier_id": r["supplier_id"], "start": pdate(r["start_date"]),
            "end": pdate(r["end_date"]), "cap": float(r["value_cap"]), "consumed": float(r["consumed_value"]),
            "lines": lines.get(r["contract_id"], {}), "source": "register",
        })
    for c in extra_contracts or []:
        md.contracts.append(c)
    return md


PR_REQUIRED_COLUMNS = ("pr_no", "pr_line", "created_at", "plant", "quantity", "need_by_date")


def _check_pr_columns(fieldnames: list[str] | None) -> None:
    cols = {(c or "").strip() for c in fieldnames or []}
    missing = [c for c in PR_REQUIRED_COLUMNS if c not in cols]
    if "item_code" not in cols and "description" not in cols:
        missing.append("item_code or description")
    if missing:
        raise ValueError(f"The CSV is missing required column(s): {', '.join(missing)}. "
                         f"Expected the PR batch format: {', '.join(PR_REQUIRED_COLUMNS)}, item_code, description, …")


def parse_pr_csv(text: str | bytes) -> tuple[list[dict], list[dict]]:
    """Returns (lines, rejected). Rejected rows are returned as NOT_PROCESSED candidates by the pipeline."""
    if isinstance(text, bytes):
        try:
            text = text.decode("utf-8-sig")
        except UnicodeDecodeError as e:
            raise ValueError("The file is not a UTF-8 text CSV. Save it as 'CSV UTF-8' and upload again.") from e
    reader = csv.DictReader(io.StringIO(text))
    _check_pr_columns(reader.fieldnames)
    lines: list[dict] = []
    for i, r in enumerate(reader, start=2):
        r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
        line = {"row": i, "pr_no": r.get("pr_no", ""), "pr_line_raw": r.get("pr_line", ""),
                "plant": r.get("plant", ""), "item_code": r.get("item_code", ""),
                "description": r.get("description", ""), "uom": r.get("uom", ""),
                "department": r.get("department", ""), "requester": r.get("requester", ""),
                "urgency": r.get("urgency", "") or "Normal", "errors": []}
        try:
            line["pr_line"] = int(float(line["pr_line_raw"]))
        except ValueError:
            line["pr_line"] = 0
            line["errors"].append("pr_line is not a number")
        try:
            line["quantity"] = float(r.get("quantity", ""))
        except ValueError:
            line["quantity"] = None
            line["errors"].append("quantity is missing or not a number")
        try:
            line["estimated_unit_price"] = float(r["estimated_unit_price"]) if r.get("estimated_unit_price") else None
        except ValueError:
            line["estimated_unit_price"] = None
        try:
            line["created_at"] = pdatetime(r.get("created_at", ""))
        except ValueError:
            line["created_at"] = None
            line["errors"].append("created_at is missing or unparseable")
        try:
            line["need_by"] = pdate(r.get("need_by_date", ""))
        except ValueError:
            line["need_by"] = None
            line["errors"].append("need_by_date is missing or unparseable")
        lines.append(line)
    if not lines:
        raise ValueError("The CSV has a header but no PR lines.")
    return lines, []
