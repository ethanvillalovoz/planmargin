# PlanMargin 3.1.0

PlanMargin 3.1.0 turns the default product surface into a simulation test
operations console and adds two real-data off-nominal behavior qualifications.

## Test operations

- Seven executable SLOs separate campaign execution health from behavior
  outcome.
- Degraded-state fixtures verify one owned, actionable alert per failed SLO.
- A schema-validated, content-sealed v2 aggregate report drives both FastAPI
  and Angular.
- The report inventories 120/120 measured test cells across three independently
  versioned plans, with numeric SLIs, objectives, and remaining error budget.
- Coverage, known gaps, and measured promotion decisions are inspectable
  without licensed scene records.
- Every alert and held decision carries the same detector, owner, impact,
  isolation path, resolution, prevention, source, and failed-gate contract.

## Off-nominal behavior verification

- Sustained planner-command dropout: 60 physical rollouts, 4,800 Waymax steps,
  10/10 protected fallback successes, 80/80 scene gates.
- Timed assistance handoff: 60 physical rollouts, 4,800 Waymax steps, 10/10
  successful handoffs, 10/10 exact request/recovery traces, 90/90 scene gates.
- Both studies use the ten deterministic real-WOMD training scenes and preserve
  per-scene traces under the ignored local evidence boundary.
- The first invalid-action fault representation remains documented as a no-go;
  thresholds were not relaxed after observing results.

## Product

- Campaign is now the default destination.
- The console provides task-separated health, versioned behavior-coverage, and
  issue-triage workflows instead of repeating the same status in several panels.
- The assistant routes ten sealed evidence topics, supports natural greetings
  and capability questions locally, and shows only three primary investigations
  before progressively revealing the remaining topics.
- The repository README uses screenshots captured from the verified local
  product; no generated or fabricated interface imagery is included.
- The visual system remains independently branded while using the spatial,
  technical, high-contrast character of public autonomous-driving tools.

## Boundaries

The fault and assistance studies are independent research. They do not model
Waymo Driver behavior, a human-operated remote-assistance service, production
fleet health, or a safety claim. Cross-simulator agreement remains open.
Scheduled completion latency is also explicitly uncovered because no per-suite
wall-clock deadline was preregistered.
