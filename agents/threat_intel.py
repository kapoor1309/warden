"""Threat-Intel: the specialist the Investigator recruits LIVE into the room.

It starts OUTSIDE the invoice room. When Warden flags a suspicious payee, the
Investigator pulls this agent in (band_add_participant) and @mentions it with the
account to screen. That live recruitment — an agent deciding it needs help and
bringing another agent into the conversation — is the heart of the "Band of
Agents" idea.

NO LLM in the decision: the verdict is a deterministic watchlist lookup
(warden/threat_intel.check_account), consistent with the rule that security
calls never depend on a model. Featherless (an open model) is used ONLY to
narrate the finding into a professional risk note — the specialist's "voice",
never its judgement.
"""

import os
import re

from band import Agent
from band.core.simple_adapter import SimpleAdapter

from agents.identity import handle_for, agent_env
from warden import record as record_lib
from warden import threat_intel as ti_lib

# Account shapes we screen: ACC-xxxx, a 6+ digit account number, or an IBAN-like
# token (2 letters, 2 digits, then alnum/spaces). Used only as a fallback when the
# asking agent did not hand us a structured {"screen_account": ...} block.
_ACCOUNT_RE = re.compile(
    r"(ACC-\w+|[A-Z]{2}\d{2}[A-Z0-9 ]{8,}|\b\d{6,}\b)"
)


def _account_from(content: str):
    """Prefer a structured screen_account field; fall back to a regex sniff."""
    rec = record_lib.extract(content)
    if isinstance(rec, dict) and rec.get("screen_account"):
        return str(rec["screen_account"]).strip(), rec.get("invoice_id")
    m = _ACCOUNT_RE.search(content or "")
    inv = rec.get("invoice_id") if isinstance(rec, dict) else None
    return (m.group(1).strip() if m else None), inv


class ThreatIntelAdapter(SimpleAdapter):
    def __init__(self):
        super().__init__()
        # Reply to whoever runs the investigation. Only the Investigator recruits us.
        self.investigator_handle = handle_for("INVESTIGATOR")
        self.use_llm = bool(os.getenv("FEATHERLESS_API_KEY"))

    async def on_message(self, msg, tools, history, participants_msg,
                         contacts_msg, *, is_session_bootstrap, room_id):
        content = getattr(msg, "content", None) or getattr(msg, "text", None) or ""
        account, inv_id = _account_from(content)
        if not account:
            print("[Threat-Intel] mentioned but no account to screen; ignoring.")
            return

        finding = ti_lib.check_account(account)        # deterministic verdict
        note = ti_lib.narrate(finding, use_llm=self.use_llm)  # LLM only phrases it
        print(f"[Threat-Intel] screened {account}: known_fraud={finding['known_fraud']} "
              f"risk={finding['risk']}")

        payload = {"threat_intel": True, "invoice_id": inv_id, **finding}
        await tools.send_message(
            content=(
                f"@{self.investigator_handle} screening complete for account "
                f"{account}. {note}\n" + record_lib.to_message(payload)
            ),
            mentions=[self.investigator_handle],
        )


def build_threat_intel() -> Agent:
    aid, key = agent_env("THREAT_INTEL")
    return Agent.create(
        adapter=ThreatIntelAdapter(), agent_id=aid, api_key=key,
        ws_url=os.getenv("THENVOI_WS_URL"), rest_url=os.getenv("THENVOI_REST_URL"),
    )


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build_threat_intel().run())
