# ADR 0001: Begin with planner-specific, avoidable counterfactual failures

- **Status:** Accepted
- **Date:** 2026-08-09

## Context

An unconstrained adversarial search can expose many collisions by forcing another actor into the ego vehicle. Such events may be physically implausible, behaviorally unrealistic, or unavoidable. Collision count alone is therefore weak evidence of a planner deficiency.

The project must also remain feasible on an Apple-silicon Mac and free compute tiers while demonstrating simulation, data, ML, systems, and visualization skills.

## Decision

PlanMargin will search for minimal mutations that satisfy three independent properties:

1. The mutation remains physically, map, and behaviorally plausible.
2. The tested planner fails after passing the original scenario.
3. A conservative reference controller succeeds under the identical mutation.

The first experiment will compare constrained Bayesian optimization with uniform random search using equal rollout budgets. It will begin with two mutation dimensions and one scenario family.

## Consequences

### Positive

- Findings are more diagnostic than raw generated collisions.
- The central result can be measured without a large learned model.
- Compute requirements remain modest.
- The experiment creates natural roles for Waymax, C++ geometry, SQL analysis, scalable pipelines, and an engineering interface.

### Negative

- The reference controller becomes part of the validity argument and must be documented carefully.
- Realism cannot be reduced to one perfect number.
- The narrow initial scope may produce fewer failures.
- Results cannot be generalized to production autonomy systems.

## Rejected alternatives

- **Train a large driving model first:** expensive and shifts attention away from evaluation.
- **Optimize only for collisions:** creates trivial and potentially unavoidable events.
- **Make 3D Gaussian splatting central:** visually compelling but unrelated to the first vector-based simulation experiment and risky on available hardware.
- **Lead with an LLM assistant:** duplicates existing résumé evidence and cannot replace deterministic evaluation.

