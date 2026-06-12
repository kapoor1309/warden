"""Phase B, U1: prove the two runtime facts Phase A could not test.

Phase A proved the control plane over REST (create room, add/remove/list
participants). It could NOT prove, without a live listening agent:

  R1. Does an @mention actually PUSH to a running agent over the WebSocket?
  R2. Does a participant join/leave PUSH to a running agent (no mention needed)?

This spike answers both with the smallest possible setup and writes the verdict
to PHASE_B_FINDINGS.md, in the same plain-language style as PHASE_A_FINDINGS.md.

It is deliberately throwaway. No business logic, no invariants — just plumbing.

SDK facts confirmed by introspection on build day (band-sdk 1.0.0):
  - Import is `from band import Agent` (NOT `from thenvoi import Agent`).
  - Subclass `band.agent.SimpleAdapter` and override `on_message(...)`.
  - Join/leave is a first-class callback: `Agent.create(...,
    on_participant_added=cb, on_participant_removed=cb)`. No polling required.
  - `await agent.run()` runs the listener until cancelled.

LIVE RUN IS PENDING BAND KEYS. The agents must be registered in the Band
dashboard first (only Yash can do that); paste WARDEN_/INTAKE_/MATCHER_ keys +
agent ids into .env. With keys absent this script FAILS LOUD and tells you so —
it does not pretend to pass.

Run from repo root:  python scripts/spike_mention.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from band import Agent
from band.agent import SimpleAdapter
from band_client import BandClient

load_dotenv()

WS_URL = os.getenv("THENVOI_WS_URL", "wss://app.band.ai/api/v1/socket/websocket")
REST_URL = os.getenv("THENVOI_REST_URL", "https://app.band.ai/").rstrip("/")

# Roles for the spike, mapped onto the agents we already register in Band.
LISTENER = "WARDEN"    # runs the live agent; also the room owner
SENDER = "INTAKE"      # posts the @mention to the listener
THIRD = "MATCHER"      # gets added then removed to trigger join/leave


def _require(name):
    key = os.getenv(f"{name}_API_KEY")
    aid = os.getenv(f"{name}_AGENT_ID")
    if not key or not aid:
        raise SystemExit(
            f"FAIL LOUD: {name}_API_KEY / {name}_AGENT_ID missing from .env.\n"
            f"Register the agents in the Band dashboard, paste keys + ids into "
            f".env, then re-run. This spike will not fake a pass."
        )
    return key, aid


# What the listener actually observed, collected from the live callbacks.
SEEN = {"mentions": [], "joins": [], "leaves": []}


class LoggerAdapter(SimpleAdapter):
    """Logs every message the listener receives. Receiving a message here IS the
    proof that @mention push works — the SDK only delivers mentioned messages."""

    async def on_message(self, msg, tools, history, participants_msg,
                         contacts_msg, *, is_session_bootstrap, room_id):
        try:
            text = msg.format_for_llm()
        except Exception:
            text = repr(msg)
        if is_session_bootstrap:
            print(f"[listener] session bootstrap in room {room_id}")
            return
        print(f"[listener] MESSAGE in {room_id}: {text}")
        SEEN["mentions"].append(text)

    async def on_started(self, agent_name, agent_description):
        print(f"[listener] started as {agent_name}")


async def _on_added(*args, **kwargs):
    print(f"[listener] PARTICIPANT ADDED  args={args} kwargs={kwargs}")
    SEEN["joins"].append({"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in kwargs.items()}})


async def _on_removed(*args, **kwargs):
    print(f"[listener] PARTICIPANT REMOVED  args={args} kwargs={kwargs}")
    SEEN["leaves"].append({"args": [str(a) for a in args], "kwargs": {k: str(v) for k, v in kwargs.items()}})


async def main():
    listener_key, listener_id = _require(LISTENER)
    sender_key, sender_id = _require(SENDER)
    third_key, third_id = _require(THIRD)

    # 1. Start the listener agent running (subscribes to its rooms over the WS).
    listener = Agent.create(
        adapter=LoggerAdapter(),
        agent_id=listener_id,
        api_key=listener_key,
        ws_url=WS_URL,
        rest_url=REST_URL,
        on_participant_added=_on_added,
        on_participant_removed=_on_removed,
    )
    run_task = asyncio.create_task(listener.run())
    await asyncio.sleep(3)  # let the WS connect + subscribe

    # 2. Sender (REST) creates a room, adds the listener, @mentions it.
    sender = BandClient(sender_key)
    room = sender.create_chat()
    chat_id = room.get("data", room).get("id") or room.get("id")
    print(f"[sender] room {chat_id}")
    sender.add_participant(chat_id, listener_id)
    await asyncio.sleep(2)  # listener should receive a join for itself

    sender.send_message(
        chat_id,
        content=f"@{LISTENER.lower()} ping from the U1 spike — did this reach you?",
        mentions=[{"participant_id": listener_id}],
    )
    await asyncio.sleep(4)  # R1: did the mention push to the listener?

    # 3. Add then remove a third participant. R2: do join/leave push?
    sender.add_participant(chat_id, third_id)
    await asyncio.sleep(3)
    sender.remove_participant(chat_id, third_id)
    await asyncio.sleep(3)

    run_task.cancel()
    try:
        await run_task
    except asyncio.CancelledError:
        pass

    _write_findings(chat_id)


def _write_findings(chat_id):
    mention_ok = bool(SEEN["mentions"])
    join_ok = bool(SEEN["joins"])
    leave_ok = bool(SEEN["leaves"])
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PHASE_B_FINDINGS.md")
    lines = [
        "# Phase B findings — the live runtime test (plain language)\n",
        "\n",
        "Phase A proved the REST control plane. This proves the two things that\n",
        "needed a *running* agent: does an @mention push to it, and does a\n",
        "join/leave push to it.\n\n",
        "## Quick scorecard\n\n",
        f"- Did a live @mention reach the running listener? **{'YES' if mention_ok else 'NO'}**.\n",
        f"- Did a participant JOIN push to the listener? **{'YES' if join_ok else 'NO'}**.\n",
        f"- Did a participant LEAVE push to the listener? **{'YES' if leave_ok else 'NO'}**.\n",
        "\n## What this means\n\n",
    ]
    if mention_ok:
        lines.append("- Mention delivery works. Warden can be tagged on every handoff and will\n  receive it live. The design's core assumption holds.\n")
    else:
        lines.append("- **Mention did NOT arrive.** Stop and debug the mention payload shape /\n  subscription before building the crew — Warden cannot watch handoffs without it.\n")
    if join_ok and leave_ok:
        lines.append("- Join/leave push works. Warden's 'watch for sneaky ejection' backstop is a\n  live callback, no polling needed.\n")
    else:
        lines.append("- **Join/leave push did NOT fully arrive.** Fallback: Warden re-lists\n  participants each cycle (polling). Record this; do not assume the push.\n")
    lines.append(f"\nRoom used: {chat_id}\n")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"\n>>> Findings written to {path}")
    # Fail loud in CI/script terms if the core fact (mention) did not hold.
    sys.exit(0 if mention_ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
