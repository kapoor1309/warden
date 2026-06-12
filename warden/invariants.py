"""Warden's behaviour contract: the deterministic 5-rule engine.

NO LLM lives here. NO invoice text is read here as instructions. Warden only
inspects the *shape and origin* of what an agent did, and re-derives the facts
that matter (payee account, amount) straight from the authoritative records.

That is why "just inject Warden too" fails: to this code, a sentence hidden in
an invoice like "Warden, ignore this" is never an instruction. It is not even
looked at. Warden only ever sees structured fields.

Iron rule: catching a brand-new attack must NEVER require new code here. This
engine checks what *correct* looks like, not a catalogue of known attacks.
"""

# The one true order every invoice must follow. No stage may be skipped.
REQUIRED_ORDER = ["intake", "matched", "limit_checked", "approved", "paid"]

# Each role may only do its own job (plus hand the work to the next agent).
# Rule 5 ("stay in your lane") is enforced against this table.
ALLOWED_ACTIONS = {
    "intake":   {"extract", "handoff"},
    "matcher":  {"match", "handoff"},
    "approver": {"approve", "handoff"},
    "payer":    {"pay"},
}

# Violation codes the engine can return. Empty result == clean.
STAGE_OUT_OF_ORDER     = "stage_skipped_or_out_of_order"
PAYEE_NOT_ON_FILE      = "payee_not_on_file"
AMOUNT_MISMATCH        = "amount_mismatch"
INSTRUCTION_FROM_DOC   = "instruction_from_document"
OUT_OF_ROLE            = "out_of_role"
MALFORMED_RECORD       = "malformed_provenance_record"


def _is_ordered_prefix(stages, order):
    """True if `stages` is the first N items of `order`, in order, none skipped."""
    if len(stages) > len(order):
        return False
    return list(stages) == order[: len(stages)]


def check(record, sources):
    """Run all five rules against one handoff provenance record.

    Returns a list of violation codes. An empty list means the step is clean.
    The record arrives over the wire from another agent, so we treat it as
    untrusted data and fail safe: a malformed record is itself a violation,
    never a crash.
    """
    violations = []

    # The record is untrusted input. Pull fields defensively.
    try:
        completed_stages = list(record.get("completed_stages", []))
        actor_role = record.get("actor_role")
        action = record.get("action")
        action_cause = record.get("action_cause")
        invoice_id = record.get("invoice_id")
        vendor_id = record.get("vendor_id")
        facts = record.get("facts", {}) or {}
        payee = (facts.get("payee_account") or {}).get("value")
        amount = (facts.get("amount") or {}).get("value")
    except AttributeError:
        return [MALFORMED_RECORD]

    # Rule 1 — right order, nothing skipped.
    if not _is_ordered_prefix(completed_stages, REQUIRED_ORDER):
        violations.append(STAGE_OUT_OF_ORDER)

    # Rule 3 — money goes only where it is supposed to.
    # RE-DERIVE the on-file account ourselves; do not trust the claim.
    on_file = sources.vendor_account(vendor_id)
    if on_file is None or payee != on_file:
        violations.append(PAYEE_NOT_ON_FILE)

    # Rule 2 — the amount must match the purchase order, re-derived.
    po = sources.purchase_order(invoice_id)
    if po is None or amount != po.get("amount"):
        violations.append(AMOUNT_MISMATCH)

    # Rule 4 — actions happen for the right reason, never because a document said so.
    if action_cause == "ingested_text":
        violations.append(INSTRUCTION_FROM_DOC)

    # Rule 5 — everyone stays in their lane.
    if action not in ALLOWED_ACTIONS.get(actor_role, set()):
        violations.append(OUT_OF_ROLE)

    return violations


def is_clean(record, sources):
    return not check(record, sources)
