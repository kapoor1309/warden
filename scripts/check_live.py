"""Phase A, tests 5-6 (the live ones): mention delivery + join/leave feed.

These are the two things we could NOT test with plain REST, because they need a
real agent connected to the websocket and listening.

What it does:
  1. Warden (REST) creates a room and adds the Intake agent.
  2. We start Intake as a REAL listening agent (no LLM - a tiny SimpleAdapter
     that just records what it receives). This is free; no model is called.
  3. Warden (REST) sends a message that @mentions Intake     -> proves MENTION delivery.
  4. Warden (REST) adds Approver to the room                 -> proves JOIN feed.
  5. Warden (REST) removes Approver                          -> proves LEAVE feed.
  6. We stop Intake and report what actually arrived.

Run:  python scripts/check_live.py
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from band import Agent
from band.core.simple_adapter import SimpleAdapter
from band_client import BandClient

load_dotenv()

INTAKE_ID = os.getenv("INTAKE_AGENT_ID")
INTAKE_KEY = os.getenv("INTAKE_API_KEY")
INTAKE_HANDLE = (os.getenv("INTAKE_HANDLE") or "").lstrip("@")
APPROVER_ID = os.getenv("APPROVER_AGENT_ID")
WARDEN_KEY = os.getenv("WARDEN_API_KEY")
WS_URL = os.getenv("THENVOI_WS_URL")
REST_URL = os.getenv("THENVOI_REST_URL")

# Everything the listener hears lands here.
EVENTS = []


class ListenerAdapter(SimpleAdapter):
    """A do-nothing brain that just records every message it is given."""

    async def on_message(self, msg, tools, history, participants_msg,
                         contacts_msg, *, is_session_bootstrap, room_id):
        content = getattr(msg, "content", None) or getattr(msg, "text", None) or repr(msg)
        EVENTS.append(("MESSAGE", content))
        print(f"   [listener] got a MESSAGE: {content!r}")
        # Reply so we can also see it land back in the room (bonus proof).
        try:
            await tools.send_message("ACK - Intake received your mention.")
        except Exception as e:
            print(f"   [listener] (reply failed, not important: {e})")


async def on_added(room_id, event):
    EVENTS.append(("JOINED", str(event)))
    print(f"   [listener] saw a participant JOIN: {event}")


async def on_removed(room_id, event):
    EVENTS.append(("LEFT", str(event)))
    print(f"   [listener] saw a participant LEAVE: {event}")


async def main():
    warden = BandClient(WARDEN_KEY)

    # 1. Warden creates a room and adds Intake.
    chat = warden.create_chat()
    chat_id = chat.get("data", chat).get("id")
    print(f"Warden created room {chat_id}")
    warden.add_participant(chat_id, INTAKE_ID)
    print("Added Intake to the room.")

    # 2. Start Intake as a real listening agent.
    adapter = ListenerAdapter()
    agent = Agent.create(
        adapter=adapter,
        agent_id=INTAKE_ID,
        api_key=INTAKE_KEY,
        ws_url=WS_URL,
        rest_url=REST_URL,
        on_participant_added=on_added,
        on_participant_removed=on_removed,
    )
    task = asyncio.create_task(agent.run())
    print("Starting Intake listener... (waiting for socket to connect)")
    await asyncio.sleep(8)

    # 3. MENTION delivery: Warden sends a message tagging Intake.
    print("\n>>> TEST: Warden sends a message that @mentions Intake")
    warden.send_message(
        chat_id,
        f"@{INTAKE_HANDLE} please reply ACK",
        mentions=[{"id": INTAKE_ID, "name": "Invoice Intake", "handle": INTAKE_HANDLE}],
    )
    await asyncio.sleep(8)

    # 4. JOIN feed: Warden adds Approver.
    print("\n>>> TEST: Warden adds Approver (should fire the JOIN feed)")
    warden.add_participant(chat_id, APPROVER_ID)
    await asyncio.sleep(6)

    # 5. LEAVE feed: Warden removes Approver.
    print("\n>>> TEST: Warden removes Approver (should fire the LEAVE feed)")
    warden.remove_participant(chat_id, APPROVER_ID)
    await asyncio.sleep(6)

    # 6. Stop and report.
    print("\nStopping Intake listener...")
    try:
        await agent.stop()
    except Exception:
        pass
    task.cancel()

    got_mention = any(k == "MESSAGE" for k, _ in EVENTS)
    got_join = any(k == "JOINED" for k, _ in EVENTS)
    got_leave = any(k == "LEFT" for k, _ in EVENTS)
    write_findings(chat_id, got_mention, got_join, got_leave)

    print(f"\nResult: mention={got_mention}, join={got_join}, leave={got_leave}")
    return 0 if (got_mention and got_join and got_leave) else 1


def write_findings(chat_id, got_mention, got_join, got_leave):
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "PHASE_A_LIVE_FINDINGS.md")
    yn = lambda b: "YES" if b else "NO - did not arrive"
    lines = [
        "# Phase A (live) findings - mention delivery + join/leave feed\n\n",
        "These are the two things that needed a real, connected agent (not just",
        " REST). We ran the Intake agent for real and poked it from Warden.\n\n",
        "## Scorecard\n\n",
        f"- Does a @mentioned message actually reach the agent? **{yn(got_mention)}**\n",
        f"- Does the agent get pinged when someone JOINS the room? **{yn(got_join)}**\n",
        f"- Does the agent get pinged when someone LEAVES the room? **{yn(got_leave)}**\n\n",
        "## What this means\n\n",
    ]
    if got_mention and got_join and got_leave:
        lines.append(
            "All three work. This is the rest of Warden's **eyes**: it will reliably "
            "receive every handoff that tags it, and it sees the room's membership "
            "change live (so a hijacked agent cannot quietly pull in a helper or slip "
            "away without Warden noticing). Phase A is fully complete - we can build "
            "the real crew now.\n\n"
        )
    else:
        lines.append(
            "At least one did not arrive. See the raw event log below; we may need a "
            "longer wait or a different subscription step.\n\n"
        )
    lines.append("## Raw events the listener recorded\n\n```\n")
    if EVENTS:
        lines.extend(f"{k}: {v}\n" for k, v in EVENTS)
    else:
        lines.append("(nothing recorded)\n")
    lines.append("```\n")
    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(lines))
    print(f">>> Findings written to {path}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
