"""Offline proof of the finance-crew happy path + the fail-loud reject paths.

Run:  python -m pytest tests/test_agents.py -v
"""

import json
from pathlib import Path

import pytest

from warden.sources import Sources
from warden import invariants as inv
from warden import agents


@pytest.fixture
def sources():
    return Sources.from_dir()


@pytest.fixture
def clean_invoice():
    path = Path(__file__).resolve().parent.parent / "fixtures" / "invoice_clean.json"
    return json.loads(path.read_text())


# --- the happy path -------------------------------------------------------

def test_happy_path_all_records_clean(sources, clean_invoice):
    records = agents.process_clean(clean_invoice, sources)
    assert [r["actor_role"] for r in records] == ["intake", "matcher", "approver"]
    for r in records:
        assert inv.check(r, sources) == [], (
            f"{r['actor_role']} record should be clean, got {inv.check(r, sources)}"
        )


def test_stage_order_progresses(sources, clean_invoice):
    records = agents.process_clean(clean_invoice, sources)
    assert records[0]["completed_stages"] == ["intake"]
    assert records[1]["completed_stages"] == ["intake", "matched"]
    assert records[2]["completed_stages"] == ["intake", "matched", "limit_checked", "approved"]


def test_final_facts_are_re_derived(sources, clean_invoice):
    """The authoritative payee/amount come from records, with record origin."""
    final = agents.process_clean(clean_invoice, sources)[-1]
    assert final["facts"]["payee_account"]["value"] == "ACC-001"
    assert final["facts"]["payee_account"]["origin"] == "vendor_record"
    assert final["facts"]["amount"]["value"] == 5000
    assert final["facts"]["amount"]["origin"] == "purchase_order"


def test_intake_facts_are_document_origin(sources, clean_invoice):
    """Intake's facts are tagged as coming from the untrusted document."""
    intake = agents.process_clean(clean_invoice, sources)[0]
    assert intake["facts"]["payee_account"]["origin"] == "invoice_document"


# --- fail-loud reject paths (not hijacks — normal exceptional conditions) --

def test_matcher_unknown_vendor_fails_loud(sources):
    bad = {"invoice_id": "INV-1042", "vendor_id": "V-UNKNOWN",
           "amount": 5000, "remit_to_account": "ACC-001"}
    with pytest.raises(ValueError):
        agents.matcher_handoff(bad, sources)


def test_approver_over_limit_rejected_loudly():
    s = Sources(
        vendor_master={"V-77": {"account_on_file": "ACC-001"}},
        purchase_orders={"INV-OVER": {"vendor_id": "V-77", "amount": 60000}},
        policy={"spend_limit": 50000,
                "required_order": ["intake", "matched", "limit_checked", "approved", "paid"]},
    )
    over = {"invoice_id": "INV-OVER", "vendor_id": "V-77",
            "amount": 60000, "remit_to_account": "ACC-001"}
    with pytest.raises(ValueError):
        agents.approver_handoff(over, s)
