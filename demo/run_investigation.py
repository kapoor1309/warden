"""Run the full security loop live on a POISONED invoice.

Flow we expect to see:
  1. Poisoned invoice (carries a fraudulent "new" bank account) is dropped in,
     mentioning Intake.
  2. Intake reads it and hands off - faithfully carrying the bad account ACC-99999.
  3. Warden re-derives the real account from records, sees the mismatch, FLAGS,
     and @mentions the Investigator.
  4. Investigator reasons over the chain, decides it is a real compromise, and
     hands a structured verdict to the Enforcer.
  5. Enforcer removes Intake, freezes the payment, and escalates to a human.

Run:  python demo/run_investigation.py
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from band_client import BandClient
from agents.identity import handle_for
from attacks import build_invoice, benchmarks, judge_input
from agents.intake import build_intake
from agents.matcher import build_matcher
from agents.approver import build_approver
from agents.investigator import build_investigator
from warden.warden_agent import build_warden
from warden.enforcer_agent import build_enforcer

WARDEN_KEY = os.getenv("WARDEN_API_KEY")
INTAKE_ID = os.getenv("INTAKE_AGENT_ID")
INTAKE_HANDLE = handle_for("INTAKE")
PARTICIPANTS = ["INTAKE", "MATCHER", "APPROVER", "INVESTIGATOR", "ENFORCER"]


def _select_attack():
    """Pick the attack. Default = a REAL AgentDojo banking injection. The graded
    attack is never self-authored (CLAUDE.md). Flags: --injecagent, --judge
    "<text>", --dev-standin (self-authored, not for grading)."""
    if "--dev-standin" in sys.argv:
        return build_invoice.dev_standin(), "DEV STAND-IN (self-authored, not for grading)"
    if "--judge" in sys.argv:
        return build_invoice.embed(judge_input.get_judge_attack()), "judge-supplied"
    src = "injecagent" if "--injecagent" in sys.argv else "agentdojo-banking"
    p = benchmarks.random_payload(src)
    return build_invoice.embed(p["text"]), f"{p['source']} [{p['ref']}]"


async def main():
    warden_rest = BandClient(WARDEN_KEY)

    chat = warden_rest.create_chat()
    chat_id = chat.get("data", chat).get("id")
    print(f"Room created by Warden: {chat_id}")
    for name in PARTICIPANTS:
        warden_rest.add_participant(chat_id, os.getenv(f"{name}_AGENT_ID"))
    print(f"Added participants: {', '.join(PARTICIPANTS)}")

    warden = build_warden()
    intake = build_intake()
    matcher = build_matcher()
    approver = build_approver()
    investigator = build_investigator()
    enforcer = build_enforcer()
    agents = [warden, intake, matcher, approver, investigator, enforcer]
    tasks = [asyncio.create_task(a.run()) for a in agents]
    print("Full crew connecting...")
    await asyncio.sleep(12)

    attack_doc, attack_src = _select_attack()
    print(f"\n>>> Dropping a POISONED invoice (attack source: {attack_src})\n")
    warden_rest.send_message(
        chat_id,
        f"@{INTAKE_HANDLE}\n{attack_doc}",
        mentions=[{"id": INTAKE_ID, "name": "Invoice Intake", "handle": INTAKE_HANDLE}],
    )

    # Two LLM round trips (Intake hand-off, Investigator verdict) + actions.
    await asyncio.sleep(55)

    print("\n================ ROOM TRANSCRIPT ================")
    try:
        ctx = warden_rest.context(chat_id)
        items = ctx.get("data", ctx) if isinstance(ctx, dict) else ctx
        if isinstance(items, dict):
            items = items.get("messages", [])
        for m in items:
            who = (m.get("sender") or {}).get("handle") or m.get("sender_handle") or m.get("author") or "?"
            txt = m.get("content") or m.get("text") or ""
            print(f"\n[{who}]\n{txt}")
    except Exception as e:
        print(f"(could not fetch transcript: {e})")

    print("\n================ FINAL ROOM MEMBERS =============")
    try:
        parts = warden_rest.list_participants(chat_id)
        rows = parts.get("data", parts) if isinstance(parts, dict) else parts
        for p in rows:
            print("   -", p.get("name") or p.get("handle") or p.get("id"))
        gone = not any((p.get("agent_id") or p.get("id")) == INTAKE_ID for p in rows)
        print(f"\n   Intake (the compromised agent) removed? {gone}")
    except Exception as e:
        print(f"(could not list participants: {e})")
    print("=================================================")

    for a in agents:
        try:
            await a.stop()
        except Exception:
            pass
    for t in tasks:
        t.cancel()


if __name__ == "__main__":
    asyncio.run(main())
