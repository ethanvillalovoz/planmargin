# Final full-program integration audit

PlanMargin's recovered program is complete as of August 13, 2026. Completion
means every original responsibility either ships with verified evidence or has
a predeclared, reproducible `no_go`. It does not mean every experimental result
was positive.

## August 18 product-workbench addendum

The research decisions below remain immutable. A later product pass changed
how engineers inspect them: PlanMargin now opens on a usable investigation
workspace, verifies and ranks all 3,200 campaign proposals, compares any two
ranked candidates, opens the exact 32-proposal cell, renders the full
qualification-gate ladder and tested/reference outcomes, produces
proposal-specific deterministic analysis with a sealed-record citation, and
exports SHA-256-digested local HTML reports. The campaign narrative is a
separate **Report** section; authentic planning replay and the camera/3DGS/LiDAR
workspace have dedicated **Replay** and **Sensor Lab** entries.

The addendum does not create campaign trajectories that were not retained.
Only the Stage-0 package contains full trajectory replay data; the 3,200
campaign proposals retain trajectory hashes and measured outcomes. The UI
states this boundary instead of synthesizing playback.

Current addendum verification: 35 Angular/Vitest tests pass, the production
Angular build remains inside its configured bundle budgets, npm reports zero
known vulnerabilities, and all 214 Python tests pass. In-app browser QA covered
the public and authenticated
investigation, comparison, proposal analysis, planning playback, real Camera
playback with changing native boxes, 3DGS, desktop, and mobile layouts. It found
and fixed the collapsed embedded-scene grid and mobile-header navigation bugs.

The aggregate-only Hugging Face package is staged, hashed, and downloadable as
`dist/planmargin-public-evidence-v1.zip`. External publication remains held for
Waymo redistribution review; no restricted artifact has been uploaded.

## Requirement disposition

| Responsibility                       | Final disposition     | Evidence                                                                                                                                                                                                                                                                                       |
| ------------------------------------ | --------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| WOMD and Waymax                      | Shipped               | Training-default access check and deterministic 80-step real WOMD replay passed. The v1 campaign retained 14,110 physical rollouts and 1,128,800 Waymax steps.                                                                                                                                 |
| Python and JAX                       | Shipped               | Simulation, mutation, coordination, evidence services, Gaussian extraction, and deterministic DQN training.                                                                                                                                                                                    |
| PyTorch and BoTorch                  | Shipped               | Frozen constrained qLogNEHVI proposal core and complete matched v1 campaign.                                                                                                                                                                                                                   |
| C++20 and pybind11                   | Shipped               | Native oriented-box interaction kernel retained exact Python parity and measured 604.893× faster in the final isolated 80-state audit fixture.                                                                                                                                                 |
| SQL, DuckDB, and Parquet             | Shipped               | Sealed experiment reconstruction, allowlisted queries, and row-level reconciliation.                                                                                                                                                                                                           |
| Apache Beam / dataflow               | Shipped               | Fresh DirectRunner integration processed 16 sealed source shards, 7,796 records, and 265 accepted events into eight deterministic partitions in 10.1 seconds.                                                                                                                                  |
| FastAPI                              | Shipped               | API v1.1 authenticated the loopback boundary, returned `401` without a token, used `no-store`, passed four representative route audits, and leaked none of the ten known scenario IDs.                                                                                                         |
| Angular, TypeScript, Three.js, Spark | Shipped               | The campaign-first workbench investigates sealed proposal gates and exports privacy-reduced digested HTML; Sensor Lab renders recorded Camera, an independent sealed Planning replay, calibrated SHARP 3DGS, same-frame LiDAR, and authenticated assistance. It has no synthetic-runtime path. |
| Gemini / agent layer                 | Conditionally shipped | Five deterministic offline evidence tools ship. The optional Gemini adapter is public-aggregate-only and free-tier-gated; no hosted request was required or made in the final audit.                                                                                                           |
| 3D Gaussian splatting                | Split disposition     | The exact-planning-scenario LiDAR field remains `no_go` at 23.66% trajectory linkage. A separate WOD Perception visualization track now ships a real 1.18M-primitive SHARP reconstruction and 50k-return same-frame LiDAR viewer, explicitly outside the planning claim.                       |
| Reinforcement learning               | Evaluated `no_go`     | Two final-seed JAX/Optax double-DQN trainings were byte-identical and passed compute/progress gates. A 3.125% synthetic collision rate failed the frozen 1.0% safety gate, so no Waymax deployment or v2 campaign ran.                                                                         |
| Free execution                       | Shipped               | All mandatory work ran locally on the M4 Pro or in data-free GitHub Actions. No paid service, hosted database, GPU, or subscription is required.                                                                                                                                               |

## Final verification

The final local audit ran from the repository root:

- Ruff: all checks passed;
- Python: 212 tests passed; the only output was two upstream PyTorch
  deprecation warnings;
- Python packaging: source distribution and native arm64 wheel built;
- Angular/Vitest: 26 tests passed across real-local parsers, the authenticated
  sensor client, independent timeline stores, campaign evidence, and state
  contracts;
- Angular production build: the application and lazy Three.js/Spark sensor
  renderer completed the optimized build budget;
- npm audit at moderate severity: zero vulnerabilities;
- browser E2E: a clean authenticated run verified Camera 099 → 109 seeking and
  35 → 32 changing native boxes during playback, Planning 000 → 010 seeking,
  minimum-margin assistant navigation, source/left/right 3DGS, LiDAR, compact
  layout, Planning-to-spatial remounts, and safe disconnect;
- JSON Schema: all 25 tracked schemas passed Draft 2020-12 meta-validation;
- documentation: all 49 tracked Markdown files were checked for local-link
  integrity after this report was added;
- native kernel: exact parity, 17.291 microseconds native versus 10,459.5
  microseconds Python on the final synthetic fixture;
- real Beam dataflow: fresh build and independent audit both returned
  `beam_pipeline_verified`;
- real evidence boundary: the sealed v1 campaign, analytics, and rollout
  collection opened successfully through API v1.1;
- evidence assistant: public claim-boundary and private-local campaign queries
  both used the deterministic offline provider and leaked no known ID;
- Gaussian and RL private reports: both reran and validated against their
  tracked schemas with their expected `no_go` decisions; and
- privacy: all ten known private scenario IDs were searched across tracked Git
  content with zero matches; no artifact, TFRecord, Parquet, DuckDB, or model
  checkpoint is tracked; common private-key and provider-token signatures were
  absent.

The completed v1 campaign cannot be resumed into its old directory from the
new source revision because its immutable manifest pins the original code and
clean environment. That rejection is expected. The sealed result remains
readable and reconstructable through the versioned evidence layer; exact
execution belongs to its recorded Git revision.

## Scientific outcome

The defensible result is deliberately narrower than the original hope:

- constrained Bayesian search increased support-and-pipeline-valid proposal
  yield by 14.8125 percentage points in the ten-scenario development campaign;
- neither method found a qualifying failure, so comparative discovery
  efficiency and minimality remain untestable;
- the Gaussian reconstruction was geometrically strong but not sufficiently
  linked to the full debugger trajectory;
- the learned controller improved greatly over its untrained initialization
  but did not meet its safety gate; and
- no validation-backed comparative search campaign ran.

One validation record was accessed by the legacy Stage-0 compatibility smoke.
The audit corrected every later absolute claim that the validation split was
pristine or never opened, while preserving the accurate historical Stage-0
report. [ADR 0007](decisions/0007-correct-validation-access-boundary.md)
documents the correction and the new training-default guard.

PlanMargin does not evaluate the production Waymo Driver and provides no
real-world safety conclusion.

## Deliberate non-goals and remaining limits

- GitHub Pages or another hosted real-data deployment was explicitly deferred;
  the complete real product remains localhost-only by design.
- Gemini availability, price, and provider terms are external and must be
  rechecked before optional use. The deterministic assistant needs none of
  them.
- Flume is proprietary and is not claimed; Apache Beam owns the public dataflow
  responsibility.
- Both real 3D PLYs and the failed DQN checkpoint remain ignored local
  artifacts. The Perception viewer is a product feature; the PLY contents and
  the failed plan-linkage/RL studies are not published evidence.
- A future learned controller, Gaussian crop, scenario family, or comparative
  validation study requires a new protocol version. The observed gates cannot
  be relaxed retroactively.

## Final decision

The original scientific program is closed as **complete with bounded negative
research results**. The later Perception visualization adds a complete local
product surface without changing, relaxing, or replacing any frozen research
decision.
