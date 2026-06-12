"""Offline proof of the provenance seam. No Band, no LLM, no keys.

Run:  python -m pytest tests/test_provenance.py -v
"""

import pytest

from warden.sources import Sources
from warden import invariants as inv
from warden.provenance import build_record


@pytest.fixture
def sources():
    return Sources.from_dir()


def _clean_kwargs():
    """A correct approver handoff for vendor V-77 -> ACC-001, $5000."""
    return dict(
        invoice_id="INV-1042", vendor_id="V-77",
        completed_stages=["intake", "matched", "limit_checked", "approved"],
        actor_role="approver", action="handoff",
        payee_value="ACC-001", payee_origin="vendor_record",
        amount_value=5000, amount_origin="purchase_order",
        action_cause="policy_and_po",
    )


def test_clean_record_passes(sources):
    assert inv.check(build_record(**_clean_kwargs()), sources) == []


def test_tampered_payee_still_caught(sources):
    """The seam: even when the attacker lies about origin, the builder carries
    the REAL diverted value, so Rule 3 (re-derived) still catches it."""
    k = _clean_kwargs()
    k["payee_value"] = "ACC-99999"
    k["payee_origin"] = "vendor_record"  # attacker claims it's on-file
    assert inv.PAYEE_NOT_ON_FILE in inv.check(build_record(**k), sources)


def test_tampered_amount_caught(sources):
    k = _clean_kwargs()
    k["amount_value"] = 9999  # PO says 5000
    assert inv.AMOUNT_MISMATCH in inv.check(build_record(**k), sources)


def test_missing_payee_fails_loud(sources):
    """No real payee value -> raise, never a clean-looking record from nothing."""
    k = _clean_kwargs()
    k["payee_value"] = None
    with pytest.raises(ValueError):
        build_record(**k)


def test_bad_origin_fails_loud(sources):
    k = _clean_kwargs()
    k["payee_origin"] = "made_up_source"
    with pytest.raises(ValueError):
        build_record(**k)


def test_empty_stages_fails_loud(sources):
    k = _clean_kwargs()
    k["completed_stages"] = []
    with pytest.raises(ValueError):
        build_record(**k)
