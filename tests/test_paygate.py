"""Offline proof of the pay-gate. No Band, no LLM. The signing secret is set here."""

import pytest

from warden import paygate
from warden.sources import Sources


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("WARDEN_SIGNING_SECRET", "test-secret")


@pytest.fixture
def sources():
    return Sources.from_dir()


STAGES = ["intake", "matched", "limit_checked", "approved"]


def _signoff(invoice_id="INV-1042", vendor_id="V-77", payee="ACC-001", amount=5000, stages=STAGES, token=None):
    so = {"invoice_id": invoice_id, "vendor_id": vendor_id, "payee": payee,
          "amount": amount, "stages": stages}
    so["token"] = token if token is not None else paygate.sign(invoice_id, payee, amount, stages)
    return so


def test_valid_signoff_releases(sources):
    released, reason = paygate.release_decision(_signoff(), sources)
    assert released, reason


def test_missing_signature_freezes(sources):
    released, reason = paygate.release_decision(_signoff(token=""), sources)
    assert not released and "signature" in reason.lower()


def test_tampered_payee_freezes(sources):
    # attacker swaps the payee AFTER Warden signed the on-file account: token no longer matches.
    so = _signoff()
    so["payee"] = "ACC-99999"
    released, reason = paygate.release_decision(so, sources)
    assert not released


def test_signed_attacker_account_still_freezes_on_rederive(sources):
    # even a VALID signature over an attacker account fails: it isn't the on-file account.
    so = _signoff(payee="ACC-99999")  # token signed over ACC-99999
    released, reason = paygate.release_decision(so, sources)
    assert not released and "on-file" in reason


def test_unapproved_chain_freezes(sources):
    so = _signoff(stages=["intake", "matched"])
    released, reason = paygate.release_decision(so, sources)
    assert not released and "approved" in reason


def test_signing_secret_required(monkeypatch, sources):
    monkeypatch.delenv("WARDEN_SIGNING_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        paygate.sign("INV-1042", "ACC-001", 5000, STAGES)
