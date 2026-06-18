# Warden Demo Video Script (about 3 minutes)

Record in 4 short clips. If you fumble one, just redo that one clip. Speak slowly
and a little louder than feels normal. You can stitch the clips later, or just
record one continuous take once you have practiced.

## Before you hit record
1. Close Slack, WhatsApp, email, and turn on Do Not Disturb (no popups on screen).
2. Terminal 1: run `uvicorn web.app:app --reload`. Open `http://127.0.0.1:8000` and make the browser full screen.
3. Terminal 2: have this typed but NOT run yet: `python scripts/run_recruitment.py`
4. On the dashboard, click the "Real invoice, tampered (BEC)" sample so it is loaded.
5. Recorder: press Win+G (Windows Game Bar), or use OBS. Turn the microphone ON.
6. Do one full practice run with no recording. Then record for real.

---

## CLIP 1: The hook (about 25 seconds)
On screen: the dashboard home page (the money stat cards are visible).

Say:
> "Companies now let teams of AI agents pay their invoices. One reads it, one
> approves it, one sends the money. Last year, thieves stole two point seven
> seven billion dollars by sending one fake invoice with the bank account
> secretly swapped. The agents never notice. This is Warden. It is the agent
> that watches the other agents, and it catches the tricked one before the money
> leaves."

---

## CLIP 2: Catch it on the dashboard (about 50 seconds)
On screen: click the tampered invoice sample, scroll the text, point at the
"BANK DETAILS HAVE CHANGED" line. Then click "Run pipeline" and let it play.

Say (while it runs):
> "Here is a real invoice from a supplier, but the bank account has been changed
> to the attacker's. Watch. The first agent reads it. But when Warden checks the
> handoff, it does not trust the document. It looks up the supplier's real
> account in the company records, sees they do not match, and raises a warning.
> The Investigator traces it, brings in a Threat-Intel expert that confirms it is
> a known bad account, and the Enforcer freezes the payment. Five thousand
> dollars, blocked."

On screen: scroll to the Decision log. Point at the red "Can this invoice
proceed to payment? NO". Point at the small lock badge. Click "Download log".

Say:
> "Every decision is written down in plain English, with the reason. It is signed,
> so it cannot be faked, and you can download it as an audit record."

---

## CLIP 3: The attack battery (about 25 seconds)
On screen: scroll to the "Attack battery" card. Click "Run battery". Let the
rows tick to 6 out of 6.

Say:
> "And this is not one lucky catch. Here are six real attacks at once, taken from
> public security tests. Payment redirect, amount changed, steps skipped, a forged
> approval. Warden blocks all six, every time, with fixed rules. No guessing."

---

## CLIP 4: Live on Band, then close (about 60 seconds)
On screen: switch to Terminal 2. Run `python scripts/run_recruitment.py`. Let the
log lines scroll. Point at the key lines as they appear.

Say:
> "And it is not just a screen. It runs live on the real Band platform, with
> separate agents talking to each other. Warden flags the bad invoice. Now watch:
> the Investigator decides it needs help and pulls a Threat-Intel agent into the
> room, live. An agent bringing in another agent. The expert confirms the fraud,
> and the Enforcer removes the tricked agent from the room."

On screen: point at the SCORECARD with both YES.

Say:
> "Pulled in live, yes. Tricked agent removed, yes. The money never moved."

On screen: title card, or back to the dashboard verdict.

Say:
> "A team of AI agents can all be fooled by the same fake invoice. Warden cannot,
> because it does not trust the document. It checks the company's own records.
> Everyone else built agents that do a job. Warden is the one that catches the
> thief. Thank you for watching."

---

## Clip checklist
- [ ] Clip 1: hook over the dashboard home
- [ ] Clip 2: tampered invoice, BLOCKED, decision log, lock badge, download
- [ ] Clip 3: attack battery ticks to 6/6
- [ ] Clip 4: live Band run (JOIN, removal, both-YES scorecard) and the closing line
- [ ] Optional 5 second shot: run a clean invoice to show the green "CLEARED" (proves it does not cry wolf)
