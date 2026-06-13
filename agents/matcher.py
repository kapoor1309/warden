"""Matcher: checks the invoice against the PO + vendor record. NO LLM.

Only Intake reads the untrusted document, so only Intake can be hijacked. The
Matcher is deterministic: when it sees Intake's handoff, it RE-DERIVES the payee
and amount straight from `sources/` (never the invoice's claim), builds the
matched record, and hands off to the Approver + Warden.

Fail loud: an unknown vendor or missing purchase order is a real reject — it posts
an error event and does NOT hand off, rather than passing something through.
"""

import os

from band import Agent
from band.core.simple_adapter import SimpleAdapter

from agents.identity import handle_for, agent_env
from warden import record
from warden import agents as logic
from warden.sources import Sources


class MatcherAdapter(SimpleAdapter):
    def __init__(self):
        super().__init__()
        self.sources = Sources.from_dir()
        self.approver_handle = handle_for("APPROVER")
        self.warden_handle = handle_for("WARDEN")

    async def on_message(self, msg, tools, history, participants_msg,
                         contacts_msg, *, is_session_bootstrap, room_id):
        content = getattr(msg, "content", None) or getattr(msg, "text", None) or ""
        rec = record.normalize(record.extract(content))
        if not rec or rec.get("actor_role") != "intake":
            return  # not my turn

        inv_id = rec.get("invoice_id")
        try:
            matched = logic.matcher_handoff(
                {"invoice_id": inv_id, "vendor_id": rec.get("vendor_id")},
                self.sources,
            )
        except Exception as e:
            print(f"[Matcher] cannot match {inv_id}: {e}")
            await tools.send_event(
                content=f"Matcher cannot process {inv_id}: {e}",
                message_type="error", metadata={"invoice_id": inv_id},
            )
            return

        print(f"[Matcher] matched {inv_id} -> handoff to Approver")
        await tools.send_message(
            content=record.to_message(matched, f"Matched {inv_id} against PO + vendor record."),
            mentions=[self.approver_handle, self.warden_handle],
        )


def build_matcher() -> Agent:
    aid, key = agent_env("MATCHER")
    return Agent.create(
        adapter=MatcherAdapter(), agent_id=aid, api_key=key,
        ws_url=os.getenv("THENVOI_WS_URL"), rest_url=os.getenv("THENVOI_REST_URL"),
    )


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build_matcher().run())
