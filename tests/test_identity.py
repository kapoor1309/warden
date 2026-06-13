"""Offline proof of the handle identity layer. No Band, no keys."""

import pytest

from agents import identity


def test_handle_built_from_prefix(monkeypatch):
    monkeypatch.setenv("BAND_HANDLE_PREFIX", "yashb967")
    monkeypatch.delenv("MATCHER_HANDLE", raising=False)
    assert identity.handle_for("MATCHER") == "yashb967/po-matcher"
    assert identity.handle_for("warden") == "yashb967/warden"


def test_prefix_unset_fails_loud(monkeypatch):
    monkeypatch.delenv("BAND_HANDLE_PREFIX", raising=False)
    monkeypatch.delenv("WARDEN_HANDLE", raising=False)
    with pytest.raises(RuntimeError):
        identity.handle_for("WARDEN")


def test_unknown_role_fails_loud(monkeypatch):
    monkeypatch.setenv("BAND_HANDLE_PREFIX", "yashb967")
    monkeypatch.delenv("NOPE_HANDLE", raising=False)
    with pytest.raises(KeyError):
        identity.handle_for("NOPE")


def test_handle_override_wins(monkeypatch):
    monkeypatch.setenv("BAND_HANDLE_PREFIX", "yashb967")
    monkeypatch.setenv("MATCHER_HANDLE", "@someoneelse/matcher-x")
    assert identity.handle_for("MATCHER") == "someoneelse/matcher-x"


def test_agent_env_fails_loud_when_missing(monkeypatch):
    monkeypatch.delenv("PAYER_AGENT_ID", raising=False)
    monkeypatch.delenv("PAYER_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        identity.agent_env("PAYER")
