---
title: "feat: Phase B — prove the live agent loop + finance-crew happy path"
status: active
date: 2026-06-13
type: feat
depth: lightweight
---

# feat: Phase B — prove the live agent loop + finance-crew happy path

## Summary

Phase A proved the **control plane** (rooms, participant add/list/remove, owner protection) and
the **brain** (deterministic 5-rule engine, 11/11 offline tests). Phase B proves the **runtime**
and builds the **happy path** — nothing adversarial yet. Two outcomes only:

1. A live agent, wired through the Band SDK, actually *receives* an @mention and a join/leave
   event. These are the two things Phase A could not test without a running agent.
2. The finance crew (Intake → Matcher → Approver) processes one **clean** invoice end to end,
   tags Warden on every handoff, and emits a provenance record built from the **real** extracted
   values — not a self-reported "all clean."

Explicitly **out of scope** this increment: the injection harness, Warden as a live agent,
Investigator, Enforcer, the pay gate. Those are the next increment, and they depend on U1's
runtime facts being true.

---

## Problem Frame

Everything downstream (Warden catching a hijack) rests on two unproven runtime assumptions and
one design seam:

- **Unproven:** does an @mention push to a listening agent over the WebSocket? (Band docs say
  agents only see messages that mention them — but "see" via REST `context` is not the same as a
  live push to a running agent.)
- **Unproven:** does a live join/leave event arrive without a mention? Phase A proved the
  participant *list changes*; it did not prove a *push* arrives. Warden's "watch for sneaky
  ejection" backstop depends on this.
- **Seam:** the provenance record must be assembled from each agent's real output (extracted
  payee, matched amount, actual stage), so that a future hijack is visible in the record's
  *origin*. If agents self-declare "clean," the entire later defense is theater (CLAUDE.md crux #4).

Prove the two facts with the smallest possible spike before building the crew. Fail loud if
either is false — a contingency (Warden polls the participant list) is noted, but we want to
*know*, not silently degrade.

---

## Requirements

- R1. A running SDK agent receives an @mention as a live event (not by polling REST).
- R2. A running SDK agent receives a participant join/leave as a live event, or we record
  definitively that it does not and fall back to polling — loudly, in the findings.
- R3. Intake → Matcher → Approver process the clean invoice `INV-1042` in the correct order,
  each tagging the next agent **and** Warden on handoff.
- R4. Each handoff emits a provenance record whose `facts` (payee, amount) and `completed_stages`
  are derived from the agent's real action, and which the existing `invariants.check` engine
  rules **clean** for a clean invoice.
- R5. The finance crew runs on AI/ML API (OpenAI-compatible); no Band per-agent key is hardcoded
  (all from `.env`).

---

## Key Technical Decisions

- **Spike before crew.** U1 is a throwaway 2-agent script whose only job is to answer R1/R2.
  No business logic. If the SDK package/import differs from what `README.md` claims
  (`band-sdk` install vs `from thenvoi import Agent`), U1 is where we discover it — cheaply.
- **Receiving requires the SDK/WebSocket, not REST.** `band_client.py` (REST) can *send* and
  *read history* but cannot receive live pushes (Band docs: "REST-only integrations cannot
  receive incoming messages"). So live agents use the SDK runtime (`await agent.run()`); the REST
  wrapper stays for deterministic control calls (create room, remove participant) and history.
- **Provenance is built by a shared helper, from real values.** A single `warden/provenance.py`
  builds the record so every agent emits the same shape, sourced from its actual output. This is
  the seam the next increment's Warden trusts.
- **Keep the crew thin.** Three small agents that extract / match / approve. Do not diversify
  across LangGraph + CrewAI adapters yet if one adapter gets all three running faster — pick the
  one that works in the spike and note adapter-spread as a later polish, not a Phase B goal.
- **Fail loud.** A missing env key, a malformed extraction, or a dropped mention raises with a
  clear message. No try/except-swallow, no "default to clean."

---

## Implementation Units

### U1. SDK plumbing spike — prove mention + join/leave delivery

**Goal:** Answer R1 and R2 with the smallest live test, before any business logic.

**Requirements:** R1, R2.

**Dependencies:** none (uses existing Band keys + `.env`).

**Files:**
- `scripts/spike_mention.py` (new) — two agents: a `sender` and a `listener`. Listener runs the
  SDK runtime with a handler that logs every message and membership event it receives. Sender
  @mentions the listener, then a participant is added and removed.
- `PHASE_B_FINDINGS.md` (new, written by the script) — same plain-language style as
  `PHASE_A_FINDINGS.md`: did the mention arrive? did the join/leave push arrive?

**Approach:** Connect the listener via the Band SDK (`Agent.create(...)` per `README.md`; if the
package name or import differs, discover the real one via `pip index` / `docs.band.ai` and update
`README.md` + `requirements.txt`). Sender uses the REST wrapper (`band_client.send_message`) to
post an @mention. Assert the listener's handler fired with the message body. Then add/remove a
third participant via REST and assert the listener received a membership event. If no membership
push arrives, record it plainly and note the polling fallback (Warden re-lists participants each
cycle) — do not pretend it works.

**Patterns to follow:** `scripts/check_room.py` (live-test + plain-language findings file),
`band_client.py` (REST shapes).

**Test scenarios:**
- Live: listener receives an @mention → message body logged. (R1)
- Live: a participant is removed → listener receives a membership/leave event. (R2)
- Failure: listener started without a valid key → raises a clear auth error, not a silent hang.

**Verification:** `python scripts/spike_mention.py` → `PHASE_B_FINDINGS.md` shows YES for mention
delivery, and YES (or an explicit NO + polling fallback) for the join/leave push.
→ verify: mention round-trip observed live; join/leave outcome recorded definitively.

### U2. Provenance builder + finance-crew agents

**Goal:** Three agents that do the real work and emit a real-valued provenance record on handoff.

**Requirements:** R3, R4, R5.

**Dependencies:** U1 (runtime confirmed).

**Files:**
- `warden/provenance.py` (new) — `build_record(...)` assembles the record (`invoice_id`,
  `vendor_id`, `completed_stages`, `actor_role`, `action`, `facts.payee_account`,
  `facts.amount`, `action_cause`) from an agent's actual outputs.
- `tests/test_provenance.py` (new) — offline, no keys.
- `warden/agents/intake.py`, `warden/agents/matcher.py`, `warden/agents/approver.py` (new) —
  thin SDK agents. Intake extracts fields from the invoice; Matcher re-reads `sources/` and
  confirms PO + vendor; Approver checks the limit and approves.
- `fixtures/invoice_clean.json` (new) — a clean `INV-1042` invoice (vendor V-77, $5000, ACC-001).

**Approach:** Each agent, on completing its step, calls `build_record(...)` with its real values
and posts it as a Band structured event (`band_client.post_event`), then @mentions the next agent
**and** Warden. Models run via AI/ML API (`OPENAI_BASE_URL=https://api.aimlapi.com/v1`). Keep the
agents minimal — extraction/matching/approval, nothing more.

**Patterns to follow:** `warden/sources.py` (re-derive from records, never trust claims),
`warden/invariants.py` record shape, `README.md` provenance-record example.

**Test scenarios:**
- `build_record` from a clean extraction → `invariants.check(record, sources) == []`. (R4)
- `build_record` from a tampered extraction (payee `ACC-99999`) → `PAYEE_NOT_ON_FILE` fires.
  (proves the builder preserves the real value rather than laundering it clean)
- `build_record` with a missing required field → raises / returns `MALFORMED_RECORD`, never a
  silent clean.

**Verification:** `python -m pytest tests/test_provenance.py -q` green; the three agent modules
import and construct without live keys.
→ verify: a real extraction round-trips to a clean verdict; a tampered one does not.

### U3. Happy-path runner — clean invoice flows end to end

**Goal:** One command runs the clean invoice through the live crew and shows a correct, fully
ordered, Warden-tagged trail.

**Requirements:** R3, R4.

**Dependencies:** U1, U2.

**Files:**
- `scripts/run_happy_path.py` (new) — Warden (as owner) creates the room, adds Intake/Matcher/
  Approver, drops `fixtures/invoice_clean.json` in, and prints the resulting message + event trail.

**Approach:** Reuse the Phase-A room/participant calls. Run the crew on the clean invoice. Read
the trail back via `band_client.context` / `messages`. Assert the stage order
`intake → matched → limit_checked → approved` appears, each handoff tagged Warden, and the final
record's payee/amount equal the on-file values. No Warden agent logic yet — this proves the crew
produces correct, well-formed, trustworthy provenance for the next increment to police.

**Patterns to follow:** `scripts/check_room.py` (room setup + readable run log).

**Test scenarios:**
- Happy path: clean invoice → stages appear in correct order, each tagged Warden, final
  payee = `ACC-001`, amount = `5000`. (R3, R4)
- Failure: a required `.env` key missing → clear startup error naming the missing key. (R5)

**Verification:** `python scripts/run_happy_path.py` prints an ordered, Warden-tagged trail ending
in `approved` with correct facts, and exits 0.
→ verify: clean invoice flows end to end; trail is ordered, tagged, and factually correct.

---

## Scope Boundaries

**In scope:** the two runtime proofs (U1), the provenance seam + crew (U2), the clean happy path
(U3).

### Deferred to Follow-Up Work (next increment)
- Injection harness (embed AgentDojo / InjecAgent payloads into an invoice).
- Warden as a live agent running `invariants.check` on the tagged handoffs + the pay gate.
- Investigator (chain reconstruction) and Enforcer (removal + freeze + human ping).
- The Warden-off / Warden-on demo toggle.
- Featherless wiring for Warden's narration (partner prize).

**Out of scope (project identity):** multiple colluding compromised agents; a compromised Warden.
Stated as a threat-model boundary, per `CLAUDE.md`.

---

## Risks

- **SDK package/import mismatch.** `README.md` claims `band-sdk` install but `from thenvoi import
  Agent`. U1 is deliberately first so this surfaces cheaply; update `requirements.txt` + `README`
  when the real names are known.
- **No live join/leave push.** If U1 finds membership events are not pushed, Warden's
  ejection-watch backstop becomes polling. Acceptable, but must be recorded loudly, not assumed.
- **Human-in-the-loop later needs the Human API (enterprise-only).** Not a Phase B concern, but do
  not design the future human ping on the Human API — use the Band web UI or a mention.
