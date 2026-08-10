# Stage 0: tested and reference controller comparison

## Question

Can PlanMargin run distinct tested and conservative-reference configurations
on identical original and mutated non-ego inputs, export their trajectories,
and evaluate each outcome independently and reproducibly?

## Configuration

- one candidate from the private ten-scenario Stage 0 manifest;
- the accepted `0.90` route-progress speed mutation;
- Waymax default IDM as the tested policy;
- the versioned conservative IDM configuration documented in the
  [protocol](../../docs/controller-comparison.md) as the technical reference;
- original and mutated variants for both controllers; and
- two deterministic 80-step runs for every controller/variant pair.

## Result

The comparison harness passed all acceptance checks. The tested policy passed
the original scenario, both controllers received matching non-SDC input hashes
for each variant, the input scenarios remained unchanged, all four exported
SDC trajectories contained the complete 81 states, and all repeated trajectory
hashes matched. The two configurations produced distinct outputs and both
responded to the mutation.

Both controllers passed both the original and mutated variants. Therefore this
run did **not** produce a tested-policy failure or a policy-specific avoidable
failure. That negative result is retained rather than reframed as evidence of
planner quality or safety.

The ignored local report contains exact scenario provenance, controller and
input hashes, per-step trajectories, timings, and scalar outcomes. Restricted
and per-scenario derived values are intentionally excluded here.

## Interpretation and limitations

The result validates the comparison machinery and independent outcome logic,
not the research hypothesis. Both configurations share Waymax's IDM
implementation, and this is one feasibility case. A passing technical
reference is not a human, legal, or universal avoidability standard. Later
experiments must use predeclared mutation search, held-out scenarios, and a
stronger independent reference before making broader claims.
