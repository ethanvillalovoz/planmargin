# Stage 0 trajectory-visualization protocol

Issue #6 requires one engineer-readable comparison before the production
Angular debugger. The Stage 0 artifact is a self-contained HTML document with
two inline SVG panels generated exclusively from rollout-record schema 1.1.0.

## Analytical question

How do the tested and reference SDC trajectories differ between the original
and counterfactual scenario, where is the mutated actor at the same state, and
does any controller first fail during the rollout?

The artifact uses spatial small multiples because position and alignment are
the evidence. It does not use 3D, animation, or hover: those would add decoding
cost without adding information at this stage.

## Visual encoding

- original and counterfactual scenarios occupy separate panels with the same
  metric bounds and coordinate transform;
- sampled WOMD roadgraph geometry is quiet gray context;
- the tested SDC is a solid blue path and oriented footprint;
- the reference SDC is a dashed orange path and footprint;
- the mutation target is a dotted purple path and footprint;
- a red cross marks the first failing state when one exists; and
- a visible table reports outcome, overlap, offroad, first failure, and final
  timestep for all four rollouts.

Color is redundant with line pattern and direct labels. Each SVG has a title
and long description, and the metric table provides the non-visual path. At
narrow widths the panels stack while keeping the spatial evidence before the
table and notes. Print styling preserves the same reading order.

## Record-only regeneration

First regenerate the private comparison and schema 1.1 rollout collection,
then run:

```bash
uv run --frozen planmargin-render-trajectory-comparison \
  --input artifacts/stage-0/rollout-records.json \
  --output artifacts/stage-0/trajectory-comparison.html
```

The generator has no network or browser-runtime dependency. Parsing, scales,
oriented-box geometry, SVG rendering, labels, annotations, and the text table
are deterministic Python functions covered by synthetic tests.

## Privacy and limitations

The HTML contains private scenario-derived roadgraph samples, actor tracks,
and trajectories. It belongs only under the ignored `artifacts/` directory and
must never be committed or publicly hosted. The repository commits the
generator, schemas, data-free tests, protocol, and privacy-safe aggregate
result only.

This view is a trace debugger for a single feasibility case. It is not a
planner benchmark, a production Waymo Driver evaluation, a legal or
responsibility model, or evidence of general safety performance.
