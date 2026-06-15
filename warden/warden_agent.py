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
from warden import paygate
from warden import record as record_lib
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
        self.payer_handle = handle_for("PAYER") if os.getenv("PAYER_AGENT_ID") else None

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
            await self._maybe_sign_off(record, inv_id, tools)
            return

        print(f"[Warden] FLAG: {inv_id} @ stage '{stage}' -> {violations}")
        # The suspect payee account, read from the record's facts (the value that
        # would actually be paid) — not any agent's self-report. The Investigator
        # hands this to Threat-Intel to screen.
        suspect_account = (
            (record.get("facts", {}) or {}).get("payee_account", {}) or {}
        ).get("value")
        await tools.send_event(
            content=f"Warden flag on {inv_id}: {', '.join(violations)}",
            message_type="error",
            metadata={"invoice_id": inv_id, "stage": stage, "violations": violations,
                      "suspect_account": suspect_account},
        )
        flag = {"invoice_id": inv_id, "stage": stage, "violations": violations,
                "suspect_account": suspect_account, "vendor_id": record.get("vendor_id")}
        await tools.send_message(
            content=(
                f"@{self.investigator_handle} possible compromise on invoice {inv_id} "
                f"at stage '{stage}'. Rule violations: {', '.join(violations)}. "
                f"Suspect payee account: {suspect_account}. Please trace the chain, "
                f"screen the account, and confirm.\n" + record_lib.to_message(flag)
            ),
            mentions=[self.investigator_handle],
        )

    async def _maybe_sign_off(self, rec, inv_id, tools):
        """On a clean 'approved' handoff, issue a signed sign-off to the Payer over
        the AUTHORITATIVE (re-derived) account — never an agent's claim. Only fires
        when a Payer is configured (PAYER_AGENT_ID)."""
        completed = rec.get("completed_stages", []) or []
        if not (self.payer_handle and "approved" in completed and "paid" not in completed):
            return
        vid = rec.get("vendor_id")
        on_file = self.sources.vendor_account(vid)
        po = self.sources.purchase_order(inv_id)
        if not on_file or not po:
            return
        amount = po.get("amount")
        stages = list(completed)
        token = paygate.sign(inv_id, on_file, amount, stages)
        signoff = {"warden_signoff": True, "invoice_id": inv_id, "vendor_id": vid,
                   "payee": on_file, "amount": amount, "stages": stages, "token": token}
        try:
            await tools.send_message(
                content=record_lib.to_message(signoff, f"Warden sign-off: {inv_id} clean through approved."),
                mentions=[self.payer_handle],
            )
        except Exception as e:
            # Payer not in this room (e.g. a stale message from an old room). The
            # sign-off only matters where a Payer is seated; elsewhere just skip.
            print(f"[Warden] sign-off skipped for {inv_id}: {e}")


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
