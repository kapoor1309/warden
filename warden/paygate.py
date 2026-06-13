"""The deterministic pay-gate — the keystone (CLAUDE.md crux #4 + #5).

Money releases ONLY when:
  1. it carries Warden's HMAC sign-off over (invoice, payee, amount, stages), AND
  2. the payee re-derived from `sources/` matches the signed payee, AND
  3. the chain ran clean through 'approved'.

The Payer trusts NEITHER an agent's self-reported record NOR an unsigned message.
Warden signs the AUTHORITATIVE (re-derived) account, never an agent's claim — so a
hijack cannot obtain a sign-off for the attacker's account: Warden flags the bad
payee before 'approved' (never signs), and even the sign-off carries the on-file
account. No LLM anywhere in here.
"""

import hashlib
import hmac
import os


def _secret() -> bytes:
    s = os.getenv("WARDEN_SIGNING_SECRET")
    if not s:
        raise RuntimeError(
            "WARDEN_SIGNING_SECRET not set — the pay-gate cannot sign or verify. "
            "Set it (any private random string) in .env."
        )
    return s.encode()


def _canon(invoice_id, payee, amount, stages) -> bytes:
    return f"{invoice_id}|{payee}|{amount}|{'>'.join(stages)}".encode()


def sign(invoice_id, payee, amount, stages) -> str:
    return hmac.new(_secret(), _canon(invoice_id, payee, amount, stages), hashlib.sha256).hexdigest()


def verify(invoice_id, payee, amount, stages, token) -> bool:
    return hmac.compare_digest(sign(invoice_id, payee, amount, stages), token or "")


def release_decision(signoff, sources):
    """signoff = {invoice_id, vendor_id, payee, amount, stages, token}.
    Returns (released: bool, reason: str). Re-derives the on-file account and
    refuses on any mismatch — fail closed, never silently release."""
    inv = signoff.get("invoice_id")
    vid = signoff.get("vendor_id")
    payee = signoff.get("payee")
    amount = signoff.get("amount")
    stages = signoff.get("stages") or []
    token = signoff.get("token")

    if not verify(inv, payee, amount, stages, token):
        return False, "FROZEN: Warden signature invalid or missing"
    if "approved" not in stages:
        return False, "FROZEN: chain did not complete through 'approved'"
    on_file = sources.vendor_account(vid)
    if on_file is None or payee != on_file:
        return False, f"FROZEN: payee {payee!r} != on-file {on_file!r}"
    po = sources.purchase_order(inv)
    if po is None or po.get("vendor_id") != vid:
        return False, "FROZEN: invoice/vendor mismatch"
    if amount != po.get("amount"):
        return False, "FROZEN: amount does not match purchase order"
    return True, f"RELEASED: {amount} to {payee} (signed + re-derived)"
