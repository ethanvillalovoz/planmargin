# Stage 0: original-versus-counterfactual visualization

## Question

Can one static, engineer-readable artifact align road geometry, actor
footprints, tested/reference trajectories, mutation configuration, failure
timing, and metric values using only the exported rollout-record collection?

## Configuration

- rollout-record schema 1.1.0;
- one bounded private scene context exported from a clean Git revision;
- two spatial small-multiple SVG panels with one shared metric transform;
- direct labels plus redundant solid, dashed, and dotted line patterns;
- visible outcome and first-failure table; and
- self-contained responsive HTML with no remote runtime dependency.

## Result

The clean private rerun passed and exported four unique variant/controller
records with 81 SDC states each. The bounded scene context retained 65
roadgraph features comprising 2,709 sampled points, one SDC footprint, and 81
original plus 81 counterfactual states for the mutation target. Draft 2020-12
schema validation and the deterministic Python structural validator both
passed.

The generated HTML contained two inline SVG panels and one accessible metric
table. This feasibility case had no controller failure, so the view explicitly
reported no first-failure timestep rather than manufacturing an event marker.
The failure-marker path is covered by a synthetic test.

Fixed desktop and mobile-portrait browser captures were reviewed for shared
scale, road/actor alignment, clipping, label collisions, reading order, and
grayscale-independent series identification. The panels stack on narrow
screens, and the solid/dashed/dotted patterns preserve identity without color
or hover.

## Interpretation and limitations

This validates the record-to-visualization boundary and the first debugging
artifact. It does not establish planner performance, scenario
representativeness, or production safety. The current scene context is bounded
to one mutation target and one SDC footprint; broader actor inspection belongs
in the later engineer-facing debugger.

The private HTML, roadgraph samples, actor tracks, identifiers, hashes, and
screenshots remain under ignored local paths. This report contains only
aggregate counts and methodology.
