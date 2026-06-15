"""The attack battery must block every attack — that's the whole point."""

import os

os.environ.setdefault("WARDEN_SIGNING_SECRET", "test-secret")

from warden.attack_suite import run_suite, ATTACKS


def test_every_attack_blocked():
    s = run_suite()
    assert s["total"] == len(ATTACKS)
    assert s["blocked"] == s["total"], [r for r in s["results"] if not r["blocked"]]


def test_each_result_has_a_reason():
    for r in run_suite()["results"]:
        assert r["blocked"] is True
        assert r["detail"] and r["kind"] and r["label"]
