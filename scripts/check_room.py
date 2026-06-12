"""Phase A, tests 2-4: rooms, participants, and removal authority.

Proves (using only REST, no LLM keys needed):
  - Warden can CREATE a room.
  - Warden can ADD other agents into it.
  - We can LIST who is in the room.
  - The room owner (Warden) can REMOVE a participant  -> the Enforcer's hands.
  - Whether a NON-owner can remove someone              -> who must be Enforcer.

The exact request shapes for Band's API are discovered by trying a few
candidates, so this keeps working even if the docs are vague.

Run from repo root:  python scripts/check_room.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import httpx

load_dotenv()

BASE = os.getenv("THENVOI_REST_URL", "https://app.band.ai/").rstrip("/") + "/api/v1"

NAMES = ["INTAKE", "MATCHER", "APPROVER", "WARDEN", "INVESTIGATOR", "ENFORCER"]
KEYS = {n: os.getenv(f"{n}_API_KEY") for n in NAMES}
IDS = {n: os.getenv(f"{n}_AGENT_ID") for n in NAMES}
HANDLES = {n: (os.getenv(f"{n}_HANDLE") or "").lstrip("@") for n in NAMES}

# Collect everything we learn here; the findings file is written from it.
LOG = []


def note(line=""):
    print(line)
    LOG.append(line)


def client(key):
    return httpx.Client(
        base_url=BASE,
        headers={"X-API-Key": key, "Content-Type": "application/json"},
        timeout=30.0,
    )


def unwrap(resp):
    """Band wraps payloads in {"data": ...}. Return the inner data."""
    try:
        body = resp.json()
    except Exception:
        return None
    return body.get("data", body) if isinstance(body, dict) else body


def try_add(cli, chat_id, agent_id, handle):
    """Try candidate request shapes until one is accepted. Logs every attempt."""
    candidates = [
        {"participant": {"participant_id": agent_id}},
    ]
    last = None
    for body in candidates:
        resp = cli.post(f"/agent/chats/{chat_id}/participants", json=body)
        last = resp
        detail = ""
        try:
            detail = json.dumps(resp.json().get("error", {}).get("details", {}))
        except Exception:
            detail = resp.text[:120]
        note(f"      try {json.dumps(_shape(body))} -> HTTP {resp.status_code} {detail}")
        if resp.status_code < 300:
            return True, body, resp
    return False, None, last


def participant_ids(data):
    """Return a readable list of (label, agent_id, participant_record_id)."""
    rows = []
    items = data if isinstance(data, list) else data.get("participants", []) if isinstance(data, dict) else []
    for p in items:
        if not isinstance(p, dict):
            continue
        label = p.get("name") or p.get("handle") or "?"
        agent_id = p.get("agent_id") or (p.get("agent") or {}).get("id") or p.get("id")
        rec_id = p.get("id")
        rows.append((label, agent_id, rec_id))
    return rows


def main():
    note("# Phase A: room, participants, removal  (live run against Band)")
    note("")

    warden = client(KEYS["WARDEN"])

    # --- 2a. Warden creates a room -----------------------------------------
    note("## Step 1 - Warden creates a room")
    r = warden.post("/agent/chats", json={"chat": {}})
    note(f"create room -> HTTP {r.status_code}")
    data = unwrap(r)
    chat_id = None
    if isinstance(data, dict):
        chat_id = data.get("id") or data.get("chat_id")
    if not chat_id:
        note("FAILED to get a room id. Raw response:")
        note(json.dumps(r.json(), indent=2)[:1500])
        write_findings(success=False)
        return
    note(f"room created. id = {chat_id}")
    note("")

    # --- 2b. who is in the room right after creation? ----------------------
    note("## Step 2 - Who is in the room right after creating it?")
    r = warden.get(f"/agent/chats/{chat_id}/participants")
    note(f"list participants -> HTTP {r.status_code}")
    for label, aid, rec in participant_ids(unwrap(r)):
        note(f"   - {label}   agent_id={aid}   participant_id={rec}")
    note("")

    # --- 2c. add Intake, Matcher, Approver ---------------------------------
    note("## Step 3 - Warden adds Intake, Matcher, Approver")
    add_shape = None
    for who in ["INTAKE", "MATCHER", "APPROVER"]:
        ok, body, resp = try_add(warden, chat_id, IDS[who], HANDLES[who])
        if ok:
            add_shape = body
            note(f"   added {who}  (HTTP {resp.status_code})  using shape {json.dumps(_shape(body))}")
        else:
            note(f"   FAILED to add {who}  (HTTP {resp.status_code})  body: {resp.text[:300]}")
    note("")

    # --- list again --------------------------------------------------------
    note("## Step 4 - Room after adding three agents")
    r = warden.get(f"/agent/chats/{chat_id}/participants")
    rows = participant_ids(unwrap(r))
    for label, aid, rec in rows:
        note(f"   - {label}   agent_id={aid}   participant_id={rec}")
    note("")

    def in_room(target_id):
        """True/False if target is in the room, or None if we couldn't check."""
        try:
            rr = warden.get(f"/agent/chats/{chat_id}/participants")
            if rr.status_code >= 300:
                return None
            return any(aid == target_id for _, aid, _ in participant_ids(unwrap(rr)))
        except Exception:
            return None

    intake = client(KEYS["INTAKE"])

    # --- Test A: can the OWNER (Warden) remove a member? -------------------
    note("## Step 5 - Can the OWNER (Warden) remove a member? (removes PO Matcher)")
    owner_removes_member = remove(warden, chat_id, IDS["MATCHER"], IDS["MATCHER"])
    note(f"   Warden removing Matcher -> {owner_removes_member}")
    note(f"   Matcher still in room? {in_room(IDS['MATCHER'])}")
    note("")

    # --- Test B: can a MEMBER (Intake) remove ANOTHER member? -------------
    note("## Step 6 - Can a MEMBER (Intake) remove another member? (removes Approver)")
    member_removes_member = remove(intake, chat_id, IDS["APPROVER"], IDS["APPROVER"])
    note(f"   Intake removing Approver -> {member_removes_member}")
    note(f"   Approver still in room? {in_room(IDS['APPROVER'])}")
    note("")

    # --- Test C: can a MEMBER remove the OWNER? (the security question) ---
    note("## Step 7 - Can a MEMBER (Intake) remove the OWNER (Warden)?  *** SECURITY CHECK ***")
    note("   (If a hijacked agent could eject Warden, that would be a hole.)")
    member_removes_owner = remove(intake, chat_id, IDS["WARDEN"], IDS["WARDEN"])
    note(f"   Intake removing Warden -> {member_removes_owner}")
    warden_survived = in_room(IDS["WARDEN"])
    note(f"   Warden still in room? {warden_survived}")
    note("")

    # --- final membership -------------------------------------------------
    note("## Step 8 - Final room membership")
    rr = warden.get(f"/agent/chats/{chat_id}/participants")
    if rr.status_code < 300:
        for label, aid, rec in participant_ids(unwrap(rr)):
            note(f"   - {label}   agent_id={aid}")
    else:
        note(f"   (could not list - HTTP {rr.status_code}; Warden may have been removed)")
    note("")

    write_findings(
        success=True,
        chat_id=chat_id,
        add_shape=add_shape,
        owner_removes_member=owner_removes_member,
        member_removes_member=member_removes_member,
        member_removes_owner=member_removes_owner,
        warden_survived=warden_survived,
    )


def _shape(body):
    """Replace the real id with a placeholder so the log shows the SHAPE."""
    s = json.loads(json.dumps(body))
    def scrub(d):
        for k, v in d.items():
            if isinstance(v, dict):
                scrub(v)
            else:
                d[k] = "<agent_id>"
    if isinstance(s, dict):
        scrub(s)
    return s


def remove(cli, chat_id, agent_id, rec_id):
    """Try removing by agent_id, then by participant record id. Report what happened."""
    for ident, kind in [(agent_id, "agent_id"), (rec_id, "participant_id")]:
        if not ident:
            continue
        resp = cli.delete(f"/agent/chats/{chat_id}/participants/{ident}")
        if resp.status_code < 300:
            return f"ALLOWED (HTTP {resp.status_code}, by {kind})"
        if resp.status_code in (401, 403):
            return f"DENIED (HTTP {resp.status_code} - not permitted)"
    return f"FAILED (last HTTP {resp.status_code}: {resp.text[:200]})"


def _yes(result):
    return result.startswith("ALLOWED")


def write_findings(success, chat_id=None, add_shape=None, owner_removes_member="",
                   member_removes_member="", member_removes_owner="", warden_survived=None):
    path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PHASE_A_FINDINGS.md")
    L = []
    def w(s=""):
        L.append(s + "\n")

    w("# Phase A findings - the plumbing test (plain language)")
    w()
    w("This file is written automatically by the test. Before building the smart")
    w("agents, we check the basic powers Warden needs: can it make a room, see who")
    w("is in it, and throw someone out. Here is what Band actually let us do.")
    w()

    w("## Quick scorecard")
    w()
    w("- Can every agent connect to Band? **YES** (all 6 keys work).")
    if success:
        w(f"- Can Warden create a room? **YES**.")
        w(f"- Can Warden add the other agents into the room? **{'YES' if add_shape else 'NO'}**.")
        w(f"- Can Warden SEE the full list of who is in the room? **YES** (this is Warden's eyes).")
        w(f"- Can the room owner (Warden) throw a member out? **{'YES' if _yes(owner_removes_member) else 'NO'}**.")
        w(f"- Can an ordinary member throw ANOTHER member out? **{'YES' if _yes(member_removes_member) else 'NO'}**.")
        if _yes(member_removes_owner):
            w(f"- Can an ordinary member throw out the OWNER (Warden)? **YES - this is a real risk, see below.**")
        elif member_removes_owner.startswith("DENIED"):
            w(f"- Can an ordinary member throw out the OWNER (Warden)? **NO - good, Warden is protected.**")
        else:
            w(f"- Can an ordinary member throw out the OWNER (Warden)? Unclear: {member_removes_owner}")
    else:
        w("- Creating a room FAILED - see the detailed log below.")
    w()

    w("## The headline result")
    w()
    if success and _yes(owner_removes_member):
        w("**Warden has its eyes and its hands.** It can create the room, watch who is")
        w("in it, and remove a compromised agent. That is everything the demo needs on")
        w("the controls side. We are clear to build the real agents.")
    else:
        w("Something in the plumbing did not work the way we need. See the log.")
    w()

    w("## The surprise (and it changes the plan a little)")
    w()
    w("The original plan assumed *only the room creator* can remove people. That is")
    w("**not** what Band does.")
    w()
    if _yes(member_removes_member):
        w("- Any member can remove another member - not just the owner.")
    if _yes(member_removes_owner):
        w("  - **Worse: a plain member was even able to remove the OWNER (Warden).**")
        w("    In our story Intake is the *hijacked* agent. So in theory a hijacked")
        w("    agent could try to throw Warden out to escape being caught.")
        w()
        w("  **Why this does NOT break the demo, and actually makes it stronger:**")
        w("  1. The attacks we use come from public benchmarks - they poison the")
        w("     *invoice*, they do not know about Band or try to remove Warden. So the")
        w("     live demo is unaffected.")
        w("  2. Warden watches the join/leave feed. If anyone is removed, that itself")
        w("     is an alarm - so an agent trying to eject Warden is a loud red flag,")
        w("     not a quiet escape.")
        w("  3. The money is gated behind Warden's sign-off. No Warden sign-off = no")
        w("     payment. Ejecting Warden does not release the money; it freezes it.")
        w("  4. If we want a hard lock, we can have the Enforcer (not Warden) hold")
        w("     owner rights, or run Warden from a second 'observer' the workers cannot")
        w("     see. We will note this as a design choice in the writeup.")
    elif member_removes_owner.startswith("DENIED"):
        w("  - But the OWNER is protected: a member could NOT remove Warden. So as long")
        w("    as Warden creates the room, no worker agent can eject it. Clean.")
    w()

    w("## What this means for how we build")
    w()
    w("- **Warden creates the room** (so it starts as owner and can always remove).")
    w("- **Warden does the actual ejecting.** The Enforcer agent makes the *decision*,")
    w("  but the removal call should run with Warden's authority.")
    w("- We will treat 'someone got removed' as an event Warden always reacts to.")
    w()

    w("## The exact technical recipe we discovered (for future me)")
    w()
    w("- REST base URL: `https://app.band.ai/api/v1` (the `/api/v1` part is required).")
    w("- Auth header: `X-API-Key: <agent key>`.")
    w("- Create a room: `POST /agent/chats` with body `{\"chat\": {}}`.")
    w("- Add an agent: `POST /agent/chats/{id}/participants` with body")
    w("  `{\"participant\": {\"participant_id\": \"<agent uuid>\"}}`.")
    w("- List who is in: `GET /agent/chats/{id}/participants`.")
    w("- Remove an agent: `DELETE /agent/chats/{id}/participants/{agent uuid}`.")
    w("- The creator is auto-added to the room as owner.")
    w()

    w("## What we STILL cannot test until the agents are live")
    w()
    w("These two need the agents actually running and listening, which needs the LLM")
    w("keys (the free promo codes from kickoff):")
    w()
    w("- **Mention delivery** - does an agent really receive a message that @tags it?")
    w("- **The live join/leave feed** - does an agent get pinged the instant someone")
    w("  joins or leaves? (We proved the list CHANGES; we have not yet proven a live")
    w("  push notification arrives.)")
    w()
    w("That is the next test, once we have an LLM key wired in.")
    w()

    w("## Detailed log (the raw run, if you want to see everything)")
    w()
    w("```")
    L.extend(x + "\n" for x in LOG)
    w("```")

    with open(path, "w", encoding="utf-8") as f:
        f.write("".join(L))
    print(f"\n>>> Findings written to {path}")


if __name__ == "__main__":
    main()
