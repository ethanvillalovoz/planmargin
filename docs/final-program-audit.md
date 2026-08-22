# Release-readiness audit

**Audit date:** August 21, 2026

**Release:** v1.2.0

**Scope:** current source tree, retained local evidence, public distribution
boundary, and task-first engineering workbench

## Decision

PlanMargin is ready as a local autonomous-driving research workbench with
bounded claims. Its public source, aggregate result, authenticated evidence
service, retained planning replay, recorded perception views, search pipeline,
deterministic assistant, and exact proposal-replay retention path are
implemented and verified. The local native toolchain is ready, including a
fresh C++ build. Gemini was exercised through the optional free-tier adapter;
the repository still defaults to the offline deterministic provider and stores
no key.

No paid service, hosted database, subscription, or purchased compute is
required.

The v1.2 audit adds a second real-WOMD trajectory track intended for deployment
qualification: 128 scenarios, 29,288 windows, complete-scenario holdout,
PyTorch, ONNX, TensorRT 11 FP32/FP16 engines, and an independent C++17 runtime.
The public model release contains weights and aggregate metrics only.

## What an engineer can do

1. Open an authenticated local session without copying a token.
2. Replay the retained Stage-0 paths or open the closest-to-failure campaign
   proposal whose fresh tested/reference trajectories reproduce the sealed v1
   hashes, outcomes, interaction metrics, and scenario validation.
3. Inspect 199 recorded WOD FRONT frames with frame-specific tracked boxes.
4. Orbit the pinned 1,179,648-primitive Apple SHARP reconstruction and inspect
   the 50,241-return same-frame LiDAR field.
5. Rank all 3,200 sealed counterfactual proposals by minimum clearance, edit
   size, or recorded precedent.
6. Trace the first failed qualification gate and compare tested/reference
   planner outcomes.
7. Export a privacy-reduced, SHA-256-digested HTML investigation report.
8. Ask bounded evidence questions through deterministic local tools.
9. Inspect measured Tesla T4 latency, throughput, FP32/FP16 drift, environment
   versions, and engine hashes without accessing licensed WOMD records.

The product does not invent a scenario, trajectory, camera stream, box track,
point field, or reconstruction when licensed evidence is absent.

## Claim and synchronization boundaries

- The frozen 3,200 campaign proposals retain hashes, outcomes, objectives, and
  costs, but did not originally retain full trajectories. Five separately
  versioned packages now re-execute and verify selected margin-, edit-, and
  support-ranked proposals across both search methods. The UI labels all
  remaining proposals as not retained and never substitutes the separate
  Stage-0 trajectory.
- The WOD Perception segment and WOMD planning replay are separate authorized
  records. Camera, 3DGS, and LiDAR are synchronized to one another where stated;
  they are not claimed to be registered to the planning replay.
- The exact-planning-scene Gaussian study remains a sealed `no_go` at 23.66%
  trajectory linkage. The shipped SHARP reconstruction is the separate,
  explicitly labeled Perception visualization track.
- The JAX/Optax learned-controller study remains a sealed `synthetic_no_go`; it
  is research evidence, not a runtime data source for the product.
- PlanMargin does not evaluate the production Waymo Driver and supports no
  real-world safety conclusion.

## Requirement disposition

| Responsibility             | Disposition | Verified implementation                                                                    |
| -------------------------- | ----------- | ------------------------------------------------------------------------------------------ |
| WOMD and Waymax            | Shipped     | deterministic 80-step replay; 14,110 retained physical rollouts and 1,128,800 Waymax steps |
| Counterfactual search      | Shipped     | matched random and constrained BoTorch qLogNEHVI budgets across 100 cells                  |
| Python and JAX             | Shipped     | simulation, mutation, orchestration, evidence services, and reproducible RL qualification  |
| C++20 and pybind11         | Shipped     | native interaction metrics with randomized Python-oracle parity                            |
| Beam, Parquet, DuckDB, SQL | Shipped     | deterministic partitions, sealed shards, and SQL reconciliation                            |
| FastAPI                    | Shipped     | loopback-only token authentication, closed response models, `no-store`, and `nosniff`      |
| Angular and TypeScript     | Shipped     | task-first Workbench, Sensors, and Evidence flows with strict types                        |
| Three.js and Spark         | Shipped     | lazy-loaded LiDAR/3DGS and planning-scene rendering                                        |
| 3D Gaussian splatting      | Split       | real SHARP Perception reconstruction shipped; planning-linked study preserved as `no_go`   |
| Evidence assistant         | Shipped     | deterministic local tools; Gemini is an optional allowlisted explanation adapter           |
| Proposal replay retention  | Shipped     | exact re-execution linked to the sealed proposal by trajectory, outcome, metric, and seal checks |
| PyTorch trajectory model   | Shipped     | 128 real WOMD scenarios; 0.322 m ADE vs 0.620 m constant-velocity baseline                      |
| ONNX and TensorRT 11       | Shipped     | hash-pinned FP32/typed-FP16 graphs; T4 CUDA-event timing and parity gates                        |
| C++17 TensorRT runtime     | Shipped     | independently compiled `enqueueV3` runner; 0.124 ms batch-1 p50                                  |
| Public distribution        | Shipped     | code and aggregate result only; licensed per-record artifacts remain local                 |

## Verification performed on this revision

- Ruff: all checks passed.
- Python: full data-free suite passed. Upstream warnings are identified in the
  CI log and do not suppress failures.
- Angular/Vitest: 50 tests passed across launch authentication, local evidence,
  parsers, stores, navigation, reports, and workbench behavior.
- Playwright: four Chromium journeys passed across desktop and mobile. They
  cover the data-free public boundary, exact proposal-to-replay transition,
  responsive overflow, meaningful interaction, and WCAG A/AA axe checks.
- TypeScript: application and test projects passed strict type checking.
- Frontend formatting and optimized production build: passed; the direct app
  payload is about 309 kB raw, while Spark and Three.js viewers remain lazy.
- Dependency audit: `npm audit --audit-level=moderate` reported zero known
  vulnerabilities.
- Authenticated HTTP: frontend, health, campaign, investigation, planning runs,
  Sensor metadata, Gaussian metadata, and proposal analysis returned success.
- Authorization and headers: unauthenticated health returned `401`; private
  responses included `Cache-Control: no-store` and
  `X-Content-Type-Options: nosniff`.
- Workspace doctor: public source, campaign evidence, exact proposal replay,
  Sensor evidence, Beam output, Gaussian research, JAX research, PyTorch/ONNX,
  and TensorRT qualification all verified as ready.

## Scientific outcome

The immutable v1 development campaign found no qualifying planner regression.
Constrained Bayesian search increased the support-and-pipeline-valid proposal
rate by 14.8125 percentage points under equal budgets. Failure-discovery
efficiency and failure minimality remain untestable because neither method
found a qualifying failure, and no validation-backed comparison was opened
after the no-go.

That negative result is part of the product's credibility: the repository
preserves what was measured, what failed, and what cannot be claimed.

## Remaining operator actions

- Supply a Gemini key only when optional external explanations are wanted and
  the current free-tier/provider terms have been reviewed. It is not required,
  and the key must remain process-local.
- Keep proposal replay packages and all WOD-derived scene media local. They are
  restricted evidence and are not part of a public release or Hugging Face
  upload.
- Re-run the authenticated visual sign-off whenever UI or evidence-contract
  source changes. CI covers a data-free equivalent because licensed evidence
  is deliberately not uploaded.
