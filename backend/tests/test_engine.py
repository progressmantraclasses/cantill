import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.engine import loader, pipeline, preferred  # noqa: E402
from app.policy import load_v5  # noqa: E402

DATA = ROOT / "data"
BLOCKED = {"S004", "S008", "S011", "S031", "S034"}

PDF_CONTRACTS = [
    {"id": "RC-2026-031", "supplier_id": "S021", "start": date(2026, 11, 15), "end": date(2027, 11, 14),
     "cap": 2000000.0, "consumed": 0.0, "source": "pdf",
     "lines": {"ITM-1036": 3537.76, "ITM-1037": 2439.01, "ITM-1039": 2746.87}},
    {"id": "RC-2026-033", "supplier_id": "S035", "start": date(2026, 11, 20), "end": date(2027, 11, 19),
     "cap": 5000000.0, "consumed": 0.0, "source": "pdf",
     "lines": {"ITM-1056": 64654.36, "ITM-1057": 10689.51}},
]


@pytest.fixture(scope="module")
def md():
    return loader.load_master(DATA, extra_contracts=[dict(c) for c in PDF_CONTRACTS])


@pytest.fixture(scope="module")
def result(md):
    lines, _ = loader.parse_pr_csv((DATA / "pr_batches" / "sample_pr_batch.csv").read_bytes())
    return pipeline.process(lines, md, [load_v5()])


def row(result, pr_no, line=1):
    return next(r for r in result["rows"] if r["pr_no"] == pr_no and r["pr_line"] == line)


def test_all_lines_returned_in_input_order(result):
    assert len(result["rows"]) == 186
    assert list(result["rows"][0].keys()) == pipeline.OUTPUT_COLUMNS


@pytest.mark.parametrize("pr,route,supplier,price,value", [
    ("PR-26-00019", "CONTRACT_PO", "S001", 9168.71, 137530.65),     # ex 1
    ("PR-26-00045", "CONTRACT_PO", "S021", 2439.01, 26829.11),      # ex 2 (PDF-only contract)
    ("PR-26-00034", "CONTRACT_PO", "S007", 7.06, 32546.6),          # ex 4 (second contract out of ceiling)
    ("PR-26-00146", "SPOT_PO", "S024", 166.41, 126471.6),           # ex 5 (3 PRs clubbed)
    ("PR-26-00088", "SPOT_PO", "S023", 391.82, 97955.0),            # ex 7 (free text)
    ("PR-26-00059", "EMERGENCY_PO", "S014", 106.38, 253184.4),      # ex 8
])
def test_po_examples(result, pr, route, supplier, price, value):
    r = row(result, pr)
    assert (r["route"], r["decision"], r["supplier_id"]) == (route, "PO", supplier)
    assert r["unit_price"] == price
    assert r["group_value_inr"] == value
    assert r["po_id"].startswith("PO-")


def test_ex3_contract_ceiling_exhausted_clubs_free_text(result):
    a, b = row(result, "PR-26-00004"), row(result, "PR-26-00026")
    assert a["group_id"] == b["group_id"]
    assert a["resolved_item_code"] == "ITM-1022"
    assert (a["route"], a["suggested_supplier_ids"]) == ("RFQ", "S014;S013;S016")
    assert a["group_value_inr"] == 220255.6


def test_ex5_clubbing_shares_group(result):
    ids = {row(result, p)["group_id"] for p in ("PR-26-00146", "PR-26-00144", "PR-26-00145")}
    assert len(ids) == 1


def test_ex6_same_item_different_plant_not_clubbed(result):
    assert row(result, "PR-26-00106")["group_id"] != row(result, "PR-26-00103")["group_id"]


def test_ex9_to_13_sourcing(result):
    assert row(result, "PR-26-00089")["suggested_supplier_ids"] == "S043;S044;S042"
    assert row(result, "PR-26-00050")["suggested_supplier_ids"] == "S003;S002;S005"
    r = row(result, "PR-26-00100")
    assert (r["route"], r["suggested_supplier_ids"], r["group_value_inr"]) == ("RFP", "S020;S017;S019;S018", 2070780.0)
    r = row(result, "PR-26-00047")
    assert (r["route"], r["suggested_supplier_ids"]) == ("CAPEX_SOURCING", "S045;S047;S020;S048;S046")
    r = row(result, "PR-26-00170")
    assert (r["route"], r["resolved_item_code"], r["suggested_supplier_ids"], r["group_value_inr"]) == \
        ("NEW_ITEM_SOURCING", "NEW", "", 141100.0)


def test_ex14_consolidated_po(result):
    # PR-34 + PR-32 (one requirement) and PR-31 + PR-35 (another) are same supplier/plant/route within 24h
    # of the first requirement only for the ones that qualify; they must share a PO where policy 7.1 allows it.
    r34, r31 = row(result, "PR-26-00034"), row(result, "PR-26-00031")
    assert r34["group_id"] == row(result, "PR-26-00032")["group_id"]
    assert r31["group_id"] == row(result, "PR-26-00035")["group_id"]
    assert r34["po_id"] == r31["po_id"]
    assert r31["group_value_inr"] == 23227.0 or abs(r31["group_value_inr"] - 23227.4) < 1


def test_bad_lines_not_processed(result):
    for pr in ("PR-26-00172", "PR-26-00173"):
        r = row(result, pr)
        assert r["route"] == "NOT_PROCESSED" and r["reason"].startswith("Not processed")


def test_blocked_or_inactive_never_used(result):
    for r in result["rows"]:
        used = {r["supplier_id"], *r["suggested_supplier_ids"].split(";")} - {""}
        assert not (used & BLOCKED), (r["pr_no"], used & BLOCKED)


def test_deterministic(md):
    lines, _ = loader.parse_pr_csv((DATA / "pr_batches" / "sample_pr_batch.csv").read_bytes())
    a = pipeline.process(lines, md, [load_v5()])["rows"]
    lines, _ = loader.parse_pr_csv((DATA / "pr_batches" / "sample_pr_batch.csv").read_bytes())
    b = pipeline.process(lines, md, [load_v5()])["rows"]
    assert a == b


@pytest.mark.parametrize("item,expected", [
    ("ITM-1048", ["S029", "S030"]),
    ("ITM-1036", ["S023", "S022", "S024"]),
    ("ITM-1016", ["S009", "S010"]),
])
def test_preferred_lists_match_worked_examples(md, item, expected):
    got = preferred.preferred_list(item, date(2026, 11, 1), md, load_v5()["params"]["preferred"])
    assert [g["supplier_id"] for g in got] == expected


def test_amendment_changes_decisions_without_code(md):
    """Policy-as-data: lower the spot limit and add a plant-only rule purely by editing the JSON."""
    import copy
    base = load_v5()
    amended = copy.deepcopy(base)
    amended["version"], amended["effective_from"] = "5.1", date(2026, 11, 1)
    for r in amended["rules"]:
        if r["id"] == "5.4":
            r["when"]["all"][0]["value"] = 100000
    lines, _ = loader.parse_pr_csv((DATA / "pr_batches" / "sample_pr_batch.csv").read_bytes())
    v50 = pipeline.process(lines, md, [base])["rows"]
    lines, _ = loader.parse_pr_csv((DATA / "pr_batches" / "sample_pr_batch.csv").read_bytes())
    v51 = pipeline.process(lines, md, [base, amended])["rows"]
    changed = [(a, b) for a, b in zip(v50, v51) if a["route"] != b["route"]]
    assert changed and all(b["policy_version"] == "5.1" and b["route"] == "RFQ" for a, b in changed)
    assert row({"rows": v51}, "PR-26-00146")["route"] == "RFQ"   # 1,26,472 is no longer under the limit
