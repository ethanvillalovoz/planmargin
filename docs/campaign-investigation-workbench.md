# Campaign investigation workbench

## Product question

PlanMargin's interface answers one engineering question:

> Why did this candidate fail to become a qualifying, policy-specific,
> avoidable planner failure—and what can the campaign actually claim?

The workbench does not treat a negative experiment as an empty dashboard. Its
default surface is a usable aggregate investigation view. After local
authentication it verifies and ranks all 3,200 proposal records, while the
immutable v1 report remains a separate **Report** section.

## Investigation flow

1. **Investigate** opens in public aggregate mode without placeholder or
   synthetic rows.
2. Local authentication verifies all 3,200 sealed proposals and builds a
   campaign-wide index for closest-margin, smallest-mutation, and
   highest-support rankings.
3. Any two campaign-ranked proposals can be compared side by side, then opened
   in their exact method/scenario/seed cell.
4. The 100-cell matrix loads and seal-verifies each cell's 32 proposal records.
5. Proposals can be ranked by criticality, minimality, empirical support, or
   their original immutable sequence.
6. The gate ladder identifies mutation, scenario, support, reference, and
   tested-controller decisions without collapsing them into one score.
7. Proposal-specific deterministic analysis cites the selected sealed record
   hash and never sends private evidence to Gemini.
8. Report export produces self-contained HTML and a SHA-256 digest over the
   selected privacy-reduced evidence payload.
9. **Replay** presents the one authentic Stage-0 planning trajectory package.
10. **Sensor Lab** keeps the WOD Perception camera, 3DGS, and LiDAR study
   available as a secondary, explicitly independent workspace.

## Replay boundary

The 3,200 campaign proposal records contain parameters, support evidence,
objectives, constraints, deterministic outcomes, cost, and validated trajectory
hashes. They do not contain the underlying controller trajectories. The UI
therefore does not synthesize or imply per-proposal playback. It links to the
single sealed Stage-0 replay package whose complete trajectories actually
exist. Producing additional campaign replays requires a separately versioned
re-execution/export protocol and cannot be inferred from hashes.

## Research follow-ups

The workbench surfaces, rather than hides, the predeclared no-go results:

- the v2 JAX double-DQN controller failed its synthetic-safety gate (3.125%
  collision rate), so no v2 Waymax development or validation campaign ran;
- the exact-planning-scene LiDAR Gaussian field covered 23.66% of debugger
  trajectories, below its 90% linkage gate;
- the real WOD Perception 3DGS/LiDAR assets remain useful for visual sensor
  inspection but are not registered to the WOMD planning claim.

No extra technology is included solely as a résumé keyword, and no paid
service is required.
