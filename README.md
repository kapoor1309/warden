<div align="center">

# 🛡️ Warden

### Catch the hijacked agent before the money moves.

**A security crew that lives inside a [Band](https://band.ai) room, watches a multi-agent invoice-approval workflow, spots a teammate hijacked by a poisoned invoice, traces it, and ejects it — before a single payment is released.**

`Band of Agents Hackathon` · `Track 3 — Regulated & High-Stakes` · `Accounts-Payable / BEC fraud`

</div>

---

## The problem

Companies are handing their accounts-payable workflow to teams of AI agents: one reads the invoice, one matches the purchase order, one approves, one pays. That opens a new door for the oldest scam in finance — **Business Email Compromise (BEC):** an attacker slips a tampered invoice into the pipeline with the bank account secretly swapped to their own. The agents see a normal-looking invoice, approve it, and wire the money to the criminal.

> **$2.77B** lost to BEC in 2024 alone, and **$55.5B** exposed losses over a decade. — *FBI IC3*

Everyone in this hackathon is building agents that **do a job.** Warden is the agent that **watches the other agents** — because the most dangerous attacker isn't outside your crew, it's one of your own agents that just got hijacked.

## What Warden does

```
Intake → Matcher → Approver → Payer        ← the normal bill-paying line
   └────────── watched by ──────────┘
        Warden · Investigator · Threat-Intel · Enforcer   ← the security crew
```

When a tampered invoice enters:

1. **Warden** re-derives the *real* payee from the company's own records, sees the invoice's account doesn't match, and raises a flag.
2. **Investigator** decides it needs help and **recruits a Threat-Intel specialist live into the room** (an agent pulling another agent into the conversation — on the real Band platform).
3. **Threat-Intel** screens the account against a fraud watchlist and confirms it's a known money-mule account.
4. **Enforcer** **ejects the compromised agent** from the room and freezes the payment — before any money is released.

Every decision is written to an **explainable, downloadable audit log** so an auditor can see exactly *why* an invoice was cleared or blocked.

## Why it's different (the moat)

**Warden's security decision is deterministic — there is no LLM in the gate.**

A committee of LLM agents can all be fooled by the *same* poisoned document. Warden can't, because it never reads the document as instructions — it ignores what the invoice *claims* and **re-derives the truth from the company's own records** (`vendor_master`, `purchase_orders`). The allow/deny call is plain, testable code. LLMs are used only to *reason about and narrate* an incident, never to decide it.

This is also why catching a brand-new attack **never requires new code**: Warden checks what *correct* behaviour looks like (a contract), not a catalogue of known attack signatures.

## How we used Band

Warden uses Band's room mechanics as a real security primitive, not just a chat log:

- **Live recruitment** — the Investigator calls `add_participant` to pull the Threat-Intel agent into the room mid-investigation. *Agents recruiting agents.*
- **Containment** — the Enforcer calls `remove_participant` to eject the compromised agent. We verified live that any member can remove another, but **not the room owner — so Warden owns the room.**
- **Mention-scoped handoffs** — every handoff `@mentions` Warden, so the guard sees every step.
- **Join/leave as a tripwire** — `on_participant_added` / `on_participant_removed` callbacks mean a hijacked agent can't quietly pull in a helper or slip away unseen.

## The attacks are real

We never invent the attacks. Malicious payloads (e.g. attacker IBANs) are drawn from peer-reviewed, third-party agent-attack benchmarks — **AgentDojo** (Invariant Labs' banking suite) and **InjecAgent** — the same suites the field uses to grade defenses. A judge can supply their own tampered invoice and it is still caught.

## Run it

**The dashboard** (no keys needed — runs on the deterministic core):
```bash
pip install -r requirements-web.txt
uvicorn web.app:app --reload          # → http://127.0.0.1:8000
```
Load a sample invoice (clean or BEC-tampered), hit **Run pipeline**, and watch every stage execute with a live verdict and a downloadable decision log.

**The live Band run** (agents recruiting + ejecting agents on the real platform):
```bash
pip install -r requirements.txt
python scripts/run_recruitment.py     # needs agent keys in .env
```

**The offline brain** — 49 passing tests prove the security engine works before any network exists:
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
| Payer | The money gate — pays only on Warden's HMAC-signed sign-off | Deterministic |

**Warden's five rules** (`warden/invariants.py`): right order / nothing skipped · amount matches the PO · payee equals the account on file · action not driven by document text · every agent stays in its lane.

**The keystone:** money cannot move without Warden's signed sign-off, issued over the *re-derived* account — never the account an agent reported.

## Threat model (scoping is strength)

- **In scope:** one compromised agent at a time; Warden (the room owner) and the pay-gate are honest.
- **Out of scope:** multiple colluding agents, a compromised Warden.

## Tech

Python · [Band SDK](https://band.ai) · LangGraph · FastAPI + a hand-built dashboard · AI/ML API (gpt-4o-mini) · Featherless (open models, for narration) · HMAC-signed pay-gate.

Engineering notes for contributors live in [`CLAUDE.md`](CLAUDE.md).

## License

MIT.
