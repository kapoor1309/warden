# Warden

A security crew that lives inside a [Band](https://band.ai) chat room, watches a
multi-agent invoice-approval workflow, catches a **compromised-but-in-policy**
agent hijacked by a poisoned document, traces it, and ejects it — before any
money moves.

Use case: accounts-payable / business-email-compromise fraud.
Hackathon: Band of Agents — Track 3 (Regulated & High-Stakes).

## The idea in one line

Everyone else secures *one agent's* input and output. Warden secures the
**teamwork between agents** — the open gap. It never reads invoice text as
instructions; it only inspects the *shape and origin* of what each agent did,
and re-derives the facts that matter from the company's own records.

## The cast (core six first, showcase later)

| Agent | Framework | Job |
|-------|-----------|-----|
| Intake | LangGraph | Reads the invoice, extracts fields (the hijackable one) |
| Matcher | CrewAI | Checks invoice vs purchase order + vendor record |
| Approver | CrewAI | Approves if it matches and is under the limit |
| **Warden** | Claude SDK | Runs the 5-rule engine on every handoff + the pay gate |
| **Investigator** | Claude SDK | Traces a flag back to where the poison entered |
| **Enforcer** | Claude SDK | Removes the hijacked agent, freezes the payment, pings a human |
| _Payer_ | _showcase_ | The real wire, gated behind Warden's sign-off |
| _Threat-Intel_ | _showcase_ | Recruited live to check if the new account is a known mule |
| _Reporter_ | _showcase_ | Drafts the incident / audit record |

## Warden's five rules (the behaviour contract)

1. **Right order, nothing skipped** — intake → matched → limit_checked → approved → paid.
2. **Important values come from records, not the document** — amount must match the PO.
3. **Money goes only where it is supposed to** — payee must equal the account on file.
4. **Actions happen for the right reason** — never because the document said "approve urgently".
5. **Everyone stays in their lane** — Intake extracts; it never approves or changes the payee.

Implemented in `warden/invariants.py` as a deterministic function. **No LLM, no
catalogue of known attacks.** Iron rule: catching a brand-new attack must never
require new code here.

## Provenance record (what every handoff carries, and what Warden parses)

```json
{
  "invoice_id": "INV-1042",
  "vendor_id": "V-77",
  "stage": "matched",
  "completed_stages": ["intake", "matched"],
  "actor_role": "matcher",
  "action": "handoff",
  "facts": {
    "amount": {"value": 5000, "claimed_source": "purchase_order"},
    "payee_account": {"value": "ACC-001", "claimed_source": "vendor_record"}
  },
  "action_cause": "policy_and_po"
}
```

Warden does **not** trust `claimed_source`. It re-reads `sources/` and compares.

## Verified Band facts (SDK introspected + Phase A live run)

- Install: `pip install band-sdk` (1.0.0 on build day). Import is **`from band import Agent`**
  — the earlier `from thenvoi import Agent` was wrong (`import thenvoi` fails; the
  top-level module is `band`).
- `Agent.create(adapter=, agent_id=, api_key=, ws_url=, rest_url=,
  on_participant_added=, on_participant_removed=)`; run with `await agent.run()`.
- Adapters: subclass `band.agent.SimpleAdapter` (no-LLM — the U1 spike uses this),
  or a framework adapter under `band.integrations` (confirm exact LangGraph/CrewAI/
  Anthropic adapter names when wiring the live crew).
- **Join/leave is a first-class callback** (`on_participant_added` /
  `on_participant_removed`) — not polling. Live firing still pending Band keys (U1).
- Native tools are `band_*`: `band_create_chatroom`, `band_add_participant`,
  `band_get_participants`, `band_remove_participant`, `band_send_message`,
  `band_send_event`, `band_lookup_peers` (NOT `thenvoi_*`).
- REST (auth header `X-API-Key`, verified Phase A): `GET /agent/me`, `POST /agent/chats`,
  `POST|GET /agent/chats/{id}/participants`, `DELETE /agent/chats/{id}/participants/{pid}`,
  `POST /agent/chats/{id}/messages`, `POST /agent/chats/{id}/events`,
  `GET /agent/chats/{id}/context` (mention-scoped view the design relies on).
- Free tier: ≤10 agents, ≤50 rooms, 24h retention.

## Running the offline core (no keys needed)

```
pip install pytest
python -m pytest tests/ -v
```

This proves the brain works before any Band connection exists.

## License

MIT.
