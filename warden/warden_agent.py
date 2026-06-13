"""Warden: the guard, alive inside the room. NO LLM.

It is a SimpleAdapter: every time it is mentioned on a handoff, on_message runs.
It pulls the structured provenance record out of the message, runs the
deterministic 5-rule engine (invariants.check), and:
  - stays quiet + logs a clean audit event   if there are no violations, or
  - @mentions the Investigator with the violation list   if something is wrong.

Warden never treats the message text as instructions. It only parses fields and
re-derives the critical facts from the authoritative records. That is what makes
"just inject Warden too" fail.
"""

import os
import json
import re

from band import Agent
from band.core.simple_adapter import SimpleAdapter

from agents.identity import handle_for
from warden import invariants
from warden.sources import Sources

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def extract_record(text: str):
    """Pull the first JSON object out of a message. Returns a dict or None.
    Tolerant: tries a ```json fence first, then the first balanced {...}."""
    if not text:
        return None
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else None
    if candidate is None:
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start:i + 1]
                    break
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


class WardenAdapter(SimpleAdapter):
    def __init__(self):
        super().__init__()
        self.sources = Sources.from_dir()
        self.investigator_handle = handle_for("INVESTIGATOR")

    async def on_message(self, msg, tools, history, participants_msg,
                         contacts_msg, *, is_session_bootstrap, room_id):
        content = getattr(msg, "content", None) or getattr(msg, "text", None) or ""
        record = extract_record(content)

        if record is None:
            # Not a structured handoff; nothing for the engine to judge.
            print(f"[Warden] message with no provenance record; ignoring.")
            return

        violations = invariants.check(record, self.sources)
        inv_id = record.get("invoice_id", "?")
        stage = record.get("stage", "?")

        if not violations:
            print(f"[Warden] CLEAN: {inv_id} @ stage '{stage}' passed all 5 rules.")
            # Audit trail (events do not require a mention).
            await tools.send_event(
                content=f"Warden sign-off: {inv_id} stage '{stage}' is clean.",
                message_type="thought",
                metadata={"invoice_id": inv_id, "stage": stage, "verdict": "clean"},
            )
            return

        print(f"[Warden] FLAG: {inv_id} @ stage '{stage}' -> {violations}")
        await tools.send_event(
            content=f"Warden flag on {inv_id}: {', '.join(violations)}",
            message_type="error",
            metadata={"invoice_id": inv_id, "stage": stage, "violations": violations},
        )
        await tools.send_message(
            content=(
                f"@{self.investigator_handle} possible compromise on invoice {inv_id} "
                f"at stage '{stage}'. Rule violations: {', '.join(violations)}. "
                f"Please trace the chain and confirm."
            ),
            mentions=[self.investigator_handle],
        )


async def _on_added(room_id, event):
    # Topology is not mention-scoped: every member sees joins/leaves. A hijacked
    # agent pulling in a helper to route around Warden shows up right here.
    p = getattr(event, "payload", None)
    who = getattr(p, "handle", None) or getattr(p, "name", None) or event
    print(f"[Warden] saw JOIN: {who}")


async def _on_removed(room_id, event):
    p = getattr(event, "payload", None)
    who = getattr(p, "handle", None) or getattr(p, "name", None) or event
    print(f"[Warden] saw LEAVE: {who}")


def build_warden() -> Agent:
    return Agent.create(
        adapter=WardenAdapter(),
        agent_id=os.environ["WARDEN_AGENT_ID"],
        api_key=os.environ["WARDEN_API_KEY"],
        ws_url=os.getenv("THENVOI_WS_URL"),
        rest_url=os.getenv("THENVOI_REST_URL"),
        on_participant_added=_on_added,
        on_participant_removed=_on_removed,
    )


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build_warden().run())
