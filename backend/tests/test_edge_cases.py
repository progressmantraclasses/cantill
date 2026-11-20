"""Error paths and guard rails: bad uploads, roles, validation, JSON errors, DB URL handling."""
import io

import pytest

from conftest import BUYER, REQUESTER, SAMPLE

HEADER = b"pr_no,pr_line,created_at,requester,department,plant,item_code,description,quantity,uom,estimated_unit_price,need_by_date,urgency\n"


def upload(client, data: bytes, name="batch.csv", headers=BUYER):
    return client.post("/api/process-batch", data={"file": (io.BytesIO(data), name)}, headers=headers)


# ---------- batch upload ----------
def test_upload_without_file_is_rejected(client):
    r = client.post("/api/process-batch", headers=BUYER)
    assert r.status_code == 400 and "No CSV" in r.get_json()["error"]


def test_binary_file_is_rejected_cleanly(client):
    r = upload(client, b"%PDF-1.7\x00\xff\xfe\xfa binary", "contract.pdf")
    assert r.status_code == 400 and "UTF-8" in r.get_json()["error"]


def test_csv_with_wrong_columns_names_what_is_missing(client):
    r = upload(client, b"name,amount\nfoo,1\n")
    assert r.status_code == 400
    msg = r.get_json()["error"]
    assert "pr_no" in msg and "need_by_date" in msg


def test_header_only_csv_is_rejected(client):
    r = upload(client, HEADER)
    assert r.status_code == 400 and "no PR lines" in r.get_json()["error"]


def test_bad_rows_are_reported_not_dropped(client):
    rows = HEADER + b"PR-X1,1,2026-11-02 10:00,A,Ops,PUN1,ITM-1001,,abc,EA,,2026-11-20,Normal\n"
    r = upload(client, rows)
    assert r.status_code == 200
    [d] = r.get_json()["decisions"]
    assert d["route"] == "NOT_PROCESSED" and "quantity" in d["reason"]


def test_upload_over_size_limit_returns_json_413(app, client):
    old = app.config["MAX_CONTENT_LENGTH"]
    app.config["MAX_CONTENT_LENGTH"] = 1024
    try:
        r = upload(client, SAMPLE)
        assert r.status_code == 413 and "too large" in r.get_json()["error"]
    finally:
        app.config["MAX_CONTENT_LENGTH"] = old


# ---------- HTTP errors are always JSON ----------
def test_unknown_endpoint_is_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.is_json


def test_invalid_json_body_is_json_400(client):
    r = client.post("/api/requirements/approve", data="{not json", content_type="application/json", headers=BUYER)
    assert r.status_code == 400 and r.is_json


def test_non_object_json_body_does_not_crash(client):
    r = client.post("/api/requirements/approve", json=[1, 2, 3], headers=BUYER)
    assert r.status_code == 404  # treated as an empty body: no such requirement


def test_missing_batch_is_404(client):
    assert client.get("/api/batches/999999").status_code == 404
    assert client.get("/api/batches/999999/export.csv").status_code == 404
    assert client.post("/api/batches/999999/reprocess", json={}, headers=BUYER).status_code == 404


def test_bad_as_of_date_is_400(client):
    assert client.get("/api/preferred-suppliers?as_of=31-11-2026").status_code == 400


# ---------- roles ----------
def _first(client, batch, pred):
    reqs = client.get(f"/api/requirements?batch_id={batch['batch_id']}").get_json()["requirements"]
    return next(r for r in reqs if pred(r))


def test_requester_cannot_approve_or_override(client, batch):
    r = _first(client, batch, lambda r: r["status"] == "pending")
    body = {"batch_id": batch["batch_id"], "key": r["key"]}
    assert client.post("/api/requirements/approve", json=body, headers=REQUESTER).status_code == 403
    ov = {**body, "route": "RFQ", "comment": "trying to bypass the buyer"}
    assert client.post("/api/requirements/override", json=ov, headers=REQUESTER).status_code == 403


def test_only_procurement_can_draft_policy(client):
    r = client.post("/api/policies/drafts", json={"text": "raise the spot limit"}, headers=BUYER)
    assert r.status_code == 403


def test_override_validation(client, batch):
    r = _first(client, batch, lambda r: r["status"] == "pending" and r["decision"] != "PO")
    base = {"batch_id": batch["batch_id"], "key": r["key"], "comment": "a proper written reason"}
    assert client.post("/api/requirements/override", json={**base, "route": "TELEPORT"}, headers=BUYER).status_code == 422
    no_sup = client.post("/api/requirements/override", json={**base, "route": "SPOT_PO"}, headers=BUYER)
    assert no_sup.status_code == 422 and "supplier" in no_sup.get_json()["error"]


def test_approve_unknown_requirement_is_404(client, batch):
    r = client.post("/api/requirements/approve", json={"batch_id": batch["batch_id"], "key": "nope"}, headers=BUYER)
    assert r.status_code == 404


# ---------- contracts ----------
GOOD = {"contract_id": "RC-TEST-001", "supplier_id": "S014", "start_date": "2026-11-01", "end_date": "2027-10-31",
        "value_cap": 500000, "consumed_value": 0, "lines": {"ITM-1001": 120.5}}


@pytest.mark.parametrize("change, fragment", [
    ({"value_cap": 0}, "ceiling"),
    ({"consumed_value": 900000}, "Consumed"),
    ({"end_date": "2026-01-01"}, "End date"),
    ({"supplier_id": "S999"}, "Unknown supplier"),
    ({"lines": {"ITM-9999": 10}}, "Unknown item"),
    ({"lines": {"ITM-1001": -5}}, "rate"),
    ({"lines": {}}, "at least one"),
    ({"start_date": "not-a-date"}, "invalid"),
])
def test_contract_validation(client, change, fragment):
    r = client.post("/api/contracts", json={**GOOD, **change}, headers=BUYER)
    assert r.status_code == 422 and fragment.lower() in r.get_json()["error"].lower()


def test_contract_roles_and_duplicates(client):
    assert client.post("/api/contracts", json=GOOD, headers=REQUESTER).status_code == 403
    assert client.post("/api/contracts", json=GOOD, headers=BUYER).status_code == 200
    assert client.post("/api/contracts", json=GOOD, headers=BUYER).status_code == 409


def test_contract_extract_needs_a_file(client):
    assert client.post("/api/contracts/extract", headers=BUYER).status_code == 400


# ---------- chat ----------
def test_chat_empty_message_is_400(client):
    assert client.post("/api/chat", json={"message": "  "}).status_code == 400


def test_chat_reset_clears_slots(client):
    sid = client.post("/api/chat", json={"message": "need 200 nitrile gloves"}).get_json()["session_id"]
    r = client.post("/api/chat", json={"message": "start over", "session_id": sid}).get_json()
    assert r["slots"] == {}


def test_chat_confirm_unknown_session_is_404(client):
    assert client.post("/api/chat/confirm", json={"session_id": "missing"}).status_code == 404


# ---------- database URL handling (Supabase) ----------
def test_supabase_url_is_normalised_for_psycopg2():
    from app.database import normalise_url
    url = normalise_url('"postgresql://postgres.ref:p%2Bw%25d@aws-1-ap-south-1.pooler.supabase.com:6543/postgres?pgbouncer=true"')
    assert url.drivername == "postgresql+psycopg2"
    assert "pgbouncer" not in url.query and url.query["sslmode"] == "require"
    assert url.password == "p+w%d"


def test_sqlite_and_local_urls_are_left_alone():
    from app.database import normalise_url
    assert normalise_url("sqlite:///x.db").drivername == "sqlite"
    assert "sslmode" not in normalise_url("postgresql://u:p@localhost:5432/db").query
