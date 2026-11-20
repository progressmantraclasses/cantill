"""Read DB state into the plain dicts the pure decision engine works with."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select

from . import models as m
from .engine import loader
from .engine.pipeline import select_policy
from .policy import normalise_policy


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
    """Approved policy versions (plus one draft, when asked) as engine-ready documents."""
    out = []
    for pv in session.scalars(select(m.PolicyVersion)):
        if pv.status == "approved" or pv.id == include_draft_id:
            doc = dict(pv.document)
            doc["version"], doc["effective_from"] = pv.version, pv.effective_from
            out.append(normalise_policy(doc))
    return out


def policy_on(session, on: date, override: str | None = None) -> dict:
    """The approved policy that applies on a given date (or the forced version)."""
    return select_policy(load_policies_from_db(session), on, override)
