"""LIVE demo: an agent recruiting an agent on Band.

Story this proves on the real platform:
  1. Warden (room owner) opens an invoice room with the finance crew + the
     security crew. The Threat-Intel specialist is deliberately LEFT OUT.
  2. A poisoned "approved" handoff arrives (a CLEARLY-LABELLED dev stand-in for
     the finance crew's output — the payee account was swapped to a known mule
     account, the classic business-email-compromise move).
  3. Warden re-derives the real account, sees it does not match the vendor record,
     and @mentions the Investigator.
  4. The Investigator decides it needs help: it RECRUITS the Threat-Intel agent
     LIVE into the room (band_add_participant) and asks it to screen the account.
  5. Threat-Intel screens it against the fraud watchlist (deterministic) and
     narrates the risk (Featherless), then replies.
  6. The Investigator rules "compromised" and the Enforcer ejects the compromised
     agent before any payment is released.

We assert the two things that make it real:
  - Threat-Intel was pulled into the room LIVE (it started outside it).
  - The compromised agent was ejected (containment).

Run from repo root:  python scripts/run_recruitment.py
(Needs all agent keys in .env, plus AIML_API_KEY for the Investigator and,
optionally, FEATHERLESS_API_KEY for Threat-Intel's narration.)
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from band_client import BandClient
from agents.identity import handle_for
from warden.provenance import build_record
from warden import record as record_lib

# How long to let the live LLM chain play out (Investigator does two turns and
# Threat-Intel may call Featherless). Bump if your providers are slow.
SETTLE_SECONDS = int(os.getenv("RECRUIT_SETTLE_SECONDS", "90"))


def _mention(name):
    """Build a Band mention object {id, name, handle} for a role from env."""
    return {"id": os.environ[f"{name}_AGENT_ID"],
            "name": name.title().replace("_", " "),
            "handle": handle_for(name).lstrip("@")}


def _poisoned_handoff():
    """A dev stand-in for the finance crew's approved handoff, with the payee
    account swapped to a known mule account (BEC). Re-derivable as fraudulent:
    vendor V-204's account on file is 70814592, not 99887766."""
    rec = build_record(
        invoice_id="INV-2026-04871", vendor_id="V-204",
        completed_stages=["intake", "matched", "limit_checked", "approved"],
        actor_role="approver", action="handoff",
        payee_value="99887766", payee_origin="invoice_document",
        amount_value=5013, amount_origin="purchase_order",
        action_cause="policy_and_po",
    )
    rec["_dev_standin"] = True  # clearly labelled: not a real third-party message
    return rec


async def main():
    warden = BandClient(os.environ["WARDEN_API_KEY"])      # Warden owns the room
    approver = BandClient(os.environ["APPROVER_API_KEY"])  # posts the handoff

    # 1. Warden opens the room and seats everyone EXCEPT Threat-Intel.
    chat = warden.create_chat()
    chat_id = (chat.get("data") or chat).get("id")
    print(f"\nWarden opened room {chat_id}")
    for role in ("INTAKE", "APPROVER", "INVESTIGATOR", "ENFORCER"):
        warden.add_participant(chat_id, os.environ[f"{role}_AGENT_ID"])
        print(f"  seated {handle_for(role)}")
    print(f"  (Threat-Intel {handle_for('THREAT_INTEL')} is NOT in the room — "
          f"the Investigator will recruit it live)\n")

    # 2. Start the live crew (Warden, Investigator, Enforcer, Threat-Intel).
    from warden.warden_agent import build_warden
    from agents.investigator import build_investigator
    from warden.enforcer_agent import build_enforcer
    from agents.threat_intel import build_threat_intel

    agents = {
        "warden": build_warden(),
        "investigator": build_investigator(),
        "enforcer": build_enforcer(),
        "threat-intel": build_threat_intel(),
    }
    tasks = [asyncio.create_task(a.run()) for a in agents.values()]
    print("Connecting the crew to Band... (sockets warming up)")
    await asyncio.sleep(10)

    # 3. The poisoned approved handoff lands, @mentioning Warden.
    rec = _poisoned_handoff()
    print(">>> Approver hands off the APPROVED invoice (payee secretly swapped) "
          "and tags Warden.\n")
    approver.send_message(
        chat_id,
        record_lib.to_message(
            rec, f"@{handle_for('WARDEN').lstrip('@')} approved, ready to pay."),
        mentions=[_mention("WARDEN")],
    )

    # 4. Let Warden -> Investigator -> recruit Threat-Intel -> Enforcer play out.
    print(f"Watching the live chain for {SETTLE_SECONDS}s "
          f"(agent logs print above)...\n")
    await asyncio.sleep(SETTLE_SECONDS)

    # 5. Stop the crew and check what actually happened on the platform.
    for a in agents.values():
        try:
            await a.stop()
        except Exception:
            pass
    for t in tasks:
        t.cancel()

    parts = warden.list_participants(chat_id)
    rows = parts.get("data", parts) if isinstance(parts, dict) else parts
    handles = {(_norm_handle(p)) for p in rows} if isinstance(rows, list) else set()
    ti = handle_for("THREAT_INTEL").lstrip("@")
    intake = handle_for("INTAKE").lstrip("@")
    recruited = ti in handles
    contained = intake not in handles

    print("\n================  SCORECARD  ================")
    print(f"Room: {chat_id}")
    print(f"Threat-Intel recruited LIVE into the room?  {'YES' if recruited else 'NO'}")
    print(f"Compromised agent (Intake) ejected?         {'YES' if contained else 'NO'}")
    print(f"Final room members: {sorted(handles) if handles else '(could not read)'}")
    print("============================================\n")
    return 0 if (recruited and contained) else 1


def _norm_handle(p):
    h = (p.get("handle") or p.get("name") or "") if isinstance(p, dict) else ""
    return h.lstrip("@")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
