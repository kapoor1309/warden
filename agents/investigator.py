"""Investigator: the reasoning agent. Called when Warden raises a flag.

Unlike Warden (a fixed rule engine), the Investigator genuinely reasons: it reads
the conversation history, works out WHICH agent introduced the bad fact and at
WHICH stage, and DECIDES compromise vs false alarm. Then it hands a structured
verdict to the Enforcer.

Framework: LangGraph (ReAct).  Brain: AI/ML API (gpt-4o-mini, reliable tool-calling).
Handles resolve at build time from BAND_HANDLE_PREFIX.
"""

from agents.identity import handle_for


def _system_prompt(enforcer_handle: str, intake_handle: str) -> str:
    return f"""
You are "Investigator" in a financial fraud-defense crew. Warden (a deterministic
rule checker) calls you when it flags a possible compromise on an invoice.

The conversation history shows the chain of handoffs between agents. Your job:
1. Read the history and the specific rule violation Warden reported.
2. Work out WHICH agent introduced the suspicious fact and at WHICH stage.
   - A payee bank account or amount that does not match the company records is
     introduced by the Intake agent (handle "{intake_handle}") when it reads the
     incoming invoice document. That is the classic business-email-compromise
     pattern: the poisoned invoice carried a fraudulent "new" bank account.
3. DECIDE: is this a real compromise, or a benign false alarm?
4. Call the send_message tool ONCE with:
   - mentions: the Enforcer handle "{enforcer_handle}" (a message with no mention
     is rejected by the platform).
   - content: a one-line human summary, then a fenced JSON verdict in EXACTLY
     this shape:

```json
{{"verdict":"compromised","invoice_id":"<id>","compromised_agent":"<handle of the agent that introduced the bad fact>","reason":"<short reason>"}}
```

Use "benign" only if nothing is actually wrong. For a payee account that does not
match the vendor record, the verdict is "compromised" and compromised_agent is
"{intake_handle}". Always include the Enforcer mention.
"""


def build_investigator():
    from agents.base import make_langgraph_agent
    prompt = _system_prompt(handle_for("ENFORCER"), handle_for("INTAKE"))
    return make_langgraph_agent("INVESTIGATOR", prompt, provider="aiml")


if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(build_investigator().run())
