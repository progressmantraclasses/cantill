"""Manual PR form (POST /api/prs): same engine and audit trail as the chat, with strict validation."""
from datetime import date, timedelta

import pytest

from conftest import REQUESTER

SOON = (date.today() + timedelta(days=10)).isoformat()
GOOD = {"item_code": "ITM-1001", "quantity": 25, "plant": "PUN1", "need_by": SOON, "urgency": "Normal"}


def test_manual_pr_is_decided_by_policy(client):
    r = client.post("/api/prs", json=GOOD, headers=REQUESTER)
    assert r.status_code == 200, r.data
    body = r.get_json()
    assert body["pr_no"].startswith("PR-MN-")
    assert body["decision"]["route"] and body["decision"]["policy_version"]
    assert body["pr_no"] in body["reply"]
    # it lands in the request batch and the audit log like a chat PR
    reqs = client.get(f"/api/requirements?batch_id={body['batch_id']}").get_json()["requirements"]
    assert any(ln["pr_no"] == body["pr_no"] for r in reqs for ln in r["lines"])
    audit = client.get("/api/audit").get_json()
    assert any(a["action"] == "raise_pr" and a["entity"] == body["pr_no"] for a in audit)


def test_manual_new_item_goes_to_sourcing(client):
    r = client.post("/api/prs", json={**GOOD, "item_code": "", "is_new": True, "description": "Custom jig fixture",
                                      "uom": "nos", "est_unit_price": 4500}, headers=REQUESTER)
    assert r.status_code == 200, r.data
    assert r.get_json()["decision"]["route"] == "NEW_ITEM_SOURCING"
    assert r.get_json()["card"]["uom"] == "NOS"


def test_pr_numbers_are_unique_across_channels(client):
    a = client.post("/api/prs", json=GOOD, headers=REQUESTER).get_json()["pr_no"]
    b = client.post("/api/prs", json=GOOD, headers=REQUESTER).get_json()["pr_no"]
    assert a != b


@pytest.mark.parametrize("change, fragment", [
    ({"item_code": ""}, "Choose an item"),
    ({"item_code": "ITM-9999"}, "not in the item master"),
    ({"quantity": 0}, "Quantity must be greater than zero"),
    ({"quantity": "lots"}, "Quantity must be a number"),
    ({"quantity": None}, "Quantity is required"),
    ({"plant": "XYZ9"}, "Plant must be one of"),
    ({"need_by": "2020-01-01"}, "past"),
    ({"need_by": ""}, "Need-by date is required"),
    ({"urgency": "Whenever"}, "Urgency must be"),
    ({"est_unit_price": -3}, "cannot be negative"),
    ({"item_code": "", "is_new": True, "description": "x"}, "at least 3 characters"),
])
def test_manual_pr_validation(client, change, fragment):
    r = client.post("/api/prs", json={**GOOD, **change}, headers=REQUESTER)
    assert r.status_code == 422
    assert any(fragment in e for e in r.get_json()["errors"]), r.get_json()


def test_chat_confirm_still_raises_after_refactor(client):
    sid = None
    for msg in ["need 200 nitrile gloves for Chakan by next Friday"]:
        r = client.post("/api/chat", json={"message": msg, "session_id": sid}).get_json()
        sid = r["session_id"]
    if r["state"] == "choose_item":
        r = client.post("/api/chat", json={"message": "1", "session_id": sid}).get_json()
    assert r["state"] == "confirm", r
    done = client.post("/api/chat/confirm", json={"session_id": sid}).get_json()
    assert done["pr_no"].startswith("PR-CH-") and done["decision"]["route"]
