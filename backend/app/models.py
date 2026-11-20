"""SQLAlchemy ORM models. The connection itself lives in database.py."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Plant(Base):
    __tablename__ = "plants"
    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))


class Item(Base):
    __tablename__ = "items"
    item_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    description: Mapped[str] = mapped_column(String(200))
    uom: Mapped[str] = mapped_column(String(16))
    category: Mapped[str] = mapped_column(String(80))
    item_type: Mapped[str] = mapped_column(String(16))
    standard_price: Mapped[float] = mapped_column(Float)


class Supplier(Base):
    __tablename__ = "suppliers"
    supplier_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(80))
    categories: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16))
    on_time_pct: Mapped[float] = mapped_column(Float)
    quality_rating: Mapped[float] = mapped_column(Float)


class PoHistory(Base):
    __tablename__ = "po_history"
    po_number: Mapped[str] = mapped_column(String(24), primary_key=True)
    po_date: Mapped[date] = mapped_column(Date, index=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))
    item_code: Mapped[str] = mapped_column(ForeignKey("items.item_code"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    uom: Mapped[str] = mapped_column(String(16))
    unit_price: Mapped[float] = mapped_column(Float)
    plant: Mapped[str] = mapped_column(String(16))
    delivered_on_time: Mapped[bool] = mapped_column(Boolean)


class Contract(Base):
    __tablename__ = "contracts"
    contract_id: Mapped[str] = mapped_column(String(24), primary_key=True)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.supplier_id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    value_cap: Mapped[float] = mapped_column(Float)
    consumed_value: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(16), default="register")  # register | pdf | manual
    lines: Mapped[dict] = mapped_column(JSON, default=dict)               # {item_code: rate}
    added_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version: Mapped[str] = mapped_column(String(32), unique=True)
    effective_from: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16))        # draft | approved | rejected
    document: Mapped[dict] = mapped_column(JSON)
    source_kind: Mapped[str] = mapped_column(String(16), default="seed")   # seed | upload | chat | manual
    source_text: Mapped[str | None] = mapped_column(Text)
    changes: Mapped[list | None] = mapped_column(JSON)       # plain-language diff vs the previous active version
    impact: Mapped[dict | None] = mapped_column(JSON)
    base_version: Mapped[str | None] = mapped_column(String(32))
    created_by: Mapped[str | None] = mapped_column(String(80))
    approved_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime)


class Batch(Base):
    __tablename__ = "batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(16), default="upload")   # upload | chat
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_by: Mapped[str | None] = mapped_column(String(80))
    lines: Mapped[list] = mapped_column(JSON, default=list)      # raw PR lines (ISO strings)
    policy_override: Mapped[str | None] = mapped_column(String(32))
    result: Mapped[dict | None] = mapped_column(JSON)            # {rows, requirements, summary}
    processed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Review(Base):
    """Buyer action on one requirement of a batch. Keyed by the requirement's line set so a reprocess keeps it."""
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("batch_id", "req_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("batches.id"))
    req_key: Mapped[str] = mapped_column(String(400))
    status: Mapped[str] = mapped_column(String(16))              # approved | overridden
    comment: Mapped[str | None] = mapped_column(Text)
    original: Mapped[dict | None] = mapped_column(JSON)          # the system decision, kept with the override
    override: Mapped[dict | None] = mapped_column(JSON)
    document_id: Mapped[str | None] = mapped_column(String(40))  # PO-xxxx / RFQ-xxxx / RFP-xxxx created
    actor: Mapped[str | None] = mapped_column(String(80))
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(24))
    action: Mapped[str] = mapped_column(String(48))
    entity: Mapped[str | None] = mapped_column(String(120))
    comment: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[dict | None] = mapped_column(JSON)


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    requester: Mapped[str | None] = mapped_column(String(80))
    slots: Mapped[dict] = mapped_column(JSON, default=dict)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    state: Mapped[str] = mapped_column(String(16), default="collecting")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
