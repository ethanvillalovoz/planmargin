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

The completed access and deterministic-baseline evidence is recorded under
[`stage-0/`](stage-0/), including the
[ten-scenario selection report](stage-0/scenario-selection.md). The first
planned mutation experiment is
`exp-0001-waymax-mutation-smoke-test`.
