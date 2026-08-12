# Data-free matched-search proposal core

## Question

Can the frozen mixed-domain Bayesian proposal rule and its random control be
implemented reproducibly on the available Apple-silicon machine without WOMD,
Waymax rollouts, private artifacts, MPS, CUDA, or paid compute?

## Configuration

- Python `3.11` with exact `uv.lock` resolution;
- PyTorch `2.13.0`, BoTorch `0.18.1`, GPyTorch `1.15.2`, and
  linear_operator `0.6.1`;
- float64 CPU tensors only;
- five seeds, 32 proposals, and eight scrambled Sobol initial proposals;
- five independent exact standardized GP outputs;
- constrained qLogNEHVI with two objectives, three negative-feasible outcome
  constraints, and `q=1`;
- six exact discrete onset candidates and one bounded continuous speed
  multiplier; and
- stateless fallback, duplicate retention, and SHA-256 acquisition-tie rules.

## Result

The data-free implementation passed its nine focused tests. All five Sobol
initial designs reproduced byte-for-byte through a fresh Python process. The
random proposal function exactly matched the preserved historical sampler.
Reference objectives and constraints, all fallback classes, exact duplicate
retention, and the `1e-12` acquisition-tie boundary passed.

The real production-setting proposal-8 transition fit five exact GPs and
successfully returned one of the six exact onset values with a speed multiplier
inside `[0.75, 1.0]`. It ran in float64 on CPU and exposed exactly two objective
outputs and three negative-feasible constraints to qLogNEHVI. The focused
suite, including that numerical transition and two fresh-process checks,
completed locally in 12.21 seconds. This is a feasibility observation, not a
controlled performance benchmark.

The complete 32-proposal synthetic state machine reached proposal index 31,
retained 24 deliberately repeated post-initialization candidates, and emitted
identical canonical output in a fresh process. No private dataset or rollout
was used.

## Interpretation and next boundary

The Mac can run the frozen Bayesian proposal core locally without GPU spending.
The next milestone is not a private comparison run. It is the method-neutral
checkpoint schema and coordinator that connects this pure component to the
already implemented support model, mutation pipeline, tested/reference
controllers, complete accounting, and interruption/resume contract.

This result makes no claim that Bayesian search outperforms random search and
no claim about the Waymo Driver, planner quality, or autonomous-driving safety.
