# Data-free matched-search cell coordinator

## Question

Can one shared coordinator execute either random or Bayesian search through an
identical 32-proposal record, support, finding, accounting, checkpoint, and
resume contract before any private integration is attempted?

## Configuration

- one cell per method, track, seed, and scenario identity;
- the frozen 32-proposal random/Sobol/qLogNEHVI proposal core;
- one supplied, validated empirical-support model fingerprint;
- five sealed Draft 2020-12 record types;
- coordinator-derived support, objectives, three constraints, findings, and
  physical costs;
- exact ordered-history links for every selection step; and
- synthetic evaluator and optimizer seams only.

## Result

The focused data-free suite passed 17 tests. Both methods completed exactly 32
proposals through the same coordinator and accounting schema. The synthetic
Bayesian cell deliberately returned the same post-initialization candidate 24
times; all duplicates consumed budget and 23 were correctly linked to earlier
instances. Accepted proposals with rejected feature records still retained
both controller evaluations and all six physical reruns.

An interrupted Bayesian cell resumed from proposal 11 and matched the
uninterrupted run in every proposal decision, raw attempt, feature, support,
objective, constraint, finding, and cost field. A completed resume performed no
scenario loading or evaluator work while still reproducing every selection and
reconstructing the report.

Resealed changes to support scores, objectives, constraints, findings, cost,
parameters, selection decisions, observation-history links, and completed
metrics were rejected. Strict finite JSON, environment locking, unexpected-file
rejection, aggregate-only summaries, private path enforcement, all five public
schemas, complete-budget behavior after findings, and rejected-proposal
retention passed.

The focused suite completed locally in under five seconds. This is a feasibility
observation on synthetic evidence, not a search-performance benchmark.

## Interpretation

The experiment engine now has a durable method-neutral unit that can be
scheduled independently without changing scientific identity or allowing an
evaluator to define method-specific outcomes. This still does not prove that
the existing Waymax pipeline supplies the new feature evidence correctly.

The next gate is the predeclared one-scenario, two-proposal private integration
smoke test through a bounded adapter. No H1, H2, H3, planner-performance, or
safety conclusion follows from this result.
