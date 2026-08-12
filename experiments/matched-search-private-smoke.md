# Bounded private matched-search integration smoke test

## Question

Can the real Waymax mutation, empirical-support, and controller pipeline supply
the raw evidence required by the method-neutral coordinator, in the frozen
order, without expanding beyond one scenario and two proposals?

## Predeclared configuration

- random method, natural track, seed 0;
- scenario selection order 1 from the fixed ten-scenario training manifest;
- proposal indices 0 and 1 from the frozen stateless PCG64 sequence;
- the validated private empirical-support model;
- two deterministic executions for each original and mutated controller; and
- a zero-new-proposal resume immediately after the two checkpoints.

## Result

The corrected smoke test passed from a clean source revision. It produced
exactly two selection records and two evaluated proposal records. Both
proposals passed mutation and scenario validation, produced accepted behavior
features, passed empirical support, and retained tested and reference
controller evidence.

The instrumented adapter verified the required order for both attempts:
mutation, scenario validation, feature extraction, support scoring, tested
controller, then reference controller. The coordinator independently reloaded
and reproduced all derived proposal fields. The zero-new-proposal resume
repeated no evaluator or controller work.

The smoke accounted for four original-controller physical rollouts and twelve
proposal-related physical rollouts, for sixteen total. All six durable records
validated against their public Draft 2020-12 schemas. The private manifest
recorded the exact source commit and a clean worktree, and the entire artifact
tree remained ignored.

The first integration attempt stopped before writing a proposal because the
underlying mutation audit reported its complete fixed configuration where the
coordinator requires only the two selected search coordinates. The adapter now
normalizes that field while the immutable fixed configuration remains in the
cell manifest. A data-free regression test covers this boundary.

## Interpretation

This closes the private integration gate. It is evidence that the components
compose correctly for the bounded probe, not evidence of search quality,
planner quality, a qualifying failure, or any hypothesis outcome. No private
identifier, source location, feature vector, support value, trajectory hash,
controller outcome, or per-proposal finding is included here.

The next milestone is the predeclared headway-regression original-eligibility
check before any complete matched-search cell is authorized.
