# Lead-braking family validation

## Question

Do the ten selected lead-vehicle-braking scenarios support a deterministic,
two-dimensional, continuously measurable mutation space that is feasible
enough to justify implementing search algorithms?

## Configuration

- WOMD Motion Dataset 1.3.1 training split;
- the ordered ten-scenario Stage 0 lead-braking feasibility set;
- braking-onset delays of `0.0`, `0.2`, and `0.5` seconds;
- speed multipliers of `0.75`, `0.80`, and `1.00`;
- 90 total grid attempts, including ten identity controls;
- tested and conservative-reference Waymax IDM configurations;
- two identical runs for mutation validation and each controller rollout; and
- the five gates predeclared in the
  [protocol](../docs/family-validation.md).

## Result

The clean run at Git revision `e3a2646` produced a **go** decision. All five
family gates passed:

| Gate | Threshold | Observed |
| --- | ---: | ---: |
| Original eligibility | at least 8 of 10 | 9 of 10 |
| Non-identity mutation validity | at least 60% | 48 of 80, exactly 60% |
| Accepted-attempt determinism | 100% | 100% |
| Tested-controller response | at least 80% | 100% |
| Scenarios with continuous severity variation | at least 5 | 8 |

All ten identity mutations reproduced their recorded trajectory fields
exactly. Nine passed the full scenario gate; one retained a recorded target
offroad outcome and was rejected without altering the source trajectory.

Across all 90 points, 57 passed every mutation and scenario gate. Twenty-six
were rejected because delayed progress exhausted the recorded route, and seven
were rejected because the mutated target went offroad. No accepted point
produced a tested-controller failure with reference-controller success.

The run took 675.90 seconds, approximately 11.27 minutes, and observed
928,497,664 bytes of peak process RSS, approximately 0.86 GiB. These are local
feasibility observations, not controlled performance benchmarks.

## Interpretation

The family is suitable for implementing the uniform-random baseline: enough
non-identity points remain valid, every accepted run is reproducible, every
accepted non-identity point changes the tested trajectory, and continuous
separation/TTC evidence varies across most eligible scenarios.

The validity result sits exactly on the predeclared 60% boundary. Search code
must therefore retain invalid attempts, model or report route-exhaustion and
offroad constraints explicitly, and avoid presenting the space as uniformly
feasible. The absence of a policy-specific failure in this coarse grid is not
a negative search result; failure discovery was not a family-feasibility gate.

## Limitations and next decision

The ordered training set is not representative, and kinematic/map checks are
not a learned behavioral-realism model. Both controllers use the same Waymax
IDM implementation with different configurations. This result makes no claim
about the production Waymo Driver or planner performance.

The next milestone is the uniform-random-search baseline with a fixed rollout
budget, complete invalid-attempt accounting, deterministic checkpointing, and
the same accepted-mutation and controller-evaluation contract.

The complete report contains restricted scenario identifiers, object indices,
per-point metrics, hashes, and controller outcomes. It remains only under the
ignored `artifacts/family-validation/` path.
