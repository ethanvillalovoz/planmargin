# Deterministic uniform-random search baseline

## Question

Can the frozen uniform-random control execute its complete training-set budget
with deterministic proposals and rollouts, durable accounting for every
attempt, and enough valid mutations to support the later equal-budget Bayesian
comparison?

Whether the run found a policy-specific failure was descriptive and was not
required for the baseline implementation to complete.

## Configuration

- WOMD Motion Dataset 1.3.1 training split;
- the ordered ten-scenario lead-braking feasibility set;
- seed `0` and stateless NumPy `SeedSequence`/`PCG64` proposals;
- 32 proposals per scenario and 320 proposals total;
- braking-onset offsets sampled from `{0.0, 0.1, 0.2, 0.3, 0.4, 0.5}` seconds;
- speed multipliers sampled uniformly from `[0.75, 1.00]`;
- every proposal counted, including core and scenario rejections;
- repeated scenario validation and tested/reference controller rollouts; and
- the frozen [random-search protocol](../docs/random-search.md).

## Result

The clean run at Git revision `26bec13` produced a
**baseline-complete** decision. All six integrity gates passed: the original
and proposal counts were exact, proposal coordinates were unique, original
and accepted rollouts were deterministic, and cost accounting reconciled.

| Measure | Observed |
| --- | ---: |
| Original scenarios eligible under both controllers | 9 of 10 |
| Proposals retained | 320 of 320 |
| Accepted proposals | 194 |
| Full mutation/scenario validity rate | 60.625% |
| Accepted-attempt determinism | 100% |
| Tested-controller response | 100% |
| Qualifying policy-specific failures | 0 |

Ninety-eight proposals were rejected because mutated progress exceeded the
recorded route. Twenty-eight more were rejected because the mutated target
went offroad. These 126 rejected proposals remain in the primary search budget
and private audit trail.

The complete run used 1,260 physical deterministic rollouts and 100,800 Waymax
rollout steps, including cached original evaluations. It recorded 2,063.84
seconds of evaluation work and completed in 2,096.59 seconds, approximately
34.94 minutes. Peak process RSS was 927,809,536 bytes, approximately 0.86 GiB.

Across accepted tested-controller rollouts, the aggregate minimum signed
separation was `0.109138 m` and the minimum longitudinal TTC was `0.0 s`.
The TTC value is a longitudinal projection, while the oriented-box minimum
remained positive. Neither continuous minimum alone satisfies the four-outcome
finding contract; no tested-controller failure with original eligibility and
identical-mutation reference success occurred.

## Interpretation

The random baseline is now a reproducible experimental control. Its validity
rate closely matches the earlier fixed-grid feasibility result, and its
negative finding result is retained rather than used to alter the search
space, controllers, thresholds, or budget.

The next milestone is constrained Bayesian search using exactly the same
32-proposal-per-scenario budget, mutation bounds, acceptance pipeline,
deterministic rerun policy, and proposal-versus-physical-rollout accounting.
Only that matched comparison can address search efficiency. Held-out
evaluation remains a later, separately predeclared experiment.

## Limitations

This is a development run on the selected training feasibility set, not a
representative or held-out evaluation. Both technical controllers use Waymax
IDMRoutePolicy with different configurations. The result makes no claim about
the production Waymo Driver, real-world safety, human driving, or universal
avoidability.

The complete run manifest, original checkpoints, 320 proposal records, source
locations, linked hashes, per-scenario summaries, and full aggregate report
remain only under the ignored `artifacts/random-search/` path.
