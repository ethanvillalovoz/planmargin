# ADR 0004: Recover the original PlanMargin program

- **Status:** Accepted
- **Date:** 2026-08-12
- **Recovery revision:** `31db633`

## Context

PlanMargin began with two coupled objectives:

1. investigate a coherent autonomous-driving testing question; and
2. give simulation, optimization, data, systems, and product technologies real
   responsibilities in one portfolio-quality system.

The frozen natural development experiment completed correctly but produced no
qualifying failures. ADR 0003 preserved the held-out split instead of tuning
the observed protocol. Subsequent work completed analytics, native geometry,
the public evidence surface, and repository presentation.

At that point the completed **experiment-v1** roadmap was incorrectly treated
as completion of the broader program. FastAPI, Beam, a constrained evidence
assistant, real-record debugger integration, and 3D Gaussian visualization had
been removed or made optional without a program-level checkpoint. The public
debugger also retained a synthetic trajectory fixture even though the real
WOMD campaign existed privately. This was scope drift: scientific restraint
did not require stopping the platform work.

## Decision

The original program is reopened under three separately versioned tracks:

1. **Experiment v1 — immutable and complete.** The natural campaign, reports,
   gates, records, and held-out `no_go` decision are not altered.
2. **Platform completion — active.** Product, data-pipeline, assistant, and
   visualization work may consume sealed v1 evidence but cannot change its
   scientific decisions.
3. **Experiment v2 — new protocol.** Any new scenario family, learned or RL
   planner, controller regression, mutation space, or held-out claim receives a
   separately frozen design and development-signal gate.

The repository is not considered complete merely because experiment v1 is
complete. Each original requirement must either ship with tested evidence or
receive an explicit, predeclared feasibility `no_go` whose gate was frozen
before implementation results were observed.

## Requirement traceability

| Requirement                       | Current evidence                                                 | Remaining responsibility                                                                             | Tracking           |
| --------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------ |
| WOMD data                         | Real private training scenarios and aggregate campaign result    | Preserve authorized local-only access in new pipelines                                               | #51, #53           |
| Waymax and JAX                    | Deterministic replay and 1,128,800 rollout steps                 | Reuse unchanged in v2; evaluate a learned JAX/RL responsibility before freezing v2                   | #56                |
| Python orchestration              | Selection, mutation, controllers, search, campaign, analytics    | Own API, Beam adapters, assistant tools, and v2 coordination                                         | #51, #53, #54, #56 |
| PyTorch and BoTorch               | Frozen qLogNEHVI proposal core                                   | Preserve experiment-v1 behavior; reuse only under a new v2 protocol                                  | #56                |
| C++20 and pybind11                | Profiled interaction-metrics kernel with parity evidence         | Profile new pipeline work before assigning more C++                                                  | #57                |
| SQL, DuckDB, and Parquet          | Private aggregate analytical layer with SQL reconciliation       | Provide allowlisted API queries and consume Beam outputs                                             | #51, #53           |
| FastAPI                           | Not implemented                                                  | Localhost-only, read-only service over ignored sealed evidence                                       | #51                |
| Angular, TypeScript, and Three.js | Synthetic scenario debugger plus real aggregate modal            | Add a real-local-data provider while keeping the public fallback                                     | #52                |
| MapReduce/dataflow concepts       | Resumable Python checkpoints, but no distributed runner          | Beam DirectRunner scenario mining and feature extraction to partitioned Parquet                      | #53                |
| Flume                             | Proprietary Google system and not publicly implementable         | Make no Flume claim; document Beam's analogous public dataflow responsibility                        | #53                |
| Gemini or agent layer             | Not implemented                                                  | Optional allowlisted evidence assistant with deterministic offline tests and no private-data default | #54                |
| Reinforcement learning            | Not implemented; Bayesian optimization is not RL                 | Evaluate a small learned/RL planner as an experiment-v2 responsibility                               | #56                |
| 3D Gaussian splatting             | Not implemented                                                  | Run frozen data, compute, privacy, quality, and integration gates; implement only on `go`            | #55                |
| Free execution                    | Local Apple silicon, CPU JAX, GitHub Actions                     | No required paid API, GPU, hosting, or subscription in any new track                                 | #51–#57            |
| Recruiter evidence                | Public aggregate report, debugger screenshot, five-minute review | Reconcile the final narrative only after all active tracks resolve                                   | #57                |

## Platform completion sequence

### 1. Real-record evidence API

A FastAPI service will read only explicitly configured paths under ignored
artifact roots. It will validate content seals, use read-only DuckDB
connections, expose an allowlisted response schema, bind to loopback by
default, and make no outbound request. Synthetic fixtures will prove the
contract in CI without WOMD access.

### 2. Dual-mode debugger

The Angular application will retain its synthetic public mode. When an
authorized local API is available, a separate provider will load real local
campaigns, trajectories, controller outcomes, proposal provenance, and metric
timelines. The UI must make the active evidence mode unmistakable and must not
cache or export private fields accidentally.

### 3. Beam data pipeline

Apache Beam DirectRunner will own bounded scenario mining and empirical feature
extraction into deterministic, partitioned Parquet. Its value will be tested
through idempotence, sharding, keyed aggregation, manifest provenance, restart
behavior, and DuckDB consumption—not through a dependency-only demonstration.

### 4. Evidence assistant

The optional assistant may translate a question into an allowlisted aggregate
query and explain returned deterministic evidence. It may not calculate safety
metrics, certify findings, control a vehicle, or send private scenario data by
default. The core product and CI must work without credentials or network
access. Use of a hosted Gemini endpoint is conditional on an available free
tier and explicit local configuration.

### 5. 3D Gaussian feasibility

Before training, a spike will freeze gates for authorized data availability,
local or Colab-Free execution, wall time, peak memory, reconstruction quality,
privacy, and trajectory-debugging value. A `no_go` is an acceptable outcome;
the technology cannot disappear merely because it is difficult.

## Experiment-v2 boundary

Experiment v2 begins only after a design note freezes:

- the scientific rationale;
- scenario family and selection procedure;
- tested and reference controller identities;
- any learned or RL policy training boundary;
- mutation dimensions and bounds;
- behavioral-support and finding contracts;
- method budgets, seeds, and physical-cost accounting;
- a quantitative development-signal gate; and
- held-out selection and aggregate reporting rules.

The official held-out split remains unopened unless the v2 development gate
passes. Platform progress cannot authorize held-out access.

## Program guardrails

- No paid service or subscription may become required.
- No restricted WOMD record or credential may enter Git, CI, a hosted service,
  or an assistant request by default.
- No experiment-v1 threshold, controller, mutation bound, or conclusion may be
  revised.
- No technology is added without an owned responsibility and a verification
  contract.
- No originally requested responsibility is silently removed; infeasible work
  requires a frozen gate and documented `no_go`.
- Negative, partial, and censored outcomes remain visible.

## Consequences

The project will take longer than the reduced version-one roadmap, but the
program once again matches its original goal. Experiment v1 remains a credible
negative result, while platform completion and experiment v2 can progress
without rewriting history.
