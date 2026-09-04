# Design QA — campaign workstation redesign

Date: 2026-09-04

## Source truth

- Public visual target: https://waymo.com/blog/2023/10/waymo-advances-ai-research-with-our-multifunctional-waymax-simulator/
- Implemented product: `docs/assets/planmargin-test-operations-overview-v3.1.jpg`
- Combined source/implementation comparisons were generated and inspected locally, then excluded to avoid redistributing Waymo media.

The source is a public Waymax visualization used as a visual-language target, not a private Waymo interface and not the same driving scenario. Exact actor placement and road geometry are therefore neither expected nor appropriate. The implementation must use only its retained real evidence.

## Capture conditions

- Public source: 1280 × 720, 1× density.
- Product capture: 1648 × 1077, 1× density.
- Product target: desktop simulation-review workstation.
- Product state: local evidence verified, retained replay selected, playback paused at 3.4 seconds.

## Iteration record

1. P1 — The campaign totals and bordered cards displaced the primary engineering artifact. Replaced the dashboard with a persistent campaign rail, dominant replay canvas, release inspector, and synchronized transport.
2. P1 — The replay was too zoomed out to read planner behavior. Added an ego-aligned interaction crop while retaining the measured road geometry.
3. P2 — Overlapping marker labels and page-like chrome reduced legibility. Removed the marker callouts, flattened the shell, tightened typography and dividers, and reserved color for semantics.
4. P1 — The backend exposed the real mutation target but the frontend silently discarded it, leaving three ego outcomes without the interacting actor. Added the typed mutation-target contract, strict parser validation, the moving counterfactual lead vehicle, its original track, and a clear legend.
5. P2 — The earlier README images still showed the generic dashboard. Replaced them with captures from the verified redesigned local product.
6. P1 — The first CI browser pass found that the compact campaign tab row overlapped the scene at mobile width. Changed the compact review grid to size the toolbar from content so controls remain clickable.
7. P1 — Automated WCAG checks found the tertiary label color just below the required contrast ratio on several evidence surfaces. Increased the neutral tertiary token while preserving the subdued hierarchy.
8. P2 — The CI browser suite found an ambiguous accessible-name query for the issue filter because the same phrase also appeared inside a card. Tightened the test to the exact filter control; application behavior was unaffected.

## Interaction verification

- Local-evidence connection and sealed-record state: passed.
- Campaign Replay, Coverage, and Issues tabs: passed.
- Play/pause, one-second step controls, and timeline seek: passed.
- Real mutation-target motion and ego-planner divergence: passed.
- Sensors camera playback with frame-specific annotations: passed.
- Real local 3DGS orbit view: passed.
- Evidence workspace navigation: passed.
- Frontend formatting, strict typecheck, 62 unit tests, and production build: passed.
- Backend suite: 296 tests passed.

## Final review

No P0, P1, or P2 visual or interaction issue remains in the audited desktop journey. The final product is intentionally denser than a marketing demo and intentionally sparser than the public Waymax scene when the retained evidence contains fewer actors.

final result: passed
