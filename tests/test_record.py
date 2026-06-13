"""Offline proof of the canonical record helpers."""

from warden import record
from warden import invariants as inv
from warden.sources import Sources


def test_extract_from_fence():
    text = 'here you go\n```json\n{"invoice_id": "INV-1042", "x": 1}\n```\nthanks'
    rec = record.extract(text)
    assert rec == {"invoice_id": "INV-1042", "x": 1}


def test_extract_from_bare_object():
    rec = record.extract('noise {"a": {"b": 2}} more noise')
    assert rec == {"a": {"b": 2}}


def test_extract_none_when_no_json():
    assert record.extract("no json here at all") is None
    assert record.extract("") is None


def test_normalize_maps_claimed_source_to_origin():
    rec = {"facts": {"payee_account": {"value": "ACC-001", "claimed_source": "vendor_record"}}}
    out = record.normalize(rec)
    assert out["facts"]["payee_account"]["origin"] == "vendor_record"


def test_normalize_is_noop_on_junk():
    assert record.normalize("not a dict") == "not a dict"
    assert record.normalize(None) is None


def test_to_message_round_trips():
    rec = {"invoice_id": "INV-1042", "facts": {"amount": {"value": 5000, "origin": "purchase_order"}}}
    msg = record.to_message(rec, "note line")
    assert record.extract(msg) == rec


def test_legacy_intake_record_still_passes_invariants():
    """An Intake record using the old claimed_source key normalizes + passes."""
    sources = Sources.from_dir()
    rec = {
        "invoice_id": "INV-1042", "vendor_id": "V-77",
        "completed_stages": ["intake"], "actor_role": "intake", "action": "handoff",
        "facts": {
            "amount": {"value": 5000, "claimed_source": "invoice_document"},
            "payee_account": {"value": "ACC-001", "claimed_source": "invoice_document"},
        },
        "action_cause": "normal_intake",
    }
    assert inv.check(record.normalize(rec), sources) == []
