import copy
import csv
import io
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["DATA_DIR"] = str(ROOT / "data")
os.environ.pop("GEMINI_API_KEY", None)

from app import create_app  # noqa: E402

PROC = {"X-User": "Asha", "X-Role": "Procurement"}
BUYER = {"X-User": "Ravi", "X-Role": "Buyer"}
SAMPLE = (ROOT / "data" / "pr_batches" / "sample_pr_batch.csv").read_bytes()


@pytest.fixture(scope="module")
def client():
    return create_app().test_client()


@pytest.fixture(scope="module")
def batch(client):
    r = client.post("/api/process-batch", data={"file": (io.BytesIO(SAMPLE), "sample.csv")}, headers=BUYER)
    assert r.status_code == 200, r.data
    return r.get_json()


def test_process_batch_returns_decisions(batch):
    assert len(batch["decisions"]) == 186 and batch["summary"]["lines"] == 186
    assert batch["decisions"][0].keys() >= {"pr_no", "route", "group_id", "policy_version", "reason"}


def test_export_csv_columns(client, batch):
    r = client.get(f"/api/batches/{batch['batch_id']}/export.csv")
    rows = list(csv.DictReader(io.StringIO(r.data.decode())))
    assert list(rows[0].keys()) == ["pr_no", "pr_line", "resolved_item_code", "group_id", "po_id", "decision", "route",
                                    "supplier_id", "unit_price", "group_value_inr", "suggested_supplier_ids",
                                    "policy_version", "reason"]
    assert len(rows) == 186


def test_process_batch_csv_format(client):
    r = client.post("/api/process-batch?format=csv", data=SAMPLE, headers=BUYER)
    assert r.mimetype == "text/csv" and r.data.decode().count("\n") == 187


def test_contracts_loaded_including_pdf_only(client):
    ids = {c["contract_id"] for c in client.get("/api/contracts").get_json()}
    assert {"RC-2025-011", "RC-2026-031", "RC-2026-033"} <= ids


def test_preferred_suppliers_export(client):
    r = client.get("/api/preferred-suppliers?as_of=2026-11-01&format=csv")
    rows = list(csv.DictReader(io.StringIO(r.data.decode())))
    assert list(rows[0].keys()) == ["item_code", "rank", "supplier_id", "reference_price"]
    assert all(int(x["rank"]) <= 3 for x in rows)
    gloves = [x["supplier_id"] for x in rows if x["item_code"] == "ITM-1048"]
    assert gloves == ["S029", "S030"]


def test_approve_and_override_flow(client, batch):
    reqs = client.get(f"/api/requirements?batch_id={batch['batch_id']}").get_json()["requirements"]
    po = next(r for r in reqs if r["decision"] == "PO")
    r = client.post("/api/requirements/approve", json={"batch_id": batch["batch_id"], "key": po["key"]}, headers=BUYER)
    assert r.status_code == 200 and r.get_json()["document_id"]
    assert client.post("/api/requirements/approve", json={"batch_id": batch["batch_id"], "key": po["key"]},
                       headers=BUYER).status_code == 409
    rfq = next(r for r in reqs if r["route"] == "RFQ")
    bad = client.post("/api/requirements/override", json={"batch_id": batch["batch_id"], "key": rfq["key"],
                                                          "route": "SPOT_PO", "supplier_id": "S014", "comment": ""},
                      headers=BUYER)
    assert bad.status_code == 422                                   # comment is mandatory
    blocked = client.post("/api/requirements/override", json={"batch_id": batch["batch_id"], "key": rfq["key"],
                          "route": "SPOT_PO", "supplier_id": "S004", "comment": "vendor asked for it"}, headers=BUYER)
    assert blocked.status_code == 422                               # blocked supplier can never get a PO
    ok = client.post("/api/requirements/override", json={"batch_id": batch["batch_id"], "key": rfq["key"],
                     "route": "SPOT_PO", "supplier_id": "S014", "comment": "Supplier has stock, line is waiting"},
                     headers=BUYER)
    assert ok.status_code == 200
    audit = client.get("/api/audit").get_json()
    assert {"approve", "override"} <= {a["action"] for a in audit}
    assert all(a["actor"] and a["at"] for a in audit)


def test_policy_amendment_changes_decisions(client, batch):
    active = client.get("/api/policies/active").get_json()
    doc = copy.deepcopy(active["document"])
    doc["version"], doc["effective_from"] = "5.1", "2026-11-01"
    for rule in doc["rules"]:
        if rule["id"] == "5.4":
            rule["when"]["all"][0]["value"] = 100000
    # a brand new kind of rule, plant-specific, no code change
    idx = next(i for i, r in enumerate(doc["rules"]) if r["id"] == "5.4")
    doc["rules"].insert(idx, {"id": "5.3a", "title": "Safety & PPE at Chakan under 50,000 is a spot PO",
                              "when": {"all": [{"fact": "plant", "op": "eq", "value": "CHK1"},
                                               {"fact": "category", "op": "eq", "value": "Safety & PPE"},
                                               {"fact": "value", "op": "lt", "value": 50000}]},
                              "then": {"decision": "PO", "route": "SPOT_PO", "supplier": "preferred_1", "suggest": 0}})
    assert client.post("/api/policies/drafts", json={"document": doc}, headers=BUYER).status_code == 403
    r = client.post("/api/policies/drafts", json={"document": doc}, headers=PROC)
    assert r.status_code == 200, r.data
    draft = r.get_json()
    texts = " ".join(c["text"] for c in draft["changes"])
    assert "5.4" in texts and "5.3a" in texts
    assert draft["impact"]["lines_changed"] > 0
    ap = client.post(f"/api/policies/drafts/{draft['id']}/approve", headers=PROC)
    assert ap.status_code == 200
    after = client.post(f"/api/batches/{batch['batch_id']}/reprocess", headers=BUYER).get_json()
    versions = {d["policy_version"] for d in after["decisions"] if d["route"] != "NOT_PROCESSED"}
    assert versions == {"5.1"}
    oc = next(d for d in after["decisions"] if d["pr_no"] == "PR-26-00146")
    assert oc["route"] == "RFQ"


def test_invalid_policy_rejected(client):
    active = client.get("/api/policies/active").get_json()
    doc = copy.deepcopy(active["document"])
    doc["version"] = "9.9"
    doc["rules"][0]["when"] = {"fact": "colour", "op": "eq", "value": 1}
    r = client.post("/api/policies/drafts", json={"document": doc}, headers=PROC)
    assert r.status_code == 422 and "unknown fact" in str(r.get_json())


def test_chat_flow(client):
    h = {**BUYER, "X-Role": "Requester"}
    r = client.post("/api/chat", json={"message": "need 200 nitrile gloves for Chakan by next Friday"}, headers=h).get_json()
    sid = r["session_id"]
    assert r["state"] == "confirm", r
    assert r["card"]["item_code"] == "ITM-1048" and r["card"]["quantity"] == 200 and r["card"]["plant"] == "CHK1"
    done = client.post("/api/chat/confirm", json={"session_id": sid}, headers=h).get_json()
    assert done["pr_no"].startswith("PR-CH-") and done["decision"]["route"]


def test_chat_asks_for_missing_and_does_not_invent(client):
    h = {**BUYER, "X-Role": "Requester"}
    r = client.post("/api/chat", json={"message": "need some gloves"}, headers=h).get_json()
    assert r["state"] in ("choose_item", "need_quantity")
    r2 = client.post("/api/chat", json={"message": "need 2 flux capacitors for Pune by 30 Nov"}, headers=h).get_json()
    assert r2["state"] == "unknown_item" and "won't guess" in r2["reply"]
