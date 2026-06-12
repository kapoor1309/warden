"""Phase B, U3: run the finance-crew happy path on the clean invoice.

Shows the ordered, Warden-tagged trail with the verdict at each handoff, and
asserts the clean invoice flows correctly end to end.

This runs the crew LOGIC offline (no Band, no keys) so the happy path is
provable today. The LIVE Band version — Warden creates the room, Intake/Matcher/
Approver run as `band` Agents and @-tag Warden at each handoff — is the next
increment and needs the per-agent Band keys in .env. We do not fake that here.

Run from repo root:  python scripts/run_happy_path.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from warden.sources import Sources
from warden import invariants as inv
from warden import agents

NEXT = {"intake": "matcher", "matcher": "approver", "approver": "payer"}


def main():
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "fixtures", "invoice_clean.json")
    invoice = json.loads(open(path, encoding="utf-8").read())
    sources = Sources.from_dir()

    print(f"Invoice {invoice['invoice_id']} from {invoice.get('vendor_name')} "
          f"(claims ${invoice.get('amount')} -> {invoice.get('remit_to_account')})\n")

    records = agents.process_clean(invoice, sources)
    all_clean = True
    for r in records:
        role = r["actor_role"]
        stage = r["completed_stages"][-1]
        payee = r["facts"]["payee_account"]["value"]
        amount = r["facts"]["amount"]["value"]
        violations = inv.check(r, sources)
        verdict = "CLEAN" if not violations else f"FLAG {violations}"
        all_clean = all_clean and not violations
        print(f"  [{role:8}] {stage:13} payee={payee:9} amount=${amount:<6} "
              f"-> handoff to @{NEXT[role]}, cc @warden   [{verdict}]")

    final = records[-1]
    ordered_ok = final["completed_stages"] == ["intake", "matched", "limit_checked", "approved"]
    facts_ok = (final["facts"]["payee_account"]["value"] == "ACC-001"
                and final["facts"]["amount"]["value"] == 5000)

    print()
    if all_clean and ordered_ok and facts_ok:
        print("HAPPY PATH OK: ordered intake->matched->limit_checked->approved, "
              "Warden tagged at each handoff, facts re-derived correctly, no flags.")
        sys.exit(0)
    print("HAPPY PATH FAILED:")
    print(f"  all_clean={all_clean} ordered={ordered_ok} facts={facts_ok}")
    sys.exit(1)


if __name__ == "__main__":
    main()
