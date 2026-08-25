# Release-readiness audit

**Audit date:** August 24, 2026

**Release candidate:** v3.0.0 (unpublished)

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

The v2.0 audit scales the deployment-oriented real-WOMD track to 1,024
scenarios and 126,992 windows, with complete-scenario holdout, PyTorch, dynamic-
batch ONNX, and a byte-identical clean repeat. It also evaluates—rather than
merely lists—two additional learned responsibilities: active-risk proposal
ranking and nearest-actor interaction context. Both failed frozen promotion
gates and remain documented negative results with no deployed model.

## What an engineer can do

1. Open an authenticated local session without copying a token.
2. Replay the retained Stage-0 paths or open the closest-to-failure campaign
   proposal whose fresh tested/reference trajectories reproduce the sealed v1
   hashes, outcomes, interaction metrics, and scenario validation.
3. Inspect 199 recorded WOD FRONT frames with frame-specific tracked boxes.
4. Orbit three independently generated 1,179,648-primitive Apple SHARP
   reconstructions and inspect the 50,241-return same-frame LiDAR field.
5. Rank all 3,200 sealed counterfactual proposals by minimum clearance, edit
   size, or recorded precedent.
6. Trace the first failed qualification gate and compare tested/reference
   planner outcomes.
7. Export a privacy-reduced, SHA-256-digested HTML investigation report.
8. Ask eight bounded evidence questions through deterministic local tools or
   the optional Gemini explanation adapter.
9. Inspect measured Tesla T4 latency, throughput, FP32/FP16 drift, environment
   versions, and engine hashes without accessing licensed WOMD records.
10. Inspect the scaled model's real-data ADE/FDE, active-mining no-go, interaction
    ablation no-go, and NVIDIA rerun status without conflating those tracks.

The product does not invent a scenario, trajectory, camera stream, box track,
point field, or reconstruction when licensed evidence is absent.

## Claim and synchronization boundaries

- The frozen 3,200 campaign proposals retain hashes, outcomes, objectives, and
  costs, but did not originally retain full trajectories. Ten separately
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
| PyTorch trajectory model   | Shipped     | 1,024 real WOMD scenarios; 0.418 m ADE vs 0.870 m constant-velocity baseline; byte-identical repeat |
| Active-risk qualification  | Stopped     | 2,097 real targets; 0.137 held-out rank correlation; only 3/9 budget-eight wins                  |
| Interaction model          | Stopped     | 0.453 m ADE with nearest actors vs 0.434 m for same-data ego-only ablation                       |
| ONNX and TensorRT 11       | Split       | scaled FP32 measured; scaled FP16 stopped after 0.101 m max drift exceeded its 0.075 m gate       |
| C++17 TensorRT runtime     | Shipped     | independent `enqueueV3` runner now reports device and pinned-host end-to-end p50/p95/p99         |
| Residual FP16 candidate    | Pending GPU | Apple-MPS numerical proxy passed; TensorRT has not been measured and promotion remains blocked    |
| Shielded RL follow-up      | Stopped     | deterministic synthetic study missed its frozen 1% collision gate at 2.686%                       |
| Public distribution        | Shipped     | code and aggregate result only; licensed per-record artifacts remain local                 |

## Verification performed on this revision

- Ruff: all checks passed.
- Python: 282 tests passed. Upstream warnings are identified in the CI log and
  do not suppress failures.
- Angular/Vitest: 56 tests passed across launch authentication, local evidence,
  parsers, stores, navigation, reports, edge-aware trajectory labels, and
  workbench behavior.
- Browser sign-off covers desktop and 390 px mobile evidence surfaces, planning
  playback, ten-frame seek controls, frame-native camera annotation changes,
  and three independently selectable SHARP reconstruction frames.
- Playwright: six desktop/mobile journeys passed. The added local-mode journey
  exercises queue ranking, comparison, candidate inspection, sealed-record
  analysis, model/runtime navigation, the grounded Gemini response contract,
  refresh recovery, responsive overflow, and WCAG A/AA axe checks.
- TypeScript: application and test projects passed strict type checking.
- Frontend formatting and optimized production build: passed; the direct app
  payload is 338.75 kB raw, while Spark and Three.js viewers remain lazy.
- Dependency audit: `npm audit --audit-level=moderate` reported zero known
  vulnerabilities.
- Authenticated HTTP: frontend, health, campaign, investigation, planning runs,
  Sensor metadata, Gaussian metadata, and proposal analysis returned success.
- Authorization and headers: unauthenticated health returned `401`; private
  responses included `Cache-Control: no-store` and
  `X-Content-Type-Options: nosniff`.
- Workspace doctor distinguishes the prior TensorRT qualification from the
  scaled model's completed FP16 no-go decision.
- Python source/wheel distributions and the native C++20 extension built
  successfully for the unpublished PlanMargin 3.0.0 candidate.
- The sixteen-record aggregate-only distribution candidate passed its
  independent SHA-256 verifier locally. No hosting change was made.

## Scientific outcome

The immutable v1 development campaign found no qualifying planner regression.
Constrained Bayesian search increased the support-and-pipeline-valid proposal
rate by 14.8125 percentage points under equal budgets. Failure-discovery
efficiency and failure minimality remain untestable because neither method
found a qualifying failure, and no validation-backed comparison was opened
after the no-go.

That negative result is part of the product's credibility: the repository
preserves what was measured, what failed, and what cannot be claimed.

The Version 2 active-risk, interaction, and scaled-FP16 studies add three
further negative results. Version 3 adds a shielded-controller no-go and a
split-residual FP16 design that passed only its Apple-MPS numerical proxy; it
still requires an NVIDIA TensorRT measurement. None is promoted, and no
thresholds were relaxed after results were observed. The supported positive claim is narrower: the
scaled ego-history predictor beats constant velocity on its 102-scenario
real-WOMD test split, reproduces byte-for-byte on the recorded MPS toolchain,
and has a measured FP32 TensorRT path.

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
- If FP16 promotion is revisited, change the model or mixed-precision export,
  preregister a new protocol, and rerun it. Do not relax the observed 0.075 m
  drift gate post hoc.
- Run the preregistered residual-only ONNX candidate on NVIDIA TensorRT before
  claiming reduced-precision qualification. The checked-in local result is a
  proxy, not a GPU measurement.
