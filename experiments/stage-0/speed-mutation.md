# Stage 0: bounded lead-vehicle speed mutation

## Question

Can PlanMargin apply a nontrivial speed change to one selected WOMD lead
vehicle, preserve its observed history and route, satisfy the declared
kinematic and map gates, and reproduce the resulting Waymax rollout exactly?

## Configuration

- one candidate from the private ten-scenario Stage 0 selection manifest;
- future-only route-progress speed mutation;
- speed multiplier `0.90`, ramped over one second;
- configured speed, acceleration, jerk, and route-deviation bounds documented
  in the [protocol](../../docs/speed-mutation.md);
- Waymax `StateDynamics` with the SDC controlled by its built-in route-following
  IDM policy;
- 80 future steps and seed 0; and
- two identical local JAX CPU rollouts.

## Result

The smoke test passed. The mutation changed future route progress while leaving
the complete observed history unchanged. It passed the configured speed,
acceleration, jerk, route-deviation, initial-overlap, actor-validity, and
off-road gates. Both full-horizon rollouts produced identical trajectory
hashes.

The ignored local report retains the exact scenario provenance, object index,
scalar per-scenario measurements, environment versions, and trajectory hash.
Those restricted and derived values are intentionally excluded here.

## Interpretation and limitations

This result establishes a deterministic, auditable first counterfactual
transformation. It does not establish behavioral realism, planner failure,
reference-controller avoidability, or a safety conclusion. It is one
feasibility case, not an evaluation sample. The next milestone is to compare a
tested controller and a conservative reference controller under identical
original and mutated actor trajectories.
