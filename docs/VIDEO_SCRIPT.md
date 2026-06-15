# Warden — Demo Video Script (~2:45)

**Goal:** judges instantly get the threat, see it caught, and see agents collaborating
live on Band. Lead with drama, end with the moat line.

**Recording setup before you start:**
- Dashboard running: `uvicorn web.app:app --reload` → open `http://127.0.0.1:8000`, full-screen the browser.
- A second terminal ready with `python scripts/run_recruitment.py` (don't run it yet).
- Screen-record at 1080p (Windows `Win+G`, or OBS). Speak slowly. Total target: under 3 min.

---

### SCENE 1 — The hook (0:00–0:25)
**On screen:** the dashboard landing page (the fraud stat cards visible).

> "Companies now let teams of AI agents pay their invoices — one reads it, one approves it, one wires the money. Last year, criminals stole **2.77 billion dollars** by slipping in one tampered invoice with the bank account secretly swapped. The agents never notice."
>
> "This is **Warden** — the agent that watches the other agents, and catches the hijacked one before the money moves."

---

### SCENE 2 — Catch it on the dashboard (0:25–1:25)
**On screen:** click the **"Real invoice — tampered (BEC)"** sample. Briefly scroll the invoice text — point at the "BANK DETAILS HAVE CHANGED" line. Click **Run pipeline.**

> "Here's a real commercial invoice from a supplier — except the remittance block has been tampered with. The account was swapped to the attacker's. Watch the pipeline run."

**On screen:** the timeline animates stage by stage; stop talking and let it play to the red **Payment blocked** verdict.

> "Intake reads it. But when **Warden** checks the handoff, it doesn't trust the document — it looks up the supplier's *real* account on file, sees it doesn't match, and flags it. The Investigator traces it, pulls in a Threat-Intel specialist that confirms it's a known money-mule account, and the Enforcer freezes the payment. **Five thousand dollars, blocked.**"

**On screen:** scroll to the **Decision log** panel; hover the red "Can this invoice proceed to payment? NO". Click **⤓ Download log**.

> "And every decision is logged in plain English — *why* it was blocked — and exported as an audit trail. That's built for a regulated, high-stakes world."

---

### SCENE 3 — The live Band run (1:25–2:25) ← the wow
**On screen:** switch to the terminal. Run `python scripts/run_recruitment.py`. Let the agents' log lines scroll. Narrate over them.

> "But this isn't just a dashboard — it's running on the **real Band platform**, with separate agents talking to each other. Watch what happens when the tampered invoice hits the live crew."

**On screen:** point to each line as it appears.

> "Warden flags it. Now the Investigator does something special — it decides it needs help and **recruits a Threat-Intel agent live into the room.** *(point at `recruited Threat-Intel` and the `JOIN` line)* An agent, pulling in another agent. The specialist screens the account, confirms fraud, and the Enforcer **ejects the compromised agent from the room.** *(point at `removing invoice-intake` and `LEAVE`)*"

**On screen:** the SCORECARD with both **YES**.

> "Recruited live: yes. Compromised agent ejected: yes. The money never moved."

---

### SCENE 4 — The moat + close (2:25–2:45)
**On screen:** back to the dashboard verdict, or a simple title card.

> "Here's the key idea: a committee of AI agents can all be fooled by the *same* poisoned document. **Warden can't** — its decision is deterministic. It ignores what the invoice claims and re-derives the truth from the company's own records. No LLM in the gate."
>
> "Everyone else built agents that do a job. **Warden is the one that catches the traitor.** Thanks for watching."

---

### Shot list checklist
- [ ] Dashboard: tampered invoice → BLOCKED verdict
- [ ] Decision log panel + download click
- [ ] Terminal: live recruitment run, JOIN + LEAVE + SCORECARD (both YES)
- [ ] Clean invoice run showing green "CLEARED" (optional 5-sec b-roll — proves it doesn't cry wolf)
- [ ] Title card with the one-liner for the close
