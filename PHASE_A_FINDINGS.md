# Phase A findings - the plumbing test (plain language)

This file is written automatically by the test. Before building the smart
agents, we check the basic powers Warden needs: can it make a room, see who
is in it, and throw someone out. Here is what Band actually let us do.

## Quick scorecard

- Can every agent connect to Band? **YES** (all 6 keys work).
- Can Warden create a room? **YES**.
- Can Warden add the other agents into the room? **YES**.
- Can Warden SEE the full list of who is in the room? **YES** (this is Warden's eyes).
- Can the room owner (Warden) throw a member out? **YES**.
- Can an ordinary member throw ANOTHER member out? **YES**.
- Can an ordinary member throw out the OWNER (Warden)? **NO - good, Warden is protected.**

## The headline result

**Warden has its eyes and its hands.** It can create the room, watch who is
in it, and remove a compromised agent. That is everything the demo needs on
the controls side. We are clear to build the real agents.

## The surprise (and it changes the plan a little)

The original plan assumed *only the room creator* can remove people. That is
**not** what Band does.

- Any member can remove another member - not just the owner.
  - But the OWNER is protected: a member could NOT remove Warden. So as long
    as Warden creates the room, no worker agent can eject it. Clean.

## What this means for how we build

- **Warden creates the room** (so it starts as owner and can always remove).
- **Warden does the actual ejecting.** The Enforcer agent makes the *decision*,
  but the removal call should run with Warden's authority.
- We will treat 'someone got removed' as an event Warden always reacts to.

## The exact technical recipe we discovered (for future me)

- REST base URL: `https://app.band.ai/api/v1` (the `/api/v1` part is required).
- Auth header: `X-API-Key: <agent key>`.
- Create a room: `POST /agent/chats` with body `{"chat": {}}`.
- Add an agent: `POST /agent/chats/{id}/participants` with body
  `{"participant": {"participant_id": "<agent uuid>"}}`.
- List who is in: `GET /agent/chats/{id}/participants`.
- Remove an agent: `DELETE /agent/chats/{id}/participants/{agent uuid}`.
- The creator is auto-added to the room as owner.

## What we STILL cannot test until the agents are live

These two need the agents actually running and listening, which needs the LLM
keys (the free promo codes from kickoff):

- **Mention delivery** - does an agent really receive a message that @tags it?
- **The live join/leave feed** - does an agent get pinged the instant someone
  joins or leaves? (We proved the list CHANGES; we have not yet proven a live
  push notification arrives.)

That is the next test, once we have an LLM key wired in.

## Detailed log (the raw run, if you want to see everything)

```
# Phase A: room, participants, removal  (live run against Band)

## Step 1 - Warden creates a room
create room -> HTTP 201
room created. id = 6ed1ec8e-cefc-4325-9a28-e55380bd614e

## Step 2 - Who is in the room right after creating it?
list participants -> HTTP 200
   - Warden   agent_id=467cf9ea-6414-456f-8d98-260a597952e1   participant_id=467cf9ea-6414-456f-8d98-260a597952e1

## Step 3 - Warden adds Intake, Matcher, Approver
      try {"participant": {"participant_id": "<agent_id>"}} -> HTTP 201 {}
   added INTAKE  (HTTP 201)  using shape {"participant": {"participant_id": "<agent_id>"}}
      try {"participant": {"participant_id": "<agent_id>"}} -> HTTP 201 {}
   added MATCHER  (HTTP 201)  using shape {"participant": {"participant_id": "<agent_id>"}}
      try {"participant": {"participant_id": "<agent_id>"}} -> HTTP 201 {}
   added APPROVER  (HTTP 201)  using shape {"participant": {"participant_id": "<agent_id>"}}

## Step 4 - Room after adding three agents
   - Approver   agent_id=2409b71c-205e-4dd1-8ea1-c8a79b98ce60   participant_id=2409b71c-205e-4dd1-8ea1-c8a79b98ce60
   - Invoice Intake   agent_id=4168bd39-3db7-463a-8823-9e5c20b780f8   participant_id=4168bd39-3db7-463a-8823-9e5c20b780f8
   - Warden   agent_id=467cf9ea-6414-456f-8d98-260a597952e1   participant_id=467cf9ea-6414-456f-8d98-260a597952e1
   - PO Matcher   agent_id=be643dbb-33b8-46f4-82e6-3a13356ac545   participant_id=be643dbb-33b8-46f4-82e6-3a13356ac545

## Step 5 - Can the OWNER (Warden) remove a member? (removes PO Matcher)
   Warden removing Matcher -> ALLOWED (HTTP 200, by agent_id)
   Matcher still in room? False

## Step 6 - Can a MEMBER (Intake) remove another member? (removes Approver)
   Intake removing Approver -> ALLOWED (HTTP 200, by agent_id)
   Approver still in room? False

## Step 7 - Can a MEMBER (Intake) remove the OWNER (Warden)?  *** SECURITY CHECK ***
   (If a hijacked agent could eject Warden, that would be a hole.)
   Intake removing Warden -> DENIED (HTTP 403 - not permitted)
   Warden still in room? True

## Step 8 - Final room membership
   - Invoice Intake   agent_id=4168bd39-3db7-463a-8823-9e5c20b780f8
   - Warden   agent_id=467cf9ea-6414-456f-8d98-260a597952e1

```
