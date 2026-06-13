"""Build the provenance record from an agent's REAL observed values.

THE SEAM (CLAUDE.md crux #4). The record an agent hands off must carry the
values it actually produced or acted on — never a hand-declared "all clean".
Warden re-derives ground truth from `sources/` and compares; this builder must
not let a real value be laundered into a safe-looking one.

Two fail-loud guarantees, both deliberate:
  - A missing real value (no payee, no amount, no stages) RAISES. We never
    fabricate a clean-looking record out of absent data.
  - Each fact records its `origin` (where the value came from). A payee that
    came from the invoice document is structurally distinguishable from one
    re-derived from the vendor record — that distinction is what makes a later
    hijack visible. An unknown origin RAISES.

The output dict matches the shape `warden.invariants.check` already consumes
(it reads `facts.*.value`); `origin` is extra provenance the engine ignores
today and the Investigator uses tomorrow.
"""

# Where a fact's value is allowed to have come from. Recorded for traceability;
# an unknown origin is a programming error, not a silent pass.
FACT_ORIGINS = {"invoice_document", "vendor_record", "purchase_order"}

_REQUIRED = ("invoice_id", "vendor_id", "actor_role", "action",
             "payee_value", "amount_value", "action_cause")


def build_record(*, invoice_id, vendor_id, completed_stages, actor_role, action,
                 payee_value, payee_origin, amount_value, amount_origin,
                 action_cause):
    """Assemble one handoff provenance record from real values. Fails loud."""
    local = locals()
    missing = [name for name in _REQUIRED
               if local[name] is None or local[name] == ""]
    if missing:
        raise ValueError(
            f"provenance: missing real values {missing} — refusing to build a "
            f"clean-looking record from absent data"
        )
    if payee_origin not in FACT_ORIGINS:
        raise ValueError(f"provenance: unknown payee_origin {payee_origin!r}")
    if amount_origin not in FACT_ORIGINS:
        raise ValueError(f"provenance: unknown amount_origin {amount_origin!r}")
    if not isinstance(completed_stages, (list, tuple)) or not completed_stages:
        raise ValueError("provenance: completed_stages must be a non-empty list")

    return {
        "invoice_id": invoice_id,
        "vendor_id": vendor_id,
        "stage": list(completed_stages)[-1],
        "completed_stages": list(completed_stages),
        "actor_role": actor_role,
        "action": action,
        "facts": {
            "amount": {"value": amount_value, "origin": amount_origin},
            "payee_account": {"value": payee_value, "origin": payee_origin},
        },
        "action_cause": action_cause,
    }
