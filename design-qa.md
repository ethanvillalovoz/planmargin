# Design QA — full-shell Waymo public-language pass

Date: 2026-09-04

## Source truth

The complete source audit is recorded in
`docs/audits/waymo-product-language-2026-09-04/audit.md`.

Public visual references:

- https://waymo.com/
- https://waymo.com/research/
- https://waymo.com/open/
- https://waymo.com/safety/impact/
- https://careers.withwaymo.com/jobs/2027-summer-intern-ms-software-engineering-behavior-test-san-francisco-california-united-states
- https://waymo.com/blog/2023/10/waymo-advances-ai-research-with-our-multifunctional-waymax-simulator/

This is a public visual-language study, not a representation of private Waymo
software. PlanMargin keeps its own name and icon; no Waymo trademark, brand
artwork, proprietary typeface, or generated imagery is included.

## Capture conditions

- Public source captures: 1280 × 720 at 1× density.
- Product captures: 1664 × 1080 at 1× density.
- Product state: local evidence verified with real retained replay and campaign
  evidence loaded.
- Exact reference/product pairs were combined and inspected locally. Those
  temporary comparisons are excluded to avoid redistributing Waymo media.

## Iteration record

1. **P1 — The shell still looked like a generic dark dashboard.** Replaced the
   hard-edged, all-dark chrome with a warm-neutral application surface, white
   rounded work areas, dark navy type, blue pill actions, green status chips,
   and whitespace-led grouping grounded in Waymo's public product surfaces.
2. **P1 — The simulator reference did not extend to the rest of the product.**
   Rebuilt the global navigation, campaign header, rails, release inspector,
   Evidence workspace, and Model & Runtime view as one consistent system.
3. **P1 — A global light token accidentally changed the simulation canvas.**
   Isolated the Waymax-derived colors inside the replay component so the scene
   remains black with semantic green, yellow, gray, and magenta trajectories.
4. **P2 — The replay reserved an obsolete 280 px left gutter.** Expanded the
   real trajectory scene to the full canvas and realigned its label, scale,
   legend, and rollout guide.
5. **P2 — The raw scenario identifier looked unfinished.** Humanized the main
   campaign title while retaining the exact plan identifier as metadata.
6. **P2 — Documentation still showed the previous shell.** Replaced the real
   Campaign and Coverage captures and added a real Evidence-workspace capture.
7. **P2 — Visual states could not be reproduced directly.** Added local query
   parameters for Campaign sections and Evidence subviews, with unit coverage.
8. **P2 — The new component theme crossed the previous style warning budget.**
   Raised the explicit component-style budget by four kilobytes and verified a
   clean production build without warnings.

## Visual comparison result

- The navigation now follows the public Waymo pattern of sparse top-level
  choices and soft active pills rather than a bordered developer tab strip.
- Primary actions are visually singular and blue; healthy evidence state is
  green; warning and simulation colors remain semantic.
- Campaign and Evidence use large rounded headings and clear plain-language
  decisions, while technical identifiers stay secondary.
- The dark replay remains the dominant engineering artifact and is framed by a
  calmer light shell rather than competing dark panels.
- Evidence and Model & Runtime read as operational workspaces, not landing-page
  advertisements.

## Interaction and build verification

- Campaign Replay, Coverage, and Issues state logic: covered by frontend tests.
- Direct Campaign-section and Evidence-subview initialization: covered by new
  frontend tests.
- Planning replay timeline and one-second stepping: covered by frontend tests.
- Real camera, LiDAR, and 3DGS behavior: unchanged and retained in the same
  simulator workspace.
- Frontend formatting and strict TypeScript checks: passed.
- Frontend unit tests: 64 passed.
- Production build: passed without size-budget warnings.
- Python suite: 296 passed.
- Python lint, native source/wheel build, and npm dependency audit: passed.

## Final review

No P0, P1, or P2 visual issue remains in the audited desktop journey. The shell
now reflects Waymo's public hierarchy, spacing, shape, and color language while
remaining an independent PlanMargin product and preserving every evidence
boundary.

final result: passed
