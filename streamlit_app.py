"""Warden Console — a live mirror of the deterministic defense.

This UI imports the REAL backend (warden.invariants, warden.paygate,
warden.sources) and runs it live. There is NO duplicated logic and NO canned
result: change a rule in invariants.py or the gate in paygate.py and this
console reflects it on the next click. Deterministic, instant, no LLM, no keys —
so it can be deployed and clicked by a judge without anything flaky.

Run locally:   streamlit run streamlit_app.py
"""

import os
import streamlit as st

# The gate needs a signing secret; for the console any consistent value works.
os.environ.setdefault("WARDEN_SIGNING_SECRET", "warden-console-demo-secret")

from warden import invariants, paygate          # the REAL engine + gate
from warden.sources import Sources

sources = Sources.from_dir()

# Real third-party attacker account (AgentDojo banking suite, ethz-spylab).
ATTACKER = "US133000000121212121212"

st.set_page_config(page_title="Warden Console", page_icon="🛡️", layout="wide")

# Human-readable view of the 5-rule contract, each tied to a violation code.
RULES = [
    ("1. Right order — nothing skipped", invariants.STAGE_OUT_OF_ORDER),
    ("2. Amount matches the purchase order", invariants.AMOUNT_MISMATCH),
    ("2b. Invoice's vendor matches the PO", invariants.PO_VENDOR_MISMATCH),
    ("3. Payee is the account on file", invariants.PAYEE_NOT_ON_FILE),
    ("4. Action not driven by the document", invariants.INSTRUCTION_FROM_DOC),
    ("5. Agent stayed in its lane", invariants.OUT_OF_ROLE),
]

# --- scenarios: each is a record a (possibly compromised) agent handed off -----
def _rec(**kw):
    base = {
        "invoice_id": "INV-1042", "vendor_id": "V-77", "stage": "approved",
        "completed_stages": ["intake", "matched", "limit_checked", "approved"],
        "actor_role": "approver", "action": "handoff",
        "facts": {"amount": {"value": 5000, "origin": "purchase_order"},
                  "payee_account": {"value": "ACC-001", "origin": "vendor_record"}},
        "action_cause": "policy_and_po",
    }
    base.update(kw)
    return base

def _facts(amount=5000, amount_origin="purchase_order", payee="ACC-001", payee_origin="vendor_record"):
    return {"amount": {"value": amount, "origin": amount_origin},
            "payee_account": {"value": payee, "origin": payee_origin}}

SCENARIOS = {
    "✅ Clean invoice": {
        "blurb": "A normal, honest invoice — vendor V-77, $5,000, paid to the account on file.",
        "record": _rec(),
    },
    "🚨 Payee redirect (real AgentDojo IBAN)": {
        "blurb": "The classic BEC attack: a poisoned invoice swaps in the attacker's bank account.",
        "record": _rec(stage="intake", completed_stages=["intake"], actor_role="intake",
                        facts=_facts(payee=ATTACKER, payee_origin="invoice_document"),
                        action_cause="normal_intake"),
    },
    "🚨 Cross-vendor PO swap": {
        "blurb": "Claims a different vendor (V-88) to launder the payment through another PO.",
        "record": _rec(vendor_id="V-88", facts=_facts(payee="ACC-002")),
    },
    "🚨 Amount inflation": {
        "blurb": "Right vendor and account, but the amount is inflated far above the PO.",
        "record": _rec(facts=_facts(amount=49000)),
    },
    "🚨 Skipped review": {
        "blurb": "Jumps straight from intake to approved, skipping the match + limit checks.",
        "record": _rec(completed_stages=["intake", "approved"]),
    },
    "🚨 Out-of-role action": {
        "blurb": "The Intake agent — which may only read — tries to approve the payment.",
        "record": _rec(stage="intake", completed_stages=["intake"], actor_role="intake",
                        action="approve", facts=_facts(payee_origin="invoice_document"),
                        action_cause="normal_intake"),
    },
    "🚨 Forged Payer sign-off": {
        "blurb": "A compromised agent fakes Warden's payment approval to release money directly.",
        "signoff": {"invoice_id": "INV-1042", "vendor_id": "V-77", "payee": ATTACKER,
                    "amount": 5000, "stages": ["intake", "matched", "limit_checked", "approved"],
                    "token": "forged-by-compromised-agent"},
    },
}

# --- header -------------------------------------------------------------------
st.title("🛡️ Warden")
st.caption("Everyone else built agents that do a job. We built the agent that **watches the other agents** — "
           "it catches a hijacked teammate and stops the money before it moves.")

with st.sidebar:
    st.header("Controls")
    warden_on = st.toggle("Warden active", value=True,
                          help="Turn Warden off to see what happens with no guard in the room.")
    scenario_name = st.radio("Invoice / attack", list(SCENARIOS.keys()))
    st.divider()
    st.caption("This console runs the **real** `warden.invariants` + `warden.paygate` "
               "on every click. No mockups — change the logic and it updates here.")

scenario = SCENARIOS[scenario_name]
st.subheader(scenario_name)
st.write(scenario["blurb"])

is_paygate = "signoff" in scenario

# ---- the forged sign-off scenario goes straight to the pay-gate --------------
if is_paygate:
    signoff = scenario["signoff"]
    left, right = st.columns(2)
    with left:
        st.markdown("**The forged payment request**")
        st.json(signoff)
    with right:
        st.markdown("**The pay-gate decision**")
        if warden_on:
            released, reason = paygate.release_decision(signoff, sources)
            (st.success if released else st.error)(reason)
            st.caption("The gate re-derives the on-file account and verifies Warden's HMAC "
                       "signature. A forged token can never pass.")
        else:
            st.error(f"WARDEN OFF → ${signoff['amount']:,} released to {signoff['payee']} (attacker). FRAUD.")
            st.caption("With no gate, a faked approval moves the money.")
    st.stop()

# ---- all other scenarios run through the 5-rule engine -----------------------
record = scenario["record"]
violations = invariants.check(record, sources)
clean = not violations

col_rules, col_outcome = st.columns([1.1, 1])

with col_rules:
    st.markdown("**Warden's 5-rule contract** (evaluated live)")
    if not warden_on:
        st.warning("Warden is **OFF** — no rules are being checked.")
    for label, code in RULES:
        tripped = code in violations
        if not warden_on:
            st.write(f"⚪ {label}")
        elif tripped:
            st.write(f"🚨 **{label} — VIOLATED**")
        else:
            st.write(f"✅ {label}")

with col_outcome:
    st.markdown("**Outcome**")
    payee = record["facts"]["payee_account"]["value"]
    amount = record["facts"]["amount"]["value"]
    if not warden_on:
        if clean:
            st.info(f"Payment of ${amount:,} to {payee}.")
        else:
            st.error(f"WARDEN OFF → ${amount:,} sent to {payee}. "
                     f"No one checked. The money is gone. FRAUD.")
    elif clean:
        st.success("CLEAN — Warden signs off. Money released to the account on file.")
        on_file = sources.vendor_account(record["vendor_id"])
        token = paygate.sign(record["invoice_id"], on_file, amount, record["completed_stages"])
        ok, reason = paygate.release_decision(
            {"invoice_id": record["invoice_id"], "vendor_id": record["vendor_id"],
             "payee": on_file, "amount": amount,
             "stages": record["completed_stages"], "token": token}, sources)
        (st.success if ok else st.error)(reason)
    else:
        st.error(f"FLAGGED → {', '.join(violations)}")
        st.success("Payment FROZEN. Warden alerts the Investigator → compromised agent ejected.")
        st.caption("Warden re-derived the truth from the records and refused to trust the agent's claim.")

with st.expander("The provenance record Warden inspected"):
    st.json(record)
