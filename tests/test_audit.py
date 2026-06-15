"""The decision log must be explainable and tamper-evident."""

import os

os.environ.setdefault("WARDEN_SIGNING_SECRET", "test-secret")

from warden.pipeline import build_audit


def _result(status, violations=None):
    return {"steps": [{"agent": "Warden", "title": "checked", "lines": ["x"],
                       "violations": violations or []}],
            "outcome": {"status": status, "message": "because"}}


def test_blocked_cannot_proceed_and_clean_can():
    assert build_audit(_result("BLOCKED", ["payee_not_on_file"]))["verdict"]["can_pay"] is False
    assert build_audit(_result("RELEASED"))["verdict"]["can_pay"] is True


def test_signature_present_and_deterministic():
    a, b = build_audit(_result("BLOCKED")), build_audit(_result("BLOCKED"))
    assert a["signature"]["value"] and a["signature"]["algo"] == "HMAC-SHA256"
    assert a["signature"]["value"] == b["signature"]["value"]  # same input -> same sig


def test_signature_breaks_when_log_is_tampered():
    a = build_audit(_result("BLOCKED", ["payee_not_on_file"]))
    b = build_audit(_result("RELEASED"))  # different verdict
    assert a["signature"]["value"] != b["signature"]["value"]
