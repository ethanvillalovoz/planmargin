# ADR 0011: Command-dropout fault protection

**Status:** Accepted and executed

**Date:** September 2026

## Context

The counterfactual campaign already tested behavior changes, but it did not
exercise a software fault or a protective state transition. A useful behavior
verification tool should show that it can make a fault observable, distinguish
test execution from behavior outcome, and block promotion when a protected path
does not meet a frozen contract.

The experiment must use the ten already selected real WOMD training scenes,
remain deterministic, require no paid compute, and publish no scene identifiers
or trajectories.

## Decision

Use a sustained primary planner-command dropout beginning at simulation step 20
(2.0 seconds). Execute three variants twice per scene:

1. **Baseline:** the primary Waymax IDM policy remains active.
2. **Unprotected:** after fault onset, hold the last commanded pose.
3. **Protected:** after fault onset, switch to a conservative Waymax IDM policy.

Each scene must pass eight frozen gates covering baseline success,
determinism, fault manifestation, protected success, recovered progress, and
exact fault onset. Promotion requires all gates in all ten scenes.

## Corrected fault representation

The first implementation marked the planner action invalid. That did not model
the intended failure: Waymax supplied log-following behavior for the invalid
action, so the unprotected trajectory continued and ten fault-manifestation
gates failed. The no-go was retained locally.

The protocol implementation was corrected before qualification to use a
zero-order hold at the final valid commanded pose. A quantitative progress gate
was added so the test cannot pass merely because trajectory hashes differ. No
passing threshold was relaxed after observing results.

## Result

- 10 real WOMD training scenes
- 60 physical rollouts
- 4,800 Waymax steps
- 10/10 baseline successes
- 10/10 unprotected fault manifestations
- 10/10 protected fallback successes
- 80/80 scene-level gates passed

The aggregate is schema-validated, content sealed, and safe to distribute. The
private trace report remains ignored.

## Consequences

- PlanMargin now demonstrates off-nominal behavior verification with a
  reproducible promotion gate.
- The Operations console can treat the fault experiment as one owned SLO and
  one pipeline stage.
- Remote assistance remains out of scope. The fallback controller is an
  independent research mechanism, not a production AV protection design.
- A second simulator is still required before making any cross-simulator
  agreement claim.
