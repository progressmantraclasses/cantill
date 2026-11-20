"""Database connection: engine, scoped session and schema creation.

Configuration (backend/.env):
  DATABASE_URL  runtime connection. Empty -> local SQLite (backend/cantill.db).
                For Supabase use the transaction-mode pooler (port 6543).
  DIRECT_URL    optional session-mode / direct connection (port 5432) used only to create tables,
                because DDL is more reliable outside the transaction pooler.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import scoped_session, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")  # never overrides variables already set in the environment

DEFAULT_SQLITE_URL = f"sqlite:///{BACKEND_DIR / 'cantill.db'}"

# Query parameters that are meant for other clients (Prisma, Supabase docs) and that psycopg2 rejects.
_UNSUPPORTED_PG_PARAMS = ("pgbouncer", "connection_limit", "pool_timeout", "schema")


def normalise_url(raw: str) -> URL:
    """Turn a postgres:// or postgresql:// string into a psycopg2 SQLAlchemy URL."""
    url = make_url(raw.strip().strip('"'))
    if url.drivername in ("postgres", "postgresql"):
        url = url.set(drivername="postgresql+psycopg2")
    if url.drivername.startswith("postgresql"):
        url = url.difference_update_query(_UNSUPPORTED_PG_PARAMS)
        if "sslmode" not in url.query and url.host not in ("localhost", "127.0.0.1", "db"):
            url = url.update_query_dict({"sslmode": "require"})
    return url


def _build_engine(raw: str) -> Engine:
    url = normalise_url(raw)
    kwargs: dict = {"pool_pre_ping": True}
    if url.drivername.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update(pool_size=5, max_overflow=5, pool_recycle=300)
    return create_engine(url, **kwargs)


def database_url() -> str:
    return os.environ.get("DATABASE_URL", "").strip() or DEFAULT_SQLITE_URL


def is_postgres() -> bool:
    return database_url().startswith(("postgres://", "postgresql"))


engine = _build_engine(database_url())
Session = scoped_session(sessionmaker(bind=engine, expire_on_commit=False))


def create_schema(metadata) -> None:
    """Create missing tables, over DIRECT_URL when it is set for a Postgres database."""
    direct = os.environ.get("DIRECT_URL", "").strip()
    if is_postgres() and direct:
        ddl_engine = _build_engine(direct)
        try:
            metadata.create_all(ddl_engine)
        finally:
            ddl_engine.dispose()
    else:
        metadata.create_all(engine)
