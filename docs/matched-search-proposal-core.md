# Matched-search proposal core

This data-free component implements the proposal and outcome boundary for the
version-two random/Bayesian development comparison frozen in the
[empirical-support and matched-search protocol](behavioral-realism-and-matched-search.md).
It does not read WOMD, run Waymax or a controller, open private checkpoints, or
certify findings.

## Reproducible environment

The released CPU stack is resolved exactly in `uv.lock` for Python 3.11:

| Dependency      | Resolved version |
| --------------- | ---------------- |
| PyTorch         | `2.13.0`         |
| BoTorch         | `0.18.1`         |
| GPyTorch        | `1.15.2`         |
| linear_operator | `0.6.1`          |

BoTorch is a direct exact dependency. The other versions are transitive exact
resolutions in the lockfile. The proposal core creates tensors only with
`torch.float64` on `cpu`; it never selects CUDA or MPS. Reproduce the public
machine-readable report with one frozen PyTorch intra-operation thread:

```bash
uv sync --frozen
uv run --frozen planmargin-report-matched-search-core
```

The report contains dependency versions, the enforced device and dtype, and
the complete immutable configuration. Hardware availability does not alter
the selected device.

## Proposal contract

Both methods retain every one of 32 proposal indices for each ordered scenario
and seed. The random control exactly preserves the existing stateless
NumPy `SeedSequence`/`PCG64` mapping. The Bayesian method uses eight keyed,
scrambled, float64 Sobol points and then refits five independent exact
`SingleTaskGP` outputs after each evaluation.

The five modeled outputs are, in order, criticality, minimality, pipeline
constraint, empirical-support constraint, and reference-controller
constraint. A `GenericMCMultiOutputObjective` exposes only the first two to
qLogNEHVI. Three constraint callables expose the remaining outputs, with
values less than or equal to zero feasible as required by BoTorch's
[qLogNEHVI API](https://botorch.readthedocs.io/en/stable/acquisition.html).
Rejected pipeline proposals retain five finite outputs but receive zero-valued
objectives.

For proposal indices 8 through 31, constrained
`qLogNoisyExpectedHypervolumeImprovement` uses `q=1`, 128 Sobol QMC samples,
fixed observation variance `1e-6`, and reference point `[0, 0]`. Six separate
calls to the official
[`optimize_acqf_mixed`](https://botorch.readthedocs.io/en/stable/optim.html)
path fix one exact onset value at a time while optimizing the bounded speed
multiplier. This exposes all six discrete candidates to the predeclared
SHA-256 tie rule instead of allowing an internal array-order tie to become the
scientific rule.

The numerical path fixes all model, QMC, and optimizer seeds and uses one CPU
intra-operation thread. It deliberately does not call TorchInductor or
`torch.use_deterministic_algorithms`: PyTorch 2.13's latter entry point imports
the installed Triton/CUDA bindings on Linux even for a CPU tensor path. The
operations used by this exact-GP path are CPU operations, and reproducibility
is tested directly rather than inferred from an accelerator-oriented flag.

Each optimizer call uses 10 restarts, 256 raw samples, and at most 200
iterations. Model construction, QMC sampling, and optimizer initialization are
keyed by stable integer identities. Exact duplicates consume budget. Any
insufficient-data, model-fit, acquisition, or optimizer failure records its
reason and selects the proposal-index-specific Sobol fallback; no adaptive
retry changes the candidate.

## Data-free evidence boundary

The test suite proves all five eight-point Sobol designs across fresh Python
processes, legacy-random equivalence, objective and constraint reference
values, negative-feasible acquisition semantics, failure-independent fallback
identity, duplicate retention, SHA tie handling, and the complete 32-state
synthetic loop. One production-setting qLogNEHVI transition proves the real
model/acquisition/optimizer integration on CPU; the full state-machine
reproducibility test injects a deterministic optimizer seam so CI does not
confuse repeated numerical optimization with proposal-accounting coverage.

This milestone establishes only a deterministic search component. The
[method-neutral cell coordinator](matched-search-coordinator.md) now supplies
the durable record, derivation, accounting, and resume boundary. Its next gate
is a bounded private evaluator adapter and one-scenario, two-proposal smoke
test. No search-efficiency or safety claim follows from either synthetic
fixture.
