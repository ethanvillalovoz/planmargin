# PlanMargin full-shell visual audit

Date: 2026-09-04

## Scope and evidence boundary

This pass audits PlanMargin against Waymo's **public** product language. It does
not claim access to, reproduce, or describe a private Waymo engineering tool.
The references were captured directly in the Codex in-app browser before the
implementation was changed. No generated imagery was used.

The exact reference and product screenshots used for side-by-side review were
kept as local QA artifacts and are not redistributed in this repository.

## Public references inspected

- [Waymo home](https://waymo.com/) — white navigation, generous spacing,
  rounded blue actions, and a small number of high-salience controls.
- [Waymo Research](https://waymo.com/research/) — large rounded editorial
  typography, near-black research surfaces, thin separators, restrained green
  accents, and compact technical metadata.
- [Waymo Open Dataset](https://waymo.com/open/) — light/dark contrast, strong
  typographic scale, circular geometry, and cyan/blue data accents.
- [Waymo Safety Impact](https://waymo.com/safety/impact/) — evidence-led
  hierarchy, dark navy framing, large section titles, sparse navigation, and
  plain-language interpretation beside quantitative data.
- [Waymo Careers](https://careers.withwaymo.com/jobs/2027-summer-intern-ms-software-engineering-behavior-test-san-francisco-california-united-states)
  — warm white canvas, dark navy text, rounded metadata chips, and blue pill
  actions.
- [Waymax simulator article](https://waymo.com/blog/2023/10/waymo-advances-ai-research-with-our-multifunctional-waymax-simulator/)
  — black simulation canvas, thin road geometry, small semantic colors, and a
  scene-first visual hierarchy.

## Audit findings

### P1 — only the simulator had a credible visual reference

The earlier redesign made the replay canvas resemble Waymax, but kept a generic
dark developer-dashboard shell around it. The surrounding navigation, campaign
rail, inspector, and controls did not inherit Waymo's public typography, shape,
spacing, or light/dark balance.

### P1 — excessive chrome obscured hierarchy

Nearly every region had a hard border and a dark fill. Small uppercase
monospace labels competed with the scenario, decision, and evidence. Public
Waymo surfaces instead establish hierarchy with scale, whitespace, and a small
number of separators.

### P2 — interaction styling was inconsistent with the public brand

Rectangular controls, yellow active rules, and hard-edged status blocks did not
match the rounded tabs, pill actions, soft status chips, and blue/green accents
seen across Waymo's public product surfaces.

### P2 — the light/dark relationship was missing

Waymo's public work uses dark immersive or technical content inside a broader
editorial system that often includes white or warm-neutral surfaces. The old
PlanMargin shell rendered every object at the same dark visual level.

### P1 — disconnected technical workspaces retained unreadable legacy chrome

A clean-session walkthrough found that Replay and Sensors still used the old
black locked-workspace styling after the rest of the shell moved to a light
system. Because the global tokens had changed, several labels and data values
rendered nearly black on black. This state was not visible during the earlier
connected-only audit.

## Implemented direction

- Rebuilt the global header as a white, low-chrome product bar with a restrained
  PlanMargin lockup, centered pill navigation, a single blue primary action,
  and a green local-evidence state.
- Reframed Campaign as a warm-neutral work surface with white rounded rails and
  inspector panels around the dark technical replay.
- Kept the Waymax-derived simulator canvas black and expanded the scene to use
  its full available width instead of reserving obsolete empty space.
- Replaced repeated dark boxes with whitespace, soft grouping, and subtle
  dividers; retained color only for actions, system state, warnings, and
  simulation semantics.
- Reworked Campaign, Coverage, Evidence, and Model & Runtime into one coherent
  visual system without changing their evidence or safety contracts.
- Rebuilt disconnected Replay and Sensors as first-class empty states with
  readable data-boundary rails, a calm light canvas, and one clear connection
  action.
- Brought the manual-token error and exported investigation report into the
  same visual system, covering the last non-simulator product surfaces.
- Corrected the connection dialog's green primary action after the new
  desktop/mobile Axe gate found its white label below WCAG AA contrast.
- Added direct local view parameters (`view`, `panel`, and `section`) for
  reproducible visual review and documentation capture.
- Replaced the README's Campaign and Coverage screenshots and added a real
  Evidence-workspace screenshot from the verified local application.

## What was deliberately not copied

- Waymo's wordmark, logo, proprietary typeface, brand artwork, and photography.
- Any claim about private Waymo tools or internal design conventions.
- Any generated or decorative image used to imply product capability.

PlanMargin remains visibly independent while using the shared public principles
that matter for this tool: calm hierarchy, evidence-first writing, large rounded
type, soft controls, strong light/dark contrast, and scene-first technical
visualization.
