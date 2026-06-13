"""Payer: the deterministic money gate. NO LLM.

Releases payment ONLY on Warden's signed sign-off, verified by warden/paygate.py,
and only to the account re-derived from sources/. It ignores everything else —
including the Approver's own handoff record. This is the keystone: money cannot
move on an agent's self-reported record, only on a Warden signature over the
authoritative facts.

LIVE use needs a 7th registered Band agent (PAYER_AGENT_ID/_API_KEY in .env).
Until then the gate is exercised by tests/test_paygate.py.
"""

import os

from band import Agent
from band.core.simple_adapter import SimpleAdapter

from agents.identity import agent_env
from warden import record, paygate
from warden.sources import Sources


class PayerAdapter(SimpleAdapter):
    def __init__(self):
        super().__init__()
        self.sources = Sources.from_dir()

    async def on_message(self, msg, tools, history, participants_msg,
                         contacts_msg, *, is_session_bootstrap, room_id):
        content = getattr(msg, "content", None) or getattr(msg, "text", None) or ""
        rec = record.extract(content)
        if not rec or not rec.get("warden_signoff"):
            return  # only Warden's signed sign-off can move money

        released, reason = paygate.release_decision(rec, self.sources)
        inv = rec.get("invoice_id")
        print(f"[Payer] {reason}")
        await tools.send_event(
            content=f"PAYMENT {reason} [{inv}]",
            message_type="action" if released else "error",
            metadata={"invoice_id": inv, "released": released, "reason": reason},
        )


def build_payer() -> Agent:
    aid, key = agent_env("PAYER")
    return Agent.create(
        adapter=PayerAdapter(), agent_id=aid, api_key=key,
        ws_url=os.getenv("THENVOI_WS_URL"), rest_url=os.getenv("THENVOI_REST_URL"),
    )


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build_payer().run())
