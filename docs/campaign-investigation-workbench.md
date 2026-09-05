# Campaign investigation workbench

## Product question

PlanMargin's interface answers one engineering question:

> Why did this candidate fail to become a qualifying, policy-specific,
> avoidable planner failure—and what can the campaign actually claim?

The authenticated application opens on **Investigate**, with the smallest-margin
change selected and its decision beside the ranked queue. Public clones show
aggregate evidence until licensed local data is connected. **Test health**,
**Sensor lab**, and **Models** are separate supporting surfaces, not additional
panels crowding the primary investigation.

## Investigation flow

1. **Investigate** opens the smallest-margin candidate and its evidence.
2. Without local data it shows real aggregates, never invented scenario rows.
3. Local authentication verifies all 3,200 sealed proposals and builds a
   review queue for closest-to-failure, smallest-change, and
   strongest-precedent rankings.
4. Any two campaign-ranked proposals can be compared side by side, then opened
   in their exact method/scenario/seed cell.
5. **Browse all 100 search runs** reveals the advanced cell matrix. It loads
   and seal-verifies each cell's 32 proposal records.
6. Raw criticality, minimality, and support measurements remain auditable, but
   the queue leads with safety result, change size, recorded precedent, and the
   reason the candidate stopped.
7. **Explain decision** reveals the gate ladder on demand. Mutation, scenario,
   support, reference, and tested-planner outcomes remain distinct.
8. Proposal-specific deterministic analysis cites the selected sealed record
   hash and never sends private evidence to Gemini.
9. When a separately versioned replay package exists, the proposal opens that
   exact replay only after the API verifies the campaign-record link, fresh
   trajectory hashes, outcomes, interaction metrics, and collection seal.
10. Report export produces self-contained HTML and a SHA-256 digest over the
    selected privacy-reduced evidence payload.
11. **Sensor lab** keeps the WOD Perception camera, 3DGS, and LiDAR study
    available as a secondary, explicitly independent workspace.

## Replay boundary

The 3,200 campaign proposal records contain parameters, support evidence,
objectives, constraints, deterministic outcomes, cost, and validated trajectory
hashes. They did not retain the underlying controller trajectories.

The separately versioned replay-retention protocol closes that gap only for
explicitly re-executed proposals. The current local workspace contains ten:

| Selection purpose                | Method   | Seed | Scenario order | Proposal |
| -------------------------------- | -------- | ---: | -------------: | -------: |
| Overall closest margin           | random   |    1 |              8 |       12 |
| Closest Bayesian margin          | bayesian |    0 |              8 |       29 |
| Small-edit near-margin case      | bayesian |    3 |              8 |       20 |
| Strongest-support Bayesian case  | bayesian |    2 |              2 |       27 |
| Strongest-support random case    | random   |    3 |              2 |       20 |
| Scenario-order 1 low-margin case | bayesian |    1 |              1 |       16 |
| Scenario-order 3 low-margin case | random   |    4 |              3 |       30 |
| Scenario-order 4 low-margin case | bayesian |    0 |              4 |       29 |
| Scenario-order 5 low-margin case | bayesian |    3 |              5 |       20 |
| Scenario-order 7 low-margin case | random   |    0 |              7 |       13 |

Their fresh trajectories reproduce the sealed v1 hashes and metrics. The UI
labels all other proposal records as not retained and never substitutes the
Stage-0 replay. Additional proposals must be re-executed and verified; a
trajectory cannot be inferred from its hash.

## Research follow-ups

The project documentation preserves the predeclared no-go results:

- the v2 JAX double-DQN controller failed its synthetic-safety gate (3.125%
  collision rate), so no v2 Waymax development or validation campaign ran;
- the exact-planning-scene LiDAR Gaussian field covered 23.66% of debugger
  trajectories, below its 90% linkage gate;
- the real WOD Perception 3DGS/LiDAR assets remain useful for visual sensor
  inspection but are not registered to the WOMD planning claim.

No paid service is required.
