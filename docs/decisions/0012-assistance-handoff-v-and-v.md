# ADR 0012: Assistance-handoff behavior verification

**Status:** Accepted and executed

**Date:** September 2026

## Context

Command-dropout protection verifies a sustained-fault fallback but does not test
the state transitions around an assistance request and recovery. The additional
protocol must exercise those transitions without claiming to implement a human
remote operator or a production autonomous-vehicle assistance service.

## Decision

Use the same ten deterministic real-WOMD training scenes and the same primary
and conservative Waymax controllers as the sustained-fault study. Inject a
temporary planner-command dropout at 2.0 seconds, emit an assistance request at
fault detection, keep the conservative fallback active for one second, apply a
deterministic resolution signal at 3.0 seconds, and resume the primary
controller.

For each scene, run baseline, unprotected, and assisted variants twice. Require
nine frozen gates:

- baseline success and exact repeatability;
- unprotected fault manifestation and exact repeatability;
- exact assistance-request timestamp;
- exact assistance-resolution timestamp;
- assisted trajectory success;
- meaningful progress recovery;
- exact assisted repeatability.

## Result

- 10 real WOMD training scenes
- 60 physical rollouts
- 4,800 Waymax steps
- 10/10 unprotected fault manifestations
- 10/10 assisted handoff successes
- 10/10 exact request and recovery transition traces
- 90/90 scene-level gates passed

The full trace report remains ignored. The tracked aggregate is schema
validated and content sealed.

## Consequences

- PlanMargin can verify fault, request, fallback, resolution, and recovery as
  distinct observable states.
- The protocol tests an assistance-behavior contract; it does not validate a
  human operator, networking stack, production latency distribution, or Waymo
  Driver behavior.
- Cross-simulator agreement remains an explicit open gap.
