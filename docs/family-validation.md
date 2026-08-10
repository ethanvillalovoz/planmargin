# Lead-braking family-validation protocol

Issue #17 decides whether the ten selected lead-vehicle-braking scenarios form
a feasible two-dimensional search space before random or Bayesian search is
implemented. The decision is based on a fixed grid and predeclared gates, not
on whether the run happens to discover a controller failure.

## Search parameters

```text
theta = [braking_onset_delay_s, speed_multiplier]
```

The fixed feasibility grid is:

- braking-onset delay: `0.0`, `0.2`, and `0.5` seconds;
- post-onset speed multiplier: `0.75`, `0.80`, and `1.00`; and
- nine points per scenario across ten scenarios.

The parameter bounds are `[0.0, 0.5]` seconds and `[0.75, 1.00]`. A
mutation-only pilot finalized these values before any controller-family result
was inspected. Most selected leads are already entering their braking window
at the current state, so advancing onset would alter immutable observed
history. Longer delays frequently require route geometry beyond the recorded
horizon.

## Mutation construction

The generator computes route progress from the lead vehicle's contiguous
recorded-valid future prefix. It identifies the first one-second window with a
speed drop of at least `1.0 m/s`, at least 80% non-increasing steps, and a
specific decreasing step. The detected braking profile is delayed by the
configured number of 100 ms steps and blended with the recorded profile over
two seconds. The post-onset multiplier uses the same smooth transition.

The resulting speed schedule is integrated into route progress and
interpolated only along the recorded spatial route. Mutations are rejected if
they exceed the available route, introduce a speed, acceleration, or jerk
violation beyond both the declared bound and any pre-existing recorded value,
or deviate from the route. Observed history and the validity mask never change.

The identity point `[0.0, 1.0]` bypasses resampling and must reproduce every
trajectory field exactly. A lead that naturally leaves the recorded scene may
retain its invalid tail; the mutation operates only on the contiguous valid
prefix.

## Continuous interaction metrics

Every accepted tested and reference rollout records:

- minimum signed separation between oriented SDC and lead-vehicle boxes;
- minimum longitudinal time to collision using bumper gap and closing speed;
  and
- the number of jointly valid states supporting those values.

Positive signed separation means disjoint boxes, zero means touching, and a
negative value is separating-axis penetration depth. TTC is absent when the
lead is not ahead and closing. These continuous metrics expose severity
variation even when binary overlap and offroad outcomes remain unchanged.

## Predeclared decision gates

The family receives a `go` decision only if all gates pass:

1. at least 8 of 10 original scenarios pass both controllers;
2. at least 60% of the 80 non-identity attempts pass core and scenario gates;
3. every accepted attempt reproduces exactly across repeated runs;
4. at least 80% of accepted non-identity attempts change the tested-controller
   trajectory; and
5. at least five eligible scenarios show a tested-controller minimum-separation
   range of `0.5 m` or a finite-TTC range of `0.5 s`.

A policy-specific failure is counted only when the tested controller fails and
the reference succeeds at the same accepted point. Its count is descriptive,
not a feasibility gate.

## Running locally

The ignored Stage 0 selection manifest must exist. Then run:

```bash
uv run --frozen planmargin-validate-lead-braking-family \
  --manifest artifacts/stage-0/scenario-selection.json \
  --output artifacts/family-validation/lead-braking-family.json
```

The terminal receives only aggregate counts and the decision. The private JSON
retains scenario identifiers, object indices, mutation records, rejection
reasons, controller outcomes, continuous metrics, hashes, timings, and
provenance. It must remain under `artifacts/` and must never be committed.

## Limitations

This ordered training sample is suitable only for feasibility work. The
kinematic and map gates do not replace a learned behavioral-likelihood model.
Both controllers share Waymax's IDM implementation. A `go` decision authorizes
implementation of a random-search baseline; it is not a planner-performance or
safety claim.
