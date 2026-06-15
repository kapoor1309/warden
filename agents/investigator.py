"""Investigator: the agent that calls for backup, then rules.

When Warden flags a suspicious payee account, the Investigator does NOT decide
alone. It RECRUITS the Threat-Intel specialist live into the room
(tools.add_participant), hands it the exact account to screen, waits for the
finding, and only then rules "compromised" to the Enforcer. That live "call for
backup" is the crew behaviour the Band-of-Agents track is about.

Why no LLM in the control flow: the project rule is that security ACTIONS are
deterministic — never dependent on a model guessing the right tool call or the
right format (that flakiness already bit us once). So the recruit-and-rule steps
are plain code. The model is used ONLY to narrate the reasoning into a
professional sentence (the detective's "voice"), never to make the call.

It is a two-message state machine, driven by what arrives:
  - a Warden FLAG (has `violations` + `suspect_account`)  -> recruit + ask.
  - a Threat-Intel FINDING (has `threat_intel: true`)      -> rule to Enforcer.
"""

import os

import httpx

from band import Agent
from band.core.simple_adapter import SimpleAdapter

from agents.identity import handle_for, agent_env
from warden import record as record_lib


def _narrate(base_reason: str, finding: dict) -> str:
    """Turn the deterministic reason into one professional sentence. Best-effort:
    any error (no key, timeout, bad response) falls back to the base reason, so
    narration can never break the verdict."""
    key = os.getenv("AIML_API_KEY") or os.getenv("FEATHERLESS_API_KEY")
    if not key:
        return base_reason
    aiml = bool(os.getenv("AIML_API_KEY"))
    base_url = (os.getenv("AIML_BASE_URL", "https://api.aimlapi.com/v1") if aiml
                else os.getenv("FEATHERLESS_BASE_URL", "https://api.featherless.ai/v1"))
    model = (os.getenv("AIML_MODEL", "gpt-4o-mini") if aiml
             else os.getenv("FEATHERLESS_MODEL", "Qwen/Qwen2.5-7B-Instruct"))
    try:
        prompt = ("You are a fraud investigator. In ONE sentence, state your finding "
                  "professionally. Do NOT change the verdict (it is compromised); just "
                  f"explain why.\n\nFACTS: {base_reason}\nSCREENING: {finding}")
        r = httpx.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0, "max_tokens": 90},
            timeout=40.0,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return base_reason


class InvestigatorAdapter(SimpleAdapter):
    def __init__(self):
        super().__init__()
        self.ti_handle = handle_for("THREAT_INTEL")
        self.ti_id = agent_env("THREAT_INTEL")[0]
        self.enforcer_handle = handle_for("ENFORCER")
        self.intake_handle = handle_for("INTAKE")
        self.use_llm = bool(os.getenv("AIML_API_KEY") or os.getenv("FEATHERLESS_API_KEY"))
        self.flags = {}  # invoice_id -> the Warden flag we are still working

    async def on_message(self, msg, tools, history, participants_msg,
                         contacts_msg, *, is_session_bootstrap, room_id):
        content = getattr(msg, "content", None) or getattr(msg, "text", None) or ""
        rec = record_lib.extract(content)
        if not isinstance(rec, dict):
            return

        if rec.get("threat_intel"):          # Threat-Intel answered -> rule.
            await self._rule(rec, tools)
        elif rec.get("violations"):          # Warden flagged -> recruit.
            await self._recruit(rec, tools)

    async def _recruit(self, flag, tools):
        inv = flag.get("invoice_id")
        suspect = flag.get("suspect_account")
        self.flags[inv] = flag
        # Bring the specialist into the room (no-op if already present).
        try:
            res = await tools.add_participant(self.ti_id)
            print(f"[Investigator] recruited Threat-Intel ({res.get('status')})")
        except Exception as e:
            print(f"[Investigator] add_participant note: {e}")
        # Ask it to screen the EXACT account, in a structured block it can always read.
        ask = {"screen_account": suspect, "invoice_id": inv}
        await tools.send_message(
            content=(f"@{self.ti_handle} I need a fraud screen on the suspect payee "
                     f"account for invoice {inv} before I rule.\n"
                     + record_lib.to_message(ask)),
            mentions=[self.ti_handle],
        )
        print(f"[Investigator] asked Threat-Intel to screen {suspect} for {inv}")

    async def _rule(self, finding, tools):
        inv = finding.get("invoice_id")
        flag = self.flags.get(inv, {})
        rules = ", ".join(flag.get("violations") or []) or "payee_not_on_file"
        account = finding.get("account")
        base = (f"Payee account {account} does not match the vendor record on file "
                f"(rule: {rules}). Threat-Intel screening: {finding.get('reason')} "
                f"(risk={finding.get('risk')}, source={finding.get('source')}).")
        reason = _narrate(base, finding) if self.use_llm else base
        verdict = {"verdict": "compromised", "invoice_id": inv,
                   "compromised_agent": self.intake_handle.lstrip("@"),
                   "reason": reason}
        await tools.send_message(
            content=(f"@{self.enforcer_handle} investigation complete on {inv}: "
                     f"COMPROMISED.\n" + record_lib.to_message(verdict)),
            mentions=[self.enforcer_handle],
        )
        print(f"[Investigator] ruled COMPROMISED on {inv}; handed to Enforcer.")


def build_investigator() -> Agent:
    aid, key = agent_env("INVESTIGATOR")
    return Agent.create(
        adapter=InvestigatorAdapter(), agent_id=aid, api_key=key,
        ws_url=os.getenv("THENVOI_WS_URL"), rest_url=os.getenv("THENVOI_REST_URL"),
    )


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build_investigator().run())
