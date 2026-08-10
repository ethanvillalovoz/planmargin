# Project specification

## Objective

Given a recorded driving scenario, search a bounded space of realistic non-ego behavior changes for the smallest mutation that causes a tested planner to fail while a conservative reference controller succeeds.

The project evaluates a testing methodology. It does not make claims about the production Waymo Driver, human driving ability, or legal responsibility.

## Research question

> Can realism-constrained Bayesian optimization discover avoidable, policy-specific failures with fewer closed-loop simulations than uniform random search?

## Hypotheses

- **H1 — efficiency:** Bayesian search requires fewer rollouts than random search to find the first valid failure under an equal budget.
- **H2 — minimality:** Bayesian search finds failures with smaller normalized mutations.
- **H3 — validity:** Improved search efficiency does not reduce the physical, map, or behavioral realism pass rate.

If the evidence does not support these hypotheses, the negative result will be reported rather than hidden.

## Version-one scope

### Dataset and simulator

- Waymo Open Motion Dataset training data for development
- A held-out validation subset for final comparisons
- Waymax for deterministic closed-loop rollout and built-in evaluation metrics

### Initial scenario family

The Stage 0 feasibility family is lead-vehicle braking involving the
self-driving car and one same-route lead vehicle.

A bounded one-shard probe found seven strict left-turn/oncoming candidates,
fewer than the ten required by the predeclared selection protocol, so the
lead-braking fallback was activated on August 9, 2026. Unprotected left turns
remain the preferred later extension but are not mixed into the feasibility
set. See [the selection protocol](scenario-selection.md).

### Mutation parameters

The fallback search space is intentionally two-dimensional:

```text
theta = [braking_onset_offset, speed_multiplier]
```

The changed lead vehicle must remain on its recorded spatial route. If the
left-turn family is revisited, its corresponding search space will use arrival
time offset and speed multiplier.

The first implemented dimension is a speed multiplier in `[0.75, 1.00]`. It
ramps from the recorded current state, scales route progress, and rejects
outputs that exceed explicit acceleration or jerk limits. The braking-onset
dimension remains future work. See the
[speed-mutation protocol](speed-mutation.md).

### Tested and reference controllers

The feasibility spike will compare:

- Waymax's built-in route-following IDM policy;
- an explicitly parameterized conservative IDM technical reference; and
- optionally, a modified planner configuration representing a regression.

The Stage 0 reference lowers desired speed and acceleration while increasing
spacing, time headway, braking authority, and lookahead. Both current
controllers share Waymax's IDM implementation, so this first comparison tests
configuration-specific behavior rather than independent planning algorithms.
The reference is a conservative technical controller, not a legal or
human-driver model. See the
[controller-comparison protocol](controller-comparison.md). A custom controller
or small learned planner may be added later, but neither is required for the
first harness result.

## Acceptance gates

A discovered failure is valid only if it passes every gate:

1. **Original pass:** the tested planner succeeds before mutation.
2. **Initial validity:** the modified scenario does not begin in overlap or an invalid state.
3. **Physical feasibility:** motion satisfies configured speed, acceleration, jerk, yaw-rate, and continuity bounds.
4. **Map feasibility:** the modified actor remains on its route and inside valid road boundaries.
5. **Behavioral realism:** motion features remain sufficiently likely under distributions estimated from real WOMD trajectories.
6. **Candidate failure:** the tested planner collides, leaves the road, violates route constraints, or crosses a predefined critical-risk threshold.
7. **Reference success:** the reference controller avoids the same event under the identical non-ego trajectory.
8. **Reproducibility:** deterministic reruns agree; stochastic policies must exceed a declared failure probability.

Formally, for planner `P`, reference `R`, scenario `s`, and mutation `theta`:

```text
P passes s
mutation(s, theta) is plausible
P fails mutation(s, theta)
R passes mutation(s, theta)
```

## Metrics

### Safety and behavior

- overlap or collision
- off-road and wrong-way indicators
- route progression and route deviation
- minimum signed separation
- minimum time to collision
- braking, acceleration, and jerk
- traffic-light violation where supported

### Search quality

- valid failure discovery rate under a fixed rollout budget
- median simulations to first valid failure
- minimum normalized mutation distance
- realism pass rate
- reference-controller avoidability rate
- number and diversity of discovered failure families

### Engineering

- scenarios processed per second
- Waymax rollout steps per second
- C++ versus Python hot-path performance
- scaling with local worker count
- deterministic reproduction rate
- scenario debugger load latency

## Search methods

### Baseline

Uniform random search within identical bounds and constraints.

### Proposed method

Constrained Bayesian optimization using PyTorch/BoTorch on CPU or MPS. A smooth search objective will reward severity and penalize mutation distance and realism violations:

```text
score(theta) =
    severity(theta)
  - lambda * normalized_mutation_distance(theta)
  - mu * realism_penalty(theta)
```

The final acceptance gates remain authoritative; the scalar search score cannot by itself certify a valid failure.

## Stage 0 feasibility exit criteria

Stage 0 is complete when the repository can:

1. Load at least ten WOMD scenarios into Waymax.
2. Replay an original scenario deterministically.
3. Apply one bounded non-ego speed or timing mutation.
4. Run both tested and reference controllers.
5. Export trajectory and metric records.
6. Render one original-versus-mutated comparison.
7. Report local runtime and memory observations.

The result of Stage 0 determines the initial scenario family and prevents premature investment in the full platform.

## Non-goals

Version one will not:

- evaluate the production Waymo Driver;
- operate a real vehicle;
- infer legal responsibility;
- build a perception stack;
- edit raw camera or LiDAR observations;
- require paid compute;
- use an LLM inside the planner or metric computation;
- make Gaussian splatting part of the critical path; or
- process the entire dataset solely to claim scale.
