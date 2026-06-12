"""Run the core loop live: a clean invoice flows Intake -> Warden, Warden clears it.

Sequence:
  1. Warden (REST) creates a room and adds the agents as participants.
  2. We start Warden (no-LLM guard) and Intake (LLM) as live listeners.
  3. We drop a CLEAN invoice into the room, @mentioning Intake.
  4. Intake's LLM extracts the fields and hands off, @mentioning Matcher + Warden.
  5. Warden runs the 5-rule engine, finds nothing wrong, and signs off (clean).
  6. We print the whole conversation from the room.

Run:  python demo/run_core_loop.py
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from band_client import BandClient
from agents.intake import build_intake
from warden.warden_agent import build_warden

WARDEN_KEY = os.getenv("WARDEN_API_KEY")
INTAKE_ID = os.getenv("INTAKE_AGENT_ID")
INTAKE_HANDLE = (os.getenv("INTAKE_HANDLE") or "").lstrip("@")

# Every agent we want mentionable must be a participant of the room.
PARTICIPANTS = ["INTAKE", "MATCHER", "APPROVER", "INVESTIGATOR", "ENFORCER"]

CLEAN_INVOICE = (
    "New invoice received from the vendor portal:\n"
    "  Invoice number: INV-1042\n"
    "  Vendor: V-77 (Acme Supplies Ltd)\n"
    "  Amount due: 5000\n"
    "  Remit to bank account: ACC-001\n"
    "  Purchase order: PO-5501\n"
    "Please process this invoice."
)


async def main():
    warden_rest = BandClient(WARDEN_KEY)

    # 1. Warden creates the room (so it is owner) and adds the participants.
    chat = warden_rest.create_chat()
    chat_id = chat.get("data", chat).get("id")
    print(f"Room created by Warden: {chat_id}")
    for name in PARTICIPANTS:
        warden_rest.add_participant(chat_id, os.getenv(f"{name}_AGENT_ID"))
    print(f"Added participants: {', '.join(PARTICIPANTS)}")

    # 2. Start the live agents (each run() blocks, so run them as tasks).
    warden = build_warden()
    intake = build_intake()
    tasks = [asyncio.create_task(warden.run()), asyncio.create_task(intake.run())]
    print("Warden + Intake are connecting...")
    await asyncio.sleep(9)

    # 3. Drop the clean invoice in, mentioning Intake.
    print("\n>>> Dropping a CLEAN invoice into the room (mentioning Intake)\n")
    warden_rest.send_message(
        chat_id,
        f"@{INTAKE_HANDLE}\n{CLEAN_INVOICE}",
        mentions=[{"id": INTAKE_ID, "name": "Invoice Intake", "handle": INTAKE_HANDLE}],
    )

    # 4-5. Give Intake's LLM time to think + hand off, and Warden time to judge.
    await asyncio.sleep(35)

    # 6. Print the conversation.
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
    print("\n=================================================")

    for a in (warden, intake):
        try:
            await a.stop()
        except Exception:
            pass
    for t in tasks:
        t.cancel()
    print("\nDone. (Look above: Intake handed off, Warden signed off CLEAN.)")


if __name__ == "__main__":
    asyncio.run(main())
