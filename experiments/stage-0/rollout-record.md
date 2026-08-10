# Stage 0: versioned rollout and metric records

## Question

Can the private tested-versus-reference comparison be converted into a stable,
versioned record that links original and counterfactual rollouts, retains all
reproducibility context, and remains usable by the next visualization step?

## Configuration

- controller-comparison artifact produced from a clean Git revision;
- rollout-record collection schema `1.0.0`;
- deterministic comparison and record identifiers;
- original and counterfactual variants for tested and reference roles; and
- output restricted to the ignored local artifacts directory.

## Result

The export passed structural validation. One comparison key linked four unique
completed rollout records covering both variants and both controller roles.
Every record retained both controller versions, metric configuration,
acceptance-gate results, seed, rollout Git revision, environment and hardware
class, independent outcome, reproducibility hashes, and a complete 81-state
trajectory.

The invalid-candidate form is covered by synthetic tests: rejection reasons are
retained while outcome and trajectory remain null. Repeated exports from the
same source are identical.

The ignored local collection contains exact identifiers, hashes, and derived
trajectories. None of those values are reproduced in this report.

## Interpretation and limitations

This result validates record structure and provenance, not planner performance
or behavioral realism. Schema `1.0.0` is intentionally narrow and currently
models one SDC trajectory per record. Future schema changes must be versioned
rather than silently changing the meaning of existing fields. The next step is
to generate a static original-versus-counterfactual visualization directly
from this collection.
