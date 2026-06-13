"""Finance-crew agent logic — the real work, framework-agnostic and testable.

This is the *brain* of each worker, separated from Band/LLM transport (which is
wired in the runner scripts). Keeping it pure means the security property is
inspectable and the happy path is provable offline.

The property that matters:
  - Intake reads the UNTRUSTED invoice document. Whatever it extracts is tagged
    `origin="invoice_document"` — it came from the attacker-controllable surface.
  - Matcher and Approver RE-DERIVE the payee and amount from `sources/` (the
    vendor master and the purchase order). They do NOT carry the invoice's
    claimed values forward. So for the authoritative steps, the payee's origin
    is `vendor_record`, not the document.

For a CLEAN invoice the document's remit account equals the on-file account, so
every handoff record is clean. For a hijacked invoice, the value the document
carries diverges from what Matcher re-derives — and `invariants.check` (Rule 3,
re-derived) catches it. That detection is the next increment; Phase B only
proves the clean path and the record-building seam.

Fail loud: an unknown vendor, a missing purchase order, or an over-limit amount
RAISES. These are real exceptional conditions, not states to paper over.
"""

from warden.provenance import build_record


def extract(invoice):
    """Intake pulls fields out of the invoice document. All doc-origin."""
    return {
        "invoice_id": invoice["invoice_id"],
        "vendor_id": invoice["vendor_id"],
        "payee": invoice.get("remit_to_account"),
        "amount": invoice.get("amount"),
    }


def intake_handoff(invoice):
    """Intake → Matcher. Facts come from the document (origin=invoice_document)."""
    e = extract(invoice)
    return build_record(
        invoice_id=e["invoice_id"], vendor_id=e["vendor_id"],
        completed_stages=["intake"], actor_role="intake", action="handoff",
        payee_value=e["payee"], payee_origin="invoice_document",
        amount_value=e["amount"], amount_origin="invoice_document",
        action_cause="role_default",
    )


def matcher_handoff(invoice, sources):
    """Matcher → Approver. Payee and amount RE-DERIVED from records, not the doc."""
    vid, iid = invoice["vendor_id"], invoice["invoice_id"]
    on_file = sources.vendor_account(vid)
    po = sources.purchase_order(iid)
    if on_file is None:
        raise ValueError(f"matcher: no vendor record for {vid!r} — cannot match")
    if po is None:
        raise ValueError(f"matcher: no purchase order for {iid!r} — cannot match")
    return build_record(
        invoice_id=iid, vendor_id=vid,
        completed_stages=["intake", "matched"], actor_role="matcher", action="handoff",
        payee_value=on_file, payee_origin="vendor_record",
        amount_value=po["amount"], amount_origin="purchase_order",
        action_cause="role_default",
    )


def approver_handoff(invoice, sources):
    """Approver → (Payer). Checks the limit, then approves. Facts re-derived."""
    vid, iid = invoice["vendor_id"], invoice["invoice_id"]
    on_file = sources.vendor_account(vid)
    po = sources.purchase_order(iid)
    if on_file is None or po is None:
        raise ValueError(f"approver: missing record for {vid!r}/{iid!r}")
    amount = po["amount"]
    if amount > sources.spend_limit:
        raise ValueError(
            f"approver: amount {amount} exceeds spend limit {sources.spend_limit} "
            f"— reject, do not approve"
        )
    return build_record(
        invoice_id=iid, vendor_id=vid,
        completed_stages=["intake", "matched", "limit_checked", "approved"],
        actor_role="approver", action="handoff",
        payee_value=on_file, payee_origin="vendor_record",
        amount_value=amount, amount_origin="purchase_order",
        action_cause="policy_and_po",
    )


def process_clean(invoice, sources):
    """Run the happy path; return the ordered handoff records (intake, matcher,
    approver). For a clean invoice each is clean per `invariants.check`."""
    return [
        intake_handoff(invoice),
        matcher_handoff(invoice, sources),
        approver_handoff(invoice, sources),
    ]
