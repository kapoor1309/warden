# Phase B findings — the live runtime test (plain language)

Phase A proved the REST control plane. This proves the two things that
needed a *running* agent: does an @mention push to it, and does a
join/leave push to it.

## Quick scorecard

- Did an @mention reach the running listener at all? **YES**.
- Did a LIVE (post-bootstrap) @mention push to it? **YES**.
- Did a participant JOIN push to the listener? **YES**.
- Did a participant LEAVE push to the listener? **YES**.

## What this means

- Mention delivery works LIVE. Warden can be tagged on every handoff and
  receives it in real time. The design's core assumption holds.
- Join/leave push works. Warden's 'watch for sneaky ejection' backstop is a
  live callback, no polling needed.

Room used: 29dbcc05-1f3f-44ee-a89c-31bbefec8b33
