# Controlled headway-regression original-eligibility gate

## Question

Does the intentionally weakened `1.0 s` safe-time-headway tested controller
retain enough valid original scenarios to support a controlled-regression
matched-search comparison?

## Predeclared decision

- ten fixed training scenarios;
- tested controller differs from the natural tested controller only in its ID
  and safe time headway;
- unchanged conservative reference;
- two deterministic executions per controller and scenario;
- original eligibility requires both controller outcomes to succeed; and
- `go` requires at least 8 of 10 eligible originals plus complete deterministic
  integrity.

No replacement configuration is allowed after a `no_go`.

## Result

The gate returned `no_go`. Four of ten originals were eligible, below the
required eight. All ten scenarios completed, all 40 physical rollouts were
deterministic, physical cost reconciled, and all integrity gates passed.

Twelve durable private records—the run manifest, ten originals, and aggregate
report—validated against their public Draft 2020-12 schemas. The manifest
recorded the exact clean source revision. Completed resume reconstructed and
validated the result without loading WOMD or evaluating a controller.

## Interpretation

This is a valid negative result. The controlled-regression track is not
authorized for mutated proposals or complete search cells under protocol
version one, and no alternate headway will be tried. The result does not alter
the natural track, support model, mutation bounds, search methods, or
hypotheses, and makes no planner-performance claim.
