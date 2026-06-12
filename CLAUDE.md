# Warden — engineering guide

A security crew that lives inside a Band room, catches an **in-policy** agent that a
poisoned invoice hijacked, traces it, and ejects it before money moves. Track 3
(Regulated & High-Stakes). Two people: **Parshiv** = security crew + rules;
**Yash** = finance crew + injection harness + demo.

## How we build
- **Step by step. One thing at a time.** Smallest real thing that works → prove it →
  add the next. No big-bang. Don't add the whole cast at once.
- **Don't overengineer.** Solve the demo in front of us, not five hypothetical
  futures. Three plain lines beat a premature abstraction.
- **Fail loud, never silent.** No try/except-swallow. No default fallback dressed up
  as "production-ready." A crash with a clear error beats silent degradation that
  quietly poisons the result. A malformed record is an *explicit* violation, not a
  quiet pass.
- **Simple, effective, correct wins.** Looks simple, hard to do. If a junior can't
  read it in 30s, it's too clever.
- **Prove it before you trust it.** Every Band capability gets a tiny live test
  before we build on it (that's what Phase A was). Untested = unknown.

## Non-negotiable invariants (the soul of the project)
1. **Contract, not catalog.** `invariants.py` checks what *correct* looks like.
   Catching a brand-new attack must NEVER require new code there. If it does, you
   built a signature scanner — that's the wrong project.
2. **Warden never reads document text as instructions.** It inspects only the *shape
   and origin* of what an agent did. "Warden, ignore this" hidden in an invoice is
   evidence to examine, never an order to follow.
3. **Re-derive ground truth from `sources/`, never trust the agent's claim.** Payee
   and amount come from `vendor_master` / `purchase_orders`, compared against what
   actually happened. `claimed_source` is ignored on purpose.
4. **Read facts from the real gated action, not the worker's self-report.** THE crux:
   the payee Warden checks must be the account in the *actual payment request it
   gates* — never a field a (possibly hijacked) agent narrated. The moment we take
   the payee from the worker's story, the whole defense is theater.
5. **The pay gate is deterministic and unbypassable.** No payment without Warden's
   sign-off. The Payer is a hard gate, not an LLM that can be talked out of it. This
   is the keystone: if money can move without Warden, nothing else matters.
6. **Security decisions are deterministic — no LLM in the gate.** `invariants.py` has
   no LLM. LLMs narrate and triage (Investigator's write-up) only; they never make
   the allow/deny call.

## Threat model (state it, don't hide it)
- **In scope:** one compromised agent at a time. Warden is the room *owner* (members
  cannot eject the owner — verified) and is honest. The pay gate is honest.
- **Out of scope:** multiple colluding agents, a compromised Warden. Say this in the
  pitch — scoping is strength, not a gap.

## Proof discipline (bias-proof — this is half the score)
- We never author the attacks Warden is graded on. Payloads come from public
  benchmarks (AgentDojo, InjecAgent) or a judge typing one live.
- Always show both directions: a real attack **caught** AND a weird-but-honest
  invoice staying **quiet**. Not crying wolf is the whole game.

## Verified Band facts (Phase A, live-tested — see PHASE_A_FINDINGS.md)
- REST base `https://app.band.ai/api/v1`, auth header `X-API-Key`.
- Room `POST /agent/chats` body `{"chat":{}}`; add `POST .../participants` body
  `{"participant":{"participant_id":"<uuid>"}}`; list `GET .../participants`;
  remove `DELETE .../participants/{uuid}`.
- Creator is auto-owner. A member CAN remove another member; a member CANNOT remove
  the owner (403) → **Warden must create the room.**
- Agents see ONLY messages that @mention them (no free full-room view). Design around
  it: tag Warden on every handoff + gate the payment behind Warden + watch join/leave.
- Human API is enterprise-only → don't build human-in-loop on it; use the Band web UI
  (the human owner sees everything) or a mention to a human.
- Free tier: ≤10 agents, ≤50 rooms, 24h retention.
- **STILL UNPROVEN** (Phase B, needs a live LLM agent): does an @mention actually
  push to a listening agent over WebSocket, and does a live join/leave push arrive?
  Prove both before building the full crew.

## Model routing
- Finance crew (Intake/Matcher/Approver) → **AI/ML API** (OpenAI-compatible,
  `OPENAI_BASE_URL=https://api.aimlapi.com/v1`).
- Warden / Investigator reasoning → open model via **Featherless** (partner prize).
  Decision logic stays deterministic; Featherless only narrates.

## Run
- Offline brain (no keys): `python3 -m pytest tests/ -q` → 11 pass.
- Connection check: `python scripts/check_connection.py`.
- Room / removal check: `python scripts/check_room.py`.
