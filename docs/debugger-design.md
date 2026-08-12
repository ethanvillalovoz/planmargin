# Scenario debugger design specification

The thin debugger is a local engineering instrument built from code-native UI,
Three.js geometry, and a bundled synthetic fixture. The accepted desktop and
mobile concepts are retained solely as implementation references:

- [desktop concept](assets/debugger/desktop-concept.png)
- [mobile concept](assets/debugger/mobile-concept.png)

## Visual system

| Token | Value | Responsibility |
| --- | --- | --- |
| App background | `#080d11` | global shell and canvas |
| Raised rail | `#0b1217` | run/evidence rails and mobile sheets |
| Primary text | `#f3f6f8` | titles and active values |
| Secondary text | `#aab4bc` | labels and inactive controls |
| Divider | `#3b464e` | panel and section boundaries |
| Subtle grid | `#162129` | canvas and chart grids |
| Tested | `#ff7900` | tested trajectory and metric series |
| Reference | `#17b9d6` | reference trajectory and metric series |
| Recorded | `#858d93` | recorded trajectory and metric series |
| Success | `#73d12f` | supported/succeeds values |
| Failure | `#ff3b30` | failure and threshold values |

Typography uses `Inter`, then the operating-system sans-serif stack. Titles are
600 weight; labels and controls are 500; evidence values are 400. Desktop UI
chrome uses a 12–14 px scale, while mobile uses 14–17 px for touch readability.
Corners remain square except for 2 px control rounding and circular trajectory
markers. Shadows, glass, glow, gradients, and decorative cards are prohibited.

## Desktop composition

- 56 px top bar: `PlanMargin`, `Scenario debugger`, `Campaign results`,
  `Open run`, `Export view`.
- 210 px run rail: run metadata, Original/Proposal 01/Proposal 02 selection,
  playback controls, time, step, and speed.
- Flexible scene canvas: roadgraph, conflict region, three trajectories,
  current vehicle states, legend, scale, and north marker.
- 300 px evidence rail: Mutation, Validity, Controller outcomes, Provenance.
- 210 px bottom timeline: scrubber plus signed-separation and longitudinal-TTC
  plots synchronized to the scene.

## Mobile composition

The mobile shell does not compress all desktop panels. It provides a shared
`Scene` / `Evidence` / `Metrics` view selector. Scene is the default and shows
the canvas, compact legend, playback row, Proposal 02 summary, and the beginning
of the first metric plot to communicate scroll continuation.

## Allowed visible copy

Above the fold may contain only the accepted concepts' interface strings and
the following accessibility equivalents:

- `PlanMargin`, `Scenario debugger`, `Open run`, `Export view`
- `RUN`, `PROPOSALS`, `Original`, `Proposal 01`, `Proposal 02`
- `synthetic-demo-v1`, `lead_braking_fixture`, `local_fixture`, `Demo fixture`
- `Scene`, `Evidence`, `Metrics`, `Tested`, `Reference`, `Recorded`
- `Mutation`, `Validity`, `Controller outcomes`, `Provenance`
- `Onset`, `Speed`, `Supported (fixture)`, `Deterministic`, `All checks passed`
- `Fails`, `Succeeds`, `Qualifying (synthetic)`, `Bundled demo data`
- `Signed separation`, `Longitudinal TTC`, `Real-time`

The synthetic disclosure is mandatory. The interface must not claim to inspect
the production Waymo Driver, name a real map or person, or expose restricted
record fields.

The `Campaign results` surface is the sole exception to the synthetic fixture
copy above. It contains only the already-published campaign aggregates: method
budgets, valid rates, zero finding counts, H1/H2/H3 decisions, total physical
cost, reconstruction/analytics evidence, the isolated native-kernel benchmark,
and the held-out/production-driver claim boundary. It contains no scenario,
cell, proposal, controller-trace, feature-vector, or support-score record.

## Component ownership

- `DebuggerStore`: selected proposal, timestep, playing state, mobile view.
- `RunRail`: metadata, proposal selection, transport controls.
- `SceneViewport`: Three.js lifecycle, resizing, trajectories, vehicle state.
- `EvidenceInspector`: deterministic evidence sections from typed fixture data.
- `MetricTimeline`: shared scrubber and two SVG plots.
- `CampaignSummary`: aggregate-only campaign evidence and explicit claim scope.
- `MobileViewNav`: responsive region selection without duplicated state.
- `ExportService`: stable, synthetic-view JSON export.

No generated bitmap is consumed by the application. The concepts define the
visual contract; the shipped scene, plots, controls, labels, and icons are
rendered from Angular, CSS, SVG, and Three.js.

## Verification contract

The shipped slice is deliberately synthetic-only. A run is rendered only when
it passes `planmargin.debugger.v1` validation: positive fixed timestep, finite
geometry and metrics, unique proposal identifiers, aligned trajectory and
metric lengths, deterministic/support flags, and a timeline matching the
declared step. Local files are capped at 5 MB. View exports contain selection
and timestep metadata, not trajectory arrays or private provenance fields.

Before merge, the implementation must pass:

- strict TypeScript compilation, Vitest unit tests, and the Angular production
  build under the pinned Node 24 runtime;
- a dependency audit at moderate severity or higher;
- desktop browser checks for selection, playback, synchronized evidence and
  metrics, and export feedback;
- mobile browser checks at 390 × 844 for Scene, Evidence, and Metrics view
  switching, playback, and timeline scrubbing; and
- a console review with no warnings or errors.

The concept images were generated for this repository as visual references.
They are documentation artifacts and are never loaded by the runtime.
