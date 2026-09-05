# PlanMargin interface audit — Waymax-grounded redesign

Date: 2026-09-04

## Scope

This audit reviews the locally running PlanMargin product shell against the public visual language of Waymo's Waymax and Waymo Open Dataset motion visualizations. It does **not** claim access to Waymo's private internal tooling. The goal is a credible engineering workstation for behavior-test and pipeline-health work, using PlanMargin's real replay, evidence, sensor, and Gemini capabilities.

## Captured workflow

1. **Connect local workspace**
   - The full-screen modal interrupts orientation before the user can understand the active scenario.
   - The dialog is visually oversized for a single token field and leaves most of the canvas inert.
2. **Open Sensors without local records**
   - This is a marketing hero, not an engineering empty state.
   - The headline consumes the main working area while the actual requirements, dataset status, and next action are secondary.
   - Three vanity totals have no operational relationship to the selected scene.
3. **Review Operations**
   - The information is real, but the hierarchy is a generic dashboard: five KPIs, bordered cards, pipeline list, and attention queue.
   - There is no persistent selected scenario, simulation time, map context, planner comparison, or synchronized evidence.
   - The user must leave Operations to understand what the measurements describe.
4. **Inspect the official Waymax public visualization**
   - The scene is the dominant artifact.
   - Lane geometry is thin and restrained; ego, agents, and route use small, high-salience colors.
   - The visual density comes from spatial evidence, not containers or decoration.
5. **Inspect the official Waymo motion visualization**
   - Agent boxes, trajectories, and road geometry share one synchronized spatial frame.
   - Color encodes object or trajectory meaning rather than branding chrome.

## Findings

### P0 — none

The current interface launches and its core data paths are present.

### P1 — the primary object is wrong

The current product treats campaign totals as the primary object. For behavior-test review, the primary object must be the synchronized scenario replay: map, actors, candidate/reference motion, current frame, injected fault, and release decision. Campaign health should select and contextualize a replay, not replace it.

### P1 — Sensors is a landing page inside a tool

The Sensors route changes from an engineering surface into an advertisement when local evidence is unavailable. A production tool should keep the same workstation frame and explain which records are unavailable, how to connect them, and what aggregate evidence remains inspectable.

### P2 — navigation models pages instead of tasks

`Operations / Scenario lab / Sensors / Research` reads like website navigation. The actual engineering loop is: select a campaign or issue, inspect a synchronized replay, compare candidate/reference behavior and sensor evidence, then record a promotion decision.

### P2 — generic “AI dashboard” styling

The blue-black background, cyan eyebrows, repeated rounded cards, oversized figures, and glow-like status dots create a familiar generated-dashboard aesthetic. Public Waymax visuals are much flatter and more utilitarian: black scene canvas, precise line work, compact controls, and color reserved for semantic objects.

### P2 — evidence provenance is separated from the decision

Dataset identity, record seal, model/runtime state, and Gemini evidence scope should remain visible next to the selected run. Hiding them on separate pages increases the chance of interpreting an aggregate result without its provenance.

## Redesign target

Build one desktop simulation-review workstation:

- a compact global toolbar with campaign, record seal, and local-evidence state;
- a left rail for campaigns, retained scenarios, and issue filters;
- a dominant center replay canvas using the existing PlanMargin simulation visualization;
- a synchronized bottom transport and event timeline;
- a right inspector for test outcome, mutation/fault, SLO evidence, provenance, and Gemini analysis;
- task modes (`Replay`, `Sensors`, `Coverage`) within the selected run rather than disconnected marketing pages;
- graphite/black surfaces, thin neutral dividers, Waymax-like scene geometry, and semantic green/magenta/amber/red accents.

## General health

The initial interface was not presentation-ready. The completed redesign replaces the page-oriented shell with a scene-first campaign workstation, keeps release evidence next to the selected replay, and exposes the real mutation-target trajectory that the earlier frontend discarded. The result preserves the existing evidence boundaries while making the scenario, intervention, planner outcomes, and promotion decision readable in one view.

## Implementation evidence

- `docs/assets/planmargin-test-operations-overview-v3.1.jpg` — final campaign workstation with a real retained replay at 3.4 seconds.
- `docs/assets/planmargin-test-operations-coverage-v3.1.jpg` — final versioned coverage and known-unknowns surface.
- `docs/assets/planmargin-sensor-trajectory-v1.1.png` — real local sensor and trajectory inspection.

The official-source/implementation comparison images used during design QA are intentionally not redistributed in this repository. The public source URLs and the locally captured implementation image are sufficient to reproduce that review without republishing Waymo media.

The public Waymax source and PlanMargin replay are different scenarios, so actor count and road geometry are not expected to match. The validated target is the visual hierarchy and semantic language: a dominant dark spatial canvas, thin road geometry, compact chrome, real moving actors, restrained high-salience trajectory colors, synchronized transport, and adjacent engineering evidence.

## Public sources

- Waymo, “Waymo advances AI research with our multifunctional Waymax simulator”: https://waymo.com/blog/2023/10/waymo-advances-ai-research-with-our-multifunctional-waymax-simulator/
- Waymax research page: https://waymo-prod.appspot.com/research/waymax/
- Waymo Open Dataset overview: https://waymo.com/open/about/
- Waymo Open Motion Dataset: https://waymo.com/intl/it/open/data/motion/
- Waymo Open Dataset repository: https://github.com/waymo-research/waymo-open-dataset
