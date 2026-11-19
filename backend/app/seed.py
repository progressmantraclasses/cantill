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

DATA_DIR = Path(os.environ.get("DATA_DIR") or Path(__file__).resolve().parents[2] / "data")


def seed(session) -> dict:
    stats = {}
    if session.scalar(select(m.Item).limit(1)) is None:
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
        from .services import contract_extract as ce
        known = {c["id"] for c in md.contracts}
        for pdf in sorted((DATA_DIR / "contracts" / "pdf").glob("*.pdf")):
            x = ce.extract(pdf.read_bytes())
            if x.get("contract_id") and x["contract_id"] not in known and not x["warnings"]:
                f = ce.to_contract_fields(x)
                session.add(m.Contract(**f, source="pdf", added_by="seed (PDF-only contract)"))
                stats.setdefault("pdf_contracts", []).append(f["contract_id"])
        stats["master"] = True
    if session.scalar(select(m.PolicyVersion).limit(1)) is None:
        doc = json.loads((POLICY_DIR / "v5_0.json").read_text(encoding="utf-8"))
        session.add(m.PolicyVersion(version=doc["version"], effective_from=date.fromisoformat(doc["effective_from"]),
                                    status="approved", document=doc, source_kind="seed", created_by="system",
                                    approved_by="system"))
        stats["policy"] = True
    session.commit()
    return stats


def load_master_from_db(session) -> loader.MasterData:
    md = loader.MasterData()
    for i in session.scalars(select(m.Item)):
        md.items[i.item_code] = {"item_code": i.item_code, "description": i.description, "uom": i.uom,
                                 "category": i.category, "item_type": i.item_type, "standard_price": i.standard_price}
    for s in session.scalars(select(m.Supplier)):
        md.suppliers[s.supplier_id] = {
            "supplier_id": s.supplier_id, "name": s.name, "city": s.city, "categories": s.categories,
            "status": s.status, "on_time_pct": s.on_time_pct, "quality_rating": s.quality_rating,
            "category_list": [c.strip() for c in s.categories.split(";") if c.strip()]}
    for p in session.scalars(select(m.PoHistory)):
        md.pos.append({"po_number": p.po_number, "po_date": p.po_date, "supplier_id": p.supplier_id,
                       "item_code": p.item_code, "quantity": p.quantity, "unit_price": p.unit_price,
                       "plant": p.plant, "on_time": p.delivered_on_time})
    for c in session.scalars(select(m.Contract)):
        md.contracts.append({"id": c.contract_id, "supplier_id": c.supplier_id, "start": c.start_date,
                             "end": c.end_date, "cap": c.value_cap, "consumed": c.consumed_value,
                             "lines": dict(c.lines or {}), "source": c.source})
    for p in session.scalars(select(m.Plant)):
        md.plants[p.code] = p.name
    return md


def load_policies_from_db(session, include_draft_id: int | None = None) -> list[dict]:
    from .policy import normalise_policy
    out = []
    for pv in session.scalars(select(m.PolicyVersion)):
        if pv.status == "approved" or pv.id == include_draft_id:
            doc = dict(pv.document)
            doc["version"], doc["effective_from"] = pv.version, pv.effective_from
            out.append(normalise_policy(doc))
    return out
