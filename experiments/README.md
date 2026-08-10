# Experiments

Each experiment will receive a versioned configuration and a short report containing:

- objective and hypothesis
- scenario selection criteria
- policy and reference-controller versions
- mutation bounds
- rollout budget
- random seeds
- metric definitions
- environment and hardware
- results and uncertainty
- limitations and follow-up decision

Large outputs, checkpoints, raw data, identifiers, and per-scenario derived
records are ignored. Public experiment notes are limited to methodology and
permitted aggregate results. Complete local manifests belong under the ignored
`artifacts/` directory.

The completed access, deterministic-baseline, scenario-selection, and first
mutation evidence is recorded under [`stage-0/`](stage-0/), including the
[ten-scenario selection report](stage-0/scenario-selection.md) and the
[bounded speed-mutation report](stage-0/speed-mutation.md). The
[controller-comparison report](stage-0/controller-comparison.md) records the
first tested-versus-reference harness run and its negative finding.
