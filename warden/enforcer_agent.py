"""Enforcer: the hands. NO LLM.

Called by the Investigator with a structured verdict. If the verdict is
"compromised", the Enforcer:
  1. removes the compromised agent from the room (containment),
  2. freezes the payment and writes an incident record (an audit event),
  3. escalates to a human for final sign-off.

We learned in Phase A that any member can remove another member (only the room
OWNER is protected), so the Enforcer - a normal member - can eject Intake itself.
"""

import os
import json
import re

from band import Agent
from band.core.simple_adapter import SimpleAdapter

from agents.identity import handle_for, SLUGS

_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _handle_to_id():
    """handle -> agent_id for every role we have an id for. Built from identity +
    env so the Enforcer can resolve who to remove regardless of which developer
    registered the agents."""
    mapping = {}
    for name in SLUGS:
        aid = os.getenv(f"{name}_AGENT_ID")
        if aid:
            mapping[handle_for(name)] = aid
    return mapping


def extract_verdict(text: str):
    if not text:
        return None
    m = _JSON_FENCE.search(text)
    candidate = m.group(1) if m else None
    if candidate is None:
        s = text.find("{")
        if s == -1:
            return None
        depth = 0
        for i in range(s, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[s:i + 1]
                    break
    if not candidate:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


class EnforcerAdapter(SimpleAdapter):
    def __init__(self):
        super().__init__()
        self.warden_handle = handle_for("WARDEN")
        self.handle_to_id = _handle_to_id()

    async def on_message(self, msg, tools, history, participants_msg,
                         contacts_msg, *, is_session_bootstrap, room_id):
        content = getattr(msg, "content", None) or getattr(msg, "text", None) or ""
        verdict = extract_verdict(content)
        if verdict is None or "verdict" not in verdict:
            print("[Enforcer] message with no verdict; ignoring.")
            return

        inv_id = verdict.get("invoice_id", "?")
        if verdict.get("verdict") != "compromised":
            print(f"[Enforcer] verdict benign for {inv_id}; no action.")
            await tools.send_event(
                content=f"Enforcer: {inv_id} cleared as benign; no action taken.",
                message_type="thought", metadata=verdict,
            )
            return

        target_handle = (verdict.get("compromised_agent") or "").lstrip("@")
        target_id = self.handle_to_id.get(target_handle)
        print(f"[Enforcer] CONTAINING {inv_id}: removing {target_handle} ({target_id})")

        # 1. Remove the compromised agent.
        removed = False
        if target_id:
            try:
                await tools.remove_participant(target_id)
                removed = True
            except Exception as e:
                print(f"[Enforcer] removal failed: {e}")

        # 2. Freeze payment + incident record (audit event, no mention needed).
        await tools.send_event(
            content=(
                f"INCIDENT {inv_id}: payment FROZEN. Compromised agent "
                f"{target_handle} {'removed from room' if removed else 'removal FAILED'}. "
                f"Reason: {verdict.get('reason', 'n/a')}."
            ),
            message_type="error",
            metadata={"invoice_id": inv_id, "removed": removed, **verdict},
        )

        # 3. Escalate to a human for final sign-off.
        await tools.send_message(
            content=(
                f"@{self.warden_handle} incident on {inv_id} contained: {target_handle} "
                f"ejected, payment frozen. Awaiting human sign-off before any release."
            ),
            mentions=[self.warden_handle],
        )


def build_enforcer() -> Agent:
    return Agent.create(
        adapter=EnforcerAdapter(),
        agent_id=os.environ["ENFORCER_AGENT_ID"],
        api_key=os.environ["ENFORCER_API_KEY"],
        ws_url=os.getenv("THENVOI_WS_URL"),
        rest_url=os.getenv("THENVOI_REST_URL"),
    )


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build_enforcer().run())
