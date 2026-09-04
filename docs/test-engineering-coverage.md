# Simulation test-engineering coverage

This matrix separates demonstrated system responsibilities from technologies
that merely appear in dependency files. Every “implemented” row points to an
executable contract, measured run, or working product surface.

| Responsibility                     | Evidence in PlanMargin                                                                                              | Status                      |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| Design behavior metrics            | Six independent candidate gates, paired tested/reference outcomes, progress recovery, exact state-transition timing | Implemented                 |
| Version test plans                 | Frozen campaign, command-dropout, and assistance-handoff protocols with immutable schema versions                   | Implemented                 |
| Test off-nominal scenarios         | Sustained and temporary planner-command dropout on ten real WOMD scenes                                             | Implemented                 |
| Verify protection behavior         | Conservative fallback succeeds in 10/10 scenes; 80/80 gates pass                                                    | Implemented                 |
| Verify assistance behavior         | Fault/request/fallback/resolution/recovery succeeds in 10/10 scenes; 90/90 gates pass                               | Implemented                 |
| Track fleet-scale fault rates      | Aggregate fault and transition pass rates are reported; no production-fleet claim is made                           | Bounded research equivalent |
| Automate coverage updates          | Python reconstructs coverage from sealed reports; JSON Schema versions the public contract                          | Implemented                 |
| Query and reconcile results        | DuckDB and SQL independently reconstruct campaign and method totals                                                 | Implemented                 |
| Monitor release-critical tests     | Seven owned SLOs distinguish execution health from behavior outcome                                                 | Implemented                 |
| Alert on unhealthy tests           | Pure evaluator emits one actionable, owned alert per failed SLO; degraded fixtures exercise it in CI                | Implemented                 |
| Debug and root-cause failures      | Issue queue links observed evidence, failed gates, owner, source record, and next action                            | Implemented                 |
| Operate complex simulation systems | Resumable 100-cell campaign, 3,200 proposals, 14,110 physical rollouts, 1,128,800 Waymax steps                      | Implemented                 |
| Python systems work                | Simulation orchestration, artifact validation, FastAPI, test health, model and search experiments                   | Implemented                 |
| C++ systems work                   | C++20 geometry kernel with Python-oracle parity; independent C++17 TensorRT runtime                                 | Implemented                 |
| Dashboard product                  | Angular operations console, coverage matrix, issue filters, local scenario debugger, and sensor lab                 | Implemented                 |
| Distributed data processing        | Apache Beam partitions, Parquet, DuckDB reconciliation, resumable checkpoints                                       | Implemented locally         |
| SRE-style contracts                | Explicit SLO targets, owners, observed values, active-alert rules, fail-closed evidence boundaries                  | Implemented                 |

## Remaining boundaries

- The fault and assistance protocols run in Waymax only; cross-simulator
  agreement is not established.
- The assistance-resolution signal is deterministic. It does not measure a
  human operator, network delay distribution, or production service.
- The campaign operates over bounded licensed research data, not a production
  fleet or release pipeline.
- The public clone exposes aggregate evidence. Authorized records are required
  for exact replay, camera, LiDAR, and 3DGS.

These limits are product features: the UI shows them as known gaps so a healthy
test run cannot be mistaken for a broader safety or production-readiness claim.
