"""Approver: checks the limit, then approves. NO LLM.

When it sees the Matcher's handoff, it RE-DERIVES amount + payee from `sources/`,
enforces the spend limit, and emits the approved record (stages intake -> matched
-> limit_checked -> approved), handing off to the Payer (if present) + Warden.

Fail loud: an over-limit invoice is a real reject — error event, no approval.
"""

import os

from band import Agent
from band.core.simple_adapter import SimpleAdapter

from agents.identity import handle_for, agent_env
from warden import record
from warden import agents as logic
from warden.sources import Sources


class ApproverAdapter(SimpleAdapter):
    def __init__(self):
        super().__init__()
        self.sources = Sources.from_dir()
        self.warden_handle = handle_for("WARDEN")
        # Payer only exists once U4 registers it; mention it when configured.
        self.payer_handle = handle_for("PAYER") if os.getenv("PAYER_AGENT_ID") else None

    async def on_message(self, msg, tools, history, participants_msg,
                         contacts_msg, *, is_session_bootstrap, room_id):
        content = getattr(msg, "content", None) or getattr(msg, "text", None) or ""
        rec = record.normalize(record.extract(content))
        if not rec or rec.get("actor_role") != "matcher":
            return  # not my turn

        inv_id = rec.get("invoice_id")
        try:
            approved = logic.approver_handoff(
                {"invoice_id": inv_id, "vendor_id": rec.get("vendor_id")},
                self.sources,
            )
        except Exception as e:
            print(f"[Approver] reject {inv_id}: {e}")
            await tools.send_event(
                content=f"Approver rejects {inv_id}: {e}",
                message_type="error", metadata={"invoice_id": inv_id},
            )
            return

        mentions = [self.warden_handle]
        if self.payer_handle:
            mentions.insert(0, self.payer_handle)
        print(f"[Approver] approved {inv_id} -> handoff (mentions {mentions})")
        await tools.send_message(
            content=record.to_message(approved, f"Approved {inv_id}; under limit, matches PO."),
            mentions=mentions,
        )


def build_approver() -> Agent:
    aid, key = agent_env("APPROVER")
    return Agent.create(
        adapter=ApproverAdapter(), agent_id=aid, api_key=key,
        ws_url=os.getenv("THENVOI_WS_URL"), rest_url=os.getenv("THENVOI_REST_URL"),
    )


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build_approver().run())
