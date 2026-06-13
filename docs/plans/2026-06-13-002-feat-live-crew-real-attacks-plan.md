---
title: "feat: complete the live crew + real third-party attacks + per-dev config"
status: active
date: 2026-06-13
type: feat
depth: deep
---

# feat: complete the live crew + real third-party attacks + per-dev config

## Summary

The live crew runs end-of-chain (Intake → Warden → Investigator → Enforcer) but the
**middle is missing** (no Matcher/Approver), the **handles are hardcoded** to one
developer, and the **attack is self-invented** — which violates the new, non-negotiable
CLAUDE.md rule that attacks must be real, maximum-capability, and third-party. This
increment closes those, in priority order, and adds the deterministic pay-gate that
finally closes the self-report crux:

1. **Per-developer agent config** — one `BAND_HANDLE_PREFIX`, handles built as
   `{prefix}/{slug}`, so Yash (`yashb967`) and Parshiv (`parshiv.kapoor`) each run the
   same code under their own 6 registered agents.
2. **Matcher + Approver as live, deterministic (no-LLM) agents** — completing
   Intake → Matcher → Approver → Warden so every stage runs and the happy path reaches
   `approved`.
3. **Real third-party attack harness** — pull injection payloads from AgentDojo
   (Banking suite) and InjecAgent, plus a judge-supplied path; retire the hand-written
   poisoned invoice.
4. **Deterministic pay-gate + Payer** — money releases only on Warden's signed sign-off,
   re-deriving the payee from records, never trusting an agent's self-reported value.

Verification target: `demo/run_investigation.py` catches a **benchmark** attack
end-to-end and the clean path flows all stages, with offline tests still green.

---

## Problem Frame

The crew is a half-chain built on three soft spots:

- **Handles are hardcoded to `parshiv.kapoor/*`.** Each developer registers their own 6
  Band agents; the spike proved Yash's matcher is `yashb967/po-matcher`. With the wrong
  prefix, every `@mention` routes to a non-existent handle and the chain silently dies.
  This is the #1 unblock — nothing else can be demoed by both people until it's fixed.
- **Matcher and Approver don't exist.** Both demos add them as participants and Intake
  `@mentions` Matcher, but `agents/matcher.py` / `agents/approver.py` are absent, so the
  chain dead-ends after Intake; stages never progress past `intake`.
- **The attack is a self-invented stand-in.** `attacks/build_invoice.py` hand-writes a
  "skip the checks, CEO-approved" invoice. Per CLAUDE.md, catching an attack we authored
  proves nothing. The graded attack must be real, third-party, max-capability.
- **The self-report crux is still open.** Intake writes its own record; nothing executes
  a payment from the *real* instruction. Without a deterministic pay-gate, a hijack that
  reports a clean record while acting otherwise is uncaught.

---

## Requirements

- R1. Both developers run the identical code under their own agent set by changing only
  `.env` (handle prefix + their 6 ids/keys). No handle is hardcoded to one owner.
- R2. The full happy path runs live: Intake → Matcher → Approver, every stage tagged to
  Warden, ending at `approved` with re-derived facts, Warden clean at each step.
- R3. Matcher and Approver are deterministic (no LLM); they re-derive payee/amount from
  `sources/` and never trust the invoice's claimed values.
- R4. The graded attack payload comes from a third-party benchmark (AgentDojo Banking
  and/or InjecAgent) or a judge typed live — never hand-authored by us. A dev stand-in
  may exist but is never demoed or claimed on.
- R5. A deterministic pay-gate releases payment only on Warden's signed sign-off and only
  to the re-derived on-file account; otherwise it freezes and escalates.
- R6. Offline tests stay green (≥23) and grow to cover the new deterministic logic.
- R7. The provenance record has one canonical shape across Intake (LLM) and the
  deterministic agents; the parser tolerates the legacy `claimed_source` key.

---

## Key Technical Decisions

- **Single source of truth for handles.** A small `agents/identity.py` exposes
  `handle(slug)` = `f"{BAND_HANDLE_PREFIX}/{slug}"` and the canonical slug map. Every
  agent imports it; no module hardcodes `parshiv.kapoor`. **Fail loud** if
  `BAND_HANDLE_PREFIX` is unset — never default to one person's handle.
- **Only Intake uses an LLM.** It is the only agent that reads the untrusted document, so
  it is the only place a hijack can enter. Matcher/Approver are **deterministic
  `SimpleAdapter` agents** that re-derive from `sources/`. This is cheaper, and it means
  the workflow middle cannot be prompt-injected at all — a security property, not just a
  cost choice. Reuse the already-tested `warden/agents.py` logic.
- **Re-derivation neutralizes *and* surfaces fraud at the earliest stage.** Because
  Matcher re-derives the on-file account, a poisoned payee never propagates — and Warden,
  tagged on Intake's handoff, flags `PAYEE_NOT_ON_FILE` at the **intake** stage before
  Matcher even runs. So the attack demo terminates at Intake (flag → Investigator →
  Enforcer), and Matcher/Approver carry the **clean** path. This is correct; document it
  so the demo narration matches the live flow.
- **Attacks are third-party (CLAUDE.md rule).** Prefer **AgentDojo's Banking suite**
  (closest domain fit: payment/transaction injections) and **InjecAgent** (indirect
  injection / data-stealing). Add a **judge-supplied** path. Prefer adaptive over static;
  **ChatInject**-style chat-template abuse is in-scope because our agents talk over Band
  chat. We never author the graded attack.
- **The pay-gate is deterministic and signature-gated.** Warden issues a signed token
  (HMAC over `invoice_id|payee|amount|stages`) only when all stages are clean through
  `approved`. The Payer verifies the signature AND re-derives the payee from `sources/`
  before releasing — so it trusts neither the LLM record nor an unsigned message. Closes
  crux #4.
- **One canonical record shape; tolerant parser.** Standardize on
  `facts.{amount,payee_account}.{value, origin}`. A shared normalizer accepts the legacy
  `claimed_source` key so Parshiv's existing Intake prompt keeps working during the
  transition.

---

## High-Level Technical Design

The full chain after this increment (clean path solid, attack path branches at Warden):

```mermaid
sequenceDiagram
    participant Doc as Invoice (untrusted)
    participant I as Intake (LLM)
    participant M as Matcher (no-LLM)
    participant A as Approver (no-LLM)
    participant W as Warden (no-LLM, owner)
    participant V as Investigator (LLM)
    participant E as Enforcer (no-LLM)
    participant P as Payer (no-LLM gate)

    Doc->>I: invoice (clean OR benchmark-poisoned)
    I->>W: intake record (facts origin=invoice_document) @Matcher @Warden
    alt payee/amount mismatch (poisoned)
        W->>V: FLAG payee_not_on_file @Investigator
        V->>E: verdict: compromised, agent=Intake @Enforcer
        E->>E: remove_participant(Intake) + freeze + human escalation
    else clean
        W-->>I: clean (audit event)
        I->>M: (handoff already sent)
        M->>W: matched record (facts re-derived from sources) @Approver @Warden
        W-->>M: clean
        A->>W: approved record (limit_checked+approved) @Payer @Warden
        W->>P: signed sign-off token (HMAC over invoice|payee|amount|stages)
        P->>P: verify signature + re-derive payee; release OR freeze
    end
```

---

## Implementation Units

### U1. Per-developer agent identity (handle prefix)

**Goal:** Same code runs under either developer's 6 agents; no hardcoded owner.

**Requirements:** R1.

**Dependencies:** none.

**Files:**
- `agents/identity.py` (new) — `handle(slug)`, the canonical `SLUGS` map
  (`invoice-intake`, `po-matcher`, `approver`, `warden`, `investigator`, `enforcer`),
  and `agent_env(name)` → `(id, key)`. Fail loud if `BAND_HANDLE_PREFIX` unset.
- `agents/intake.py`, `agents/investigator.py`, `warden/warden_agent.py`,
  `warden/enforcer_agent.py` (modify) — replace the hardcoded `parshiv.kapoor/*` handle
  defaults with `identity.handle(...)`.
- `.env.example` (modify) — document `BAND_HANDLE_PREFIX` and BOTH dev sets clearly
  (Yash `yashb967`, Parshiv `parshiv.kapoor`), with the 6 id/key slots.
- `scripts/check_handles.py` (new) — for each agent key, resolve its real handle from the
  live API and assert it equals `handle(slug)`; print mismatches loudly.
- `tests/test_identity.py` (new).

**Approach:** One module owns handle construction. Agents call `handle("po-matcher")`
instead of embedding a name. `check_handles.py` is the live truth check (the spike showed
`yashb967/po-matcher`); run it once per developer after they fill `.env`.

**Patterns to follow:** `scripts/check_connection.py` (per-agent env iteration + live
check), `band_client.py`.

**Test scenarios:**
- `handle("po-matcher")` with `BAND_HANDLE_PREFIX=yashb967` → `yashb967/po-matcher`.
- `BAND_HANDLE_PREFIX` unset → `handle()` raises a clear error (fail loud), not a default.
- Unknown slug → raises.
- (live, via `check_handles.py`) each registered agent's API-reported handle equals the
  expected `{prefix}/{slug}`.

**Verification:** `BAND_HANDLE_PREFIX=yashb967 python scripts/check_handles.py` reports all
6 handles match. → verify: no module contains the literal `parshiv.kapoor`; both prefixes
resolve correctly.

### U2. Matcher + Approver live agents + canonical record

**Goal:** Complete Intake → Matcher → Approver → Warden with all stages, deterministically.

**Requirements:** R2, R3, R7.

**Dependencies:** U1.

**Files:**
- `warden/record.py` (new) — canonical record builder/normalizer; wraps
  `warden/provenance.py` and accepts the legacy `claimed_source` key as an alias for
  `origin`. Single parse path used by Warden + the new agents.
- `agents/matcher.py` (new) — `band` `SimpleAdapter`; on_message: parse the upstream
  record, re-derive payee/amount from `sources/` via `warden.agents.matcher_handoff`,
  `send_message` the matched record `@approver @warden`.
- `agents/approver.py` (new) — `SimpleAdapter`; parse matched record, build approved
  record via `warden.agents.approver_handoff` (limit check), `send_message` `@payer
  @warden`.
- `warden/agents.py` (modify) — ensure the handoff builders take an upstream record and
  carry `invoice_id`/`vendor_id` forward; align field names with `warden/record.py`.
- `agents/intake.py` (modify) — emit `origin` (keep `claimed_source` accepted by the
  normalizer for back-compat).
- `demo/run_core_loop.py` (modify) — expect the chain to reach `approved` with Warden
  clean at each stage.
- `tests/test_agents.py` (modify), `tests/test_record.py` (new).

**Approach:** Matcher/Approver never trust the invoice — they re-derive from `sources/`
keyed by the upstream record's `invoice_id`/`vendor_id`, and **fail loud** on unknown
vendor / missing PO / over-limit (those are real reject conditions, not silent passes).
They listen via `@mention`, build their record, and tag the next agent + Warden.

**Patterns to follow:** `warden/warden_agent.py` (SimpleAdapter + `extract_record`),
`warden/agents.py` (re-derive logic), `agents/base.py` (agent construction; but no LLM —
build the `SimpleAdapter` directly like `warden_agent.py`).

**Test scenarios:**
- Matcher: clean intake record → matched record → `invariants.check == []`.
- Matcher: intake record with unknown `vendor_id` → raises (fail loud).
- Approver: matched record under limit → approved record clean, stages
  `[intake, matched, limit_checked, approved]`.
- Approver: PO amount over `spend_limit` → raises (reject, not approve).
- `warden/record.py`: a record using legacy `claimed_source` normalizes to `origin` and
  passes `invariants.check` when values are correct.
- Integration: a clean intake record fed through Matcher then Approver yields three
  ordered records, each clean.

**Verification:** `python demo/run_core_loop.py` shows intake → matched → approved live,
Warden clean at each handoff. → verify: stages reach `approved`; offline tests green.

### U3. Real third-party attack harness

**Goal:** The graded attack comes from a third-party benchmark or a judge — never us.

**Requirements:** R4.

**Dependencies:** U1, U2.

**Files:**
- `attacks/benchmarks.py` (new) — loaders that yield injection payloads from **AgentDojo**
  (Banking suite) and **InjecAgent**. Either depend on the `agentdojo` package / vendor a
  small attributed payload set from the public repos, or fetch InjecAgent's test-case
  JSON. Each payload carries its source + license attribution.
- `attacks/build_invoice.py` (modify) — `embed(payload)` wraps a benchmark injection
  string inside an invoice document (the untrusted content Intake reads); keep the old
  hand-written invoice ONLY behind an explicit `--dev-standin` flag, clearly labeled.
- `attacks/judge_input.py` (new) — accept an attack string from stdin / a CLI arg so a
  judge can supply their own live.
- `demo/run_investigation.py` (modify) — default to a benchmark payload (random draw),
  not the hand-written one; print which benchmark + case id was used.
- `requirements.txt` (modify) — add `agentdojo` (or vendored-data note).
- `tests/test_attacks.py` (new).

**Approach:** Bias-proof by construction — the demo draws an attack we did not write. The
embedder is generic (it does not special-case any payload), reinforcing contract-not-
catalog. ChatInject-style payloads (instructions framed as chat turns) are valid since
agents communicate over Band chat.

**Patterns to follow:** `attacks/build_invoice.py` current structure; CLAUDE.md "Attacks
are real" section for sourcing rules.

**Test scenarios:**
- Loader returns ≥1 non-empty payload from each configured benchmark (skip-with-clear-
  message if a benchmark isn't installed — but never silently fall back to a hand-written
  attack for the graded run).
- `embed(payload)` produces an invoice document that contains the payload verbatim.
- Judge-input path: a supplied string is embedded unchanged.
- `--dev-standin` is the only way to get the hand-written invoice, and it prints a loud
  "DEV STAND-IN — not for demo/grading" banner.

**Verification:** `python demo/run_investigation.py` runs a benchmark attack end-to-end
(Intake poisoned → Warden flags → Investigator → Enforcer ejects Intake), and the
transcript names the benchmark source. → verify: no hand-authored attack in the graded
path; judge can supply one.

### U4. Deterministic pay-gate + Payer

**Goal:** Money releases only on Warden's signed sign-off, to the re-derived account.

**Requirements:** R5.

**Dependencies:** U2.

**Files:**
- `warden/paygate.py` (new) — sign/verify a sign-off token (HMAC over
  `invoice_id|payee|amount|completed_stages`) using a shared secret; `release_or_freeze`
  that re-derives the payee from `sources/` and refuses on mismatch or bad signature.
- `warden/warden_agent.py` (modify) — when a record is clean through `approved`, emit a
  signed sign-off event; never sign a flagged invoice.
- `agents/payer.py` (new) — `SimpleAdapter`; on the approved handoff, require Warden's
  signed token, verify via `paygate`, then release (mock) or freeze + escalate.
- `tests/test_paygate.py` (new).

**Approach:** The Payer trusts neither the LLM record nor an unsigned message. It verifies
Warden's signature and independently re-derives the payee. This is the keystone from
CLAUDE.md: if money can move without Warden's signature over the correct facts, nothing
else matters. Gives the "frozen vs released" demo beat.

**Patterns to follow:** `warden/invariants.py` (deterministic, re-derive from sources),
`warden/enforcer_agent.py` (SimpleAdapter acting on a structured message).

**Test scenarios:**
- Valid Warden signature over correct facts + payee matches on-file → released.
- Missing/invalid signature → frozen, no release.
- Signature over a tampered payee (≠ on-file) → frozen.
- Flagged invoice (Warden never signed) → Payer never releases.

**Verification:** clean path → payment released; benchmark-attack path → no sign-off →
frozen. → verify: `test_paygate.py` green; demo shows money frozen on the attack.

---

## Scope Boundaries

**In scope:** the four units above and the canonical-record reconciliation.

### Deferred to Follow-Up Work
- Threat-Intel + Reporter showcase agents (README "showcase" tier).
- A/B demo toggle (Warden off vs on) and the chain-graph visual for the pitch.
- Multi-benchmark scoring / catch-rate report across the full AgentDojo + InjecAgent sets.

**Out of scope (project identity, per CLAUDE.md threat model):** multiple colluding
compromised agents; a compromised Warden. State as a scoping boundary in the pitch.

---

## Risks & Dependencies

- **AgentDojo / InjecAgent install + license.** Confirm `agentdojo` is pip-installable and
  how to enumerate Banking-suite injections; InjecAgent is dataset JSON — vendor a small
  attributed subset if no clean package API. If neither installs cleanly, the judge-input
  path is the fallback for a real (non-self-authored) attack — record this honestly, do
  not regress to the hand-written invoice for grading. (External research flagged this as
  the one open implementation unknown.)
- **Handle slugs must match registration.** `check_handles.py` (U1) is the guard; run it
  before any live demo. A wrong slug = silent mention failure.
- **Record-shape drift.** Intake (LLM) emits via a prompt; the normalizer must tolerate
  both `origin` and `claimed_source` or the live chain breaks even though offline tests
  pass.
- **Shared secret for the pay-gate** lives in `.env` (gitignored), per developer; never
  commit it.

---

## Sources & Research

- AgentDojo (Invariant Labs) — dynamic tool-calling injection benchmark; Banking suite is
  the closest fit to invoice/payment fraud; 7000+ security test cases.
- InjecAgent — 1,000 indirect-prompt-injection cases (data-stealing + unauthorized tool
  calls), Base and Enhanced variants.
- AgentDyn (built on AgentDojo), ASB (Agent Security Bench) — broader suites for extras.
- Technique families to prefer over toy payloads: indirect injection via ingested
  content, semantic persuasion (never "ignore your instructions"), encoded/non-English
  payloads, ChatInject-style chat-template abuse (fits Band chat), zero-click exfil
  patterns; prefer adaptive ("the attacker moves second") over static.
