"""Seed the DB from the kit CSVs + policy v5.0 when empty. Idempotent."""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from sqlalchemy import select

from . import models as m
from .engine import loader
from .policy import HERE as POLICY_DIR
from .services import contract_extract as ce

DATA_DIR = Path(os.environ.get("DATA_DIR") or Path(__file__).resolve().parents[2] / "data")


def seed(session) -> dict:
    """Load master data and policy v5.0 into empty tables. Returns what was seeded."""
    stats: dict = {}
    if session.scalar(select(m.Item).limit(1)) is None:
        _seed_master(session, stats)
    if session.scalar(select(m.PolicyVersion).limit(1)) is None:
        _seed_policy(session)
        stats["policy"] = True
    session.commit()
    return stats


def _seed_master(session, stats: dict) -> None:
    md = loader.load_master(DATA_DIR)
    for code, name in md.plants.items():
        session.add(m.Plant(code=code, name=name))
    for i in md.items.values():
        session.add(m.Item(item_code=i["item_code"], description=i["description"], uom=i["uom"],
                           category=i["category"], item_type=i["item_type"], standard_price=i["standard_price"]))
    for s in md.suppliers.values():
        session.add(m.Supplier(supplier_id=s["supplier_id"], name=s["name"], city=s["city"],
                               categories=s["categories"], status=s["status"], on_time_pct=s["on_time_pct"],
                               quality_rating=s["quality_rating"]))
    session.flush()
    for p in md.pos:
        session.add(m.PoHistory(po_number=p["po_number"], po_date=p["po_date"], supplier_id=p["supplier_id"],
                                item_code=p["item_code"], quantity=p["quantity"], uom=md.items[p["item_code"]]["uom"],
                                unit_price=p["unit_price"], plant=p["plant"], delivered_on_time=p["on_time"]))
    for c in md.contracts:
        session.add(m.Contract(contract_id=c["id"], supplier_id=c["supplier_id"], start_date=c["start"],
                               end_date=c["end"], value_cap=c["cap"], consumed_value=c["consumed"],
                               source="register", lines=c["lines"]))
    # Contracts signed after the last register update exist only as PDFs (policy 4.4): load them too.
    known = {c["id"] for c in md.contracts}
    for pdf in sorted((DATA_DIR / "contracts" / "pdf").glob("*.pdf")):
        x = ce.extract(pdf.read_bytes())
        if x.get("contract_id") and x["contract_id"] not in known and not x["warnings"]:
            f = ce.to_contract_fields(x)
            session.add(m.Contract(**f, source="pdf", added_by="seed (PDF-only contract)"))
            stats.setdefault("pdf_contracts", []).append(f["contract_id"])
    stats["master"] = True


def _seed_policy(session) -> None:
    doc = json.loads((POLICY_DIR / "v5_0.json").read_text(encoding="utf-8"))
    session.add(m.PolicyVersion(version=doc["version"], effective_from=date.fromisoformat(doc["effective_from"]),
                                status="approved", document=doc, source_kind="seed", created_by="system",
                                approved_by="system"))
