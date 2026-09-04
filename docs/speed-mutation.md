# Stage 0 bounded speed-mutation protocol

Issue #2 introduces the first counterfactual transformation: change the future
speed of one selected non-ego lead vehicle while keeping its observed history
and recorded spatial route fixed.

## Contract

For the selected actor, the transformation:

1. preserves every trajectory field through Waymax timestep 10;
2. requires a finite, contiguous future route;
3. ramps a configured speed multiplier from `1.0` over a fixed number of steps;
4. scales each recorded route segment by that multiplier to produce new route
   progress;
5. interpolates position and heading on the recorded polyline; and
6. rejects the candidate if any validation gate fails.

The default Stage 0 configuration is:

| Parameter                     |                Value |
| ----------------------------- | -------------------: |
| Speed multiplier              |               `0.90` |
| Allowed multiplier range      |       `[0.75, 1.00]` |
| Smoothstep ramp               | `10` steps (`1.0` s) |
| Maximum speed                 |           `40.0 m/s` |
| Maximum absolute acceleration |          `12.0 m/s²` |
| Maximum absolute jerk         |         `100.0 m/s³` |
| Maximum route deviation       |             `0.05 m` |

These Stage 0 thresholds are conservative data-quality guards for 10 Hz WOMD
trajectories, not claims about passenger comfort or a complete
behavioral-realism model.

## Route-progress construction

Let `d[t]` be the distance of recorded route segment `t`, `m[t]` the multiplier
after the smoothstep ramp, and `dt = 0.1 s`. The raw target speed is:

```text
target_speed[t] = d[t] / dt * m[t]
```

The generator cumulatively integrates `target_speed[t] * dt` into route
progress. Position and heading are interpolated at that progress on the
original future polyline. A multiplier of `1.0` is therefore an identity for
the recorded route. The actor cannot leave the end of its recorded route.

## Acceptance and audit record

The data-free core records explicit rejection reasons for invalid dimensions,
lengths, multiplier bounds, route continuity, initial kinematics, route
exhaustion, history changes, and post-generation kinematic or route violations.
Its serializable report contains parameters and scalar metrics but never
trajectory arrays.

The private real-data smoke test additionally requires:

- no initial overlap for the SDC or mutated actor;
- a valid, on-road mutated actor throughout the rollout;
- a complete 80-step Waymax rollout; and
- identical full-trajectory hashes across two runs.

Run it only after producing the ignored local selection manifest:

```bash
uv sync --frozen
uv run --frozen planmargin-speed-mutation-smoke-test \
  --manifest artifacts/stage-0/scenario-selection.json \
  --output artifacts/stage-0/speed-mutation-smoke-test.json
```

The JSON output contains restricted identifiers and per-scenario derived
metrics. It must remain under `artifacts/` and must not be committed.

## Limitations

This first transformation changes route timing for one logged actor. It does
not yet model interactive intent, estimate behavioral likelihood, introduce the
braking-onset dimension, compare tested and reference controllers, or establish
a planner failure. The counterfactual actor still follows a route observed in
hindsight.
