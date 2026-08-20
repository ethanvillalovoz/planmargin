# Release-readiness audit

**Audit date:** August 20, 2026

**Scope:** current source tree, retained local evidence, public distribution
boundary, and task-first engineering workbench

## Decision

PlanMargin is ready as a local autonomous-driving research workbench with
bounded claims. Its public source, aggregate result, authenticated evidence
service, retained planning replay, recorded perception views, search pipeline,
and deterministic assistant are implemented and verified.

Two items are intentionally outside that readiness decision:

- this Mac cannot perform a fresh native C++ rebuild until its owner reviews
  and accepts the installed Xcode license; and
- the optional Gemini explanation adapter is not configured. The offline
  deterministic assistant remains available.

Neither item blocks the currently verified local workbench. No paid service,
hosted database, subscription, or purchased compute is required.

## What an engineer can do

1. Open an authenticated local session without copying a token.
2. Replay the retained Stage-0 tested, reference, and recorded planner paths on
   a shared timeline.
3. Inspect 199 recorded WOD FRONT frames with frame-specific tracked boxes.
4. Orbit the pinned 1,179,648-primitive Apple SHARP reconstruction and inspect
   the 50,241-return same-frame LiDAR field.
5. Rank all 3,200 sealed counterfactual proposals by minimum clearance, edit
   size, or recorded precedent.
6. Trace the first failed qualification gate and compare tested/reference
   planner outcomes.
7. Export a privacy-reduced, SHA-256-digested HTML investigation report.
8. Ask bounded evidence questions through deterministic local tools.

The product does not invent a scenario, trajectory, camera stream, box track,
point field, or reconstruction when licensed evidence is absent.

## Claim and synchronization boundaries

- The 3,200 campaign proposals retain hashes, outcomes, objectives, and costs,
  but not full replay trajectories. The UI never presents the separate Stage-0
  trajectory as if it belonged to a selected campaign proposal.
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
| Public distribution        | Shipped     | code and aggregate result only; licensed per-record artifacts remain local                 |

## Verification performed on this revision

- Ruff: all checks passed.
- Python: 221 tests passed. The three warnings are upstream PyTorch deprecation
  and BoTorch's documented pure-Python fallback when Ninja is unavailable.
- Angular/Vitest: 36 tests passed across launch authentication, local evidence,
  parsers, stores, navigation, reports, and workbench behavior.
- TypeScript: application and test projects passed strict type checking.
- Frontend formatting and optimized production build: passed; the direct app
  payload is about 301 kB raw, while Spark and Three.js viewers remain lazy.
- Dependency audit: `npm audit --audit-level=moderate` reported zero known
  vulnerabilities.
- Authenticated HTTP: frontend, health, campaign, investigation, planning runs,
  Sensor metadata, Gaussian metadata, and proposal analysis returned success.
- Authorization and headers: unauthenticated health returned `401`; private
  responses included `Cache-Control: no-store` and
  `X-Content-Type-Options: nosniff`.
- Workspace doctor: public source, campaign evidence, Sensor evidence, Beam
  output, Gaussian research, and JAX research all verified as ready.

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

- Review and accept the Xcode license before requesting a fresh native rebuild
  on this Mac. PlanMargin will not perform that privileged acceptance step.
- Supply a Gemini key only if optional external explanations are wanted and the
  current free-tier/provider terms have been reviewed. It is not required.
- Perform final visual sign-off in the authenticated local browser whenever UI
  source changes; licensed evidence is deliberately not uploaded for remote
  visual testing.
