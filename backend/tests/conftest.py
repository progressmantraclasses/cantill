"""Shared test setup: an isolated SQLite database and no external services.

Environment variables are set *before* the app is imported. They are set (not removed) so that
backend/.env, loaded by app.database, can never point the tests at Supabase or Gemini.
"""
import io
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["DIRECT_URL"] = ""
os.environ["GEMINI_API_KEY"] = ""
os.environ["DATA_DIR"] = str(ROOT / "data")

from app import create_app  # noqa: E402

PROC = {"X-User": "Asha", "X-Role": "Procurement"}
BUYER = {"X-User": "Ravi", "X-Role": "Buyer"}
REQUESTER = {"X-User": "Meera", "X-Role": "Requester"}
SAMPLE = (ROOT / "data" / "pr_batches" / "sample_pr_batch.csv").read_bytes()


@pytest.fixture(scope="session")
def app():
    return create_app()


@pytest.fixture(scope="session")
def client(app):
    return app.test_client()


@pytest.fixture(scope="session")
def batch(client):
    r = client.post("/api/process-batch", data={"file": (io.BytesIO(SAMPLE), "sample.csv")}, headers=BUYER)
    assert r.status_code == 200, r.data
    return r.get_json()
