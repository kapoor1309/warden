<div align="center">

# Warden

### Catch the hijacked agent before the money moves.

A security crew that lives inside a [Band](https://band.ai) room, watches a multi-agent
invoice-approval workflow, and catches a teammate hijacked by a poisoned invoice —
tracing it and ejecting it before any payment is released.

**Band of Agents Hackathon · Track 3 — Regulated & High-Stakes**

</div>

---

## The problem

Companies are handing accounts-payable to teams of AI agents — one reads the invoice, one
matches the purchase order, one approves, one pays. That opens the door to the oldest scam in
finance: **Business Email Compromise.** An attacker slips in a tampered invoice with the bank
account swapped to their own. The agents see a normal invoice, approve it, and wire the money
to the criminal.

> **$2.77B** lost to BEC in 2024 · **$55.5B** exposed over a decade — *FBI IC3*

The most dangerous attacker isn't outside the crew. It's one of your own agents, hijacked.

## What Warden does

```
Intake → Matcher → Approver → Payer          the bill-paying line
   └──────── watched by ────────┘
   Warden · Investigator · Threat-Intel · Enforcer
```

When a tampered invoice enters:

1. **Warden** re-derives the real payee from company records, sees it doesn't match, and flags it.
2. **Investigator** recruits a Threat-Intel specialist **live into the room** — an agent pulling in another agent.
3. **Threat-Intel** screens the account and confirms it's a known money-mule.
4. **Enforcer** ejects the compromised agent and freezes the payment — before any money moves.

Every decision is written to a **signed, tamper-evident** audit log you can download.

## Why it can't be fooled

**Warden's decision is deterministic — there is no LLM in the gate.**

A committee of LLM agents can all be fooled by the *same* poisoned document. Warden can't: it
never treats the document as instructions, and re-derives the truth from the company's own
records (`vendor_master`, `purchase_orders`). The allow/deny call is plain, testable code; LLMs
only narrate an incident, never decide it.

This is also why catching a brand-new attack **never requires new code** — Warden checks what
*correct* behaviour looks like, not a catalogue of known attack signatures.

## How we used Band

Band's rooms are a security primitive here, not just a chat log:

- **Live recruitment** — the Investigator calls `add_participant` to pull Threat-Intel into the room mid-investigation.
- **Containment** — the Enforcer calls `remove_participant` to eject the compromised agent. *(Verified live: a member can't remove the owner — so Warden owns the room.)*
- **Join/leave tripwire** — participant callbacks mean a hijacked agent can't quietly pull in a helper or slip away unseen.

## The attacks are real

Malicious payloads are drawn from third-party agent-attack benchmarks — **AgentDojo** (banking
suite) and **InjecAgent** — the same suites the field uses to grade defenses. A judge can supply
their own tampered invoice and it is still caught. The dashboard's **attack battery** fires a
matrix of real attacks (payment redirect, amount tamper, process bypass, forged sign-off…) at the
engine and blocks them **6/6**, deterministically.

## Run it

**Dashboard** — no keys needed, runs on the deterministic core:
```bash
pip install -r requirements-web.txt
uvicorn web.app:app --reload        # http://127.0.0.1:8000   (pitch deck at /deck)
```

**Live Band run** — agents recruiting and ejecting agents on the real platform:
```bash
pip install -r requirements.txt
python scripts/run_recruitment.py   # needs agent keys in .env
```

**Offline core** — 54 passing tests prove the engine before any network exists:
```bash
python -m pytest tests/ -q
```

## Architecture

| Component | Role | Brain |
|-----------|------|-------|
| Intake | Reads the invoice, extracts fields (the hijackable surface) | LangGraph + LLM |
| Matcher / Approver | Re-derive payee & amount from records, check the limit | Deterministic |
| **Warden** | Runs the 5-rule engine on every handoff; signs the pay-gate | **Deterministic** |
| **Investigator** | Traces the flag, recruits Threat-Intel, rules on compromise | Deterministic + LLM narration |
| **Threat-Intel** | Screens the payee account against a fraud watchlist | Deterministic + LLM narration |
| **Enforcer** | Ejects the compromised agent, freezes payment, escalates | Deterministic |
| Payer | Pays only on Warden's HMAC-signed sign-off | Deterministic |

**The five rules** (`warden/invariants.py`): right order, nothing skipped · amount matches the PO ·
payee equals the account on file · action not driven by document text · every agent stays in its lane.

**The keystone:** money moves only on Warden's signed sign-off, issued over the *re-derived*
account — never the account an agent reported.

## Threat model

- **In scope:** one compromised agent at a time; Warden (room owner) and the pay-gate are honest.
- **Out of scope:** multiple colluding agents, a compromised Warden.

## Tech

Python · [Band SDK](https://band.ai) · LangGraph · FastAPI · AI/ML API · Featherless · HMAC-signed pay-gate.
Engineering notes live in [`docs/CLAUDE.md`](docs/CLAUDE.md).

## License

MIT
