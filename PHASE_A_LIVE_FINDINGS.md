# Phase A (live) findings - mention delivery + join/leave feed

These are the two things that needed a real, connected agent (not just REST). We ran the Intake agent for real and poked it from Warden.

## Scorecard

- Does a @mentioned message actually reach the agent? **YES**
- Does the agent get pinged when someone JOINS the room? **YES**
- Does the agent get pinged when someone LEAVES the room? **YES**

## What this means

All three work. This is the rest of Warden's **eyes**: it will reliably receive every handoff that tags it, and it sees the room's membership change live (so a hijacked agent cannot quietly pull in a helper or slip away without Warden noticing). Phase A is fully complete - we can build the real crew now.

## Raw events the listener recorded

```
MESSAGE: @[[4168bd39-3db7-463a-8823-9e5c20b780f8]] please reply ACK
JOINED: ParticipantAddedEvent(type='participant_added', room_id='719362c5-e1a3-411d-829d-59901bbf4937', payload=ParticipantAddedPayload(id='2409b71c-205e-4dd1-8ea1-c8a79b98ce60', name='Approver', type='Agent', is_remote=True, is_external=True, handle='parshiv.kapoor/approver', status='inactive', description='Approves payments that match and are under the limit', role='member'), raw=None)
LEFT: ParticipantRemovedEvent(type='participant_removed', room_id='719362c5-e1a3-411d-829d-59901bbf4937', payload=ParticipantRemovedPayload(id='2409b71c-205e-4dd1-8ea1-c8a79b98ce60', handle='parshiv.kapoor/approver', name='Approver', status='inactive', type='Agent', description='Approves payments that match and are under the limit', role='member', is_external=True), raw=None)
```
