# ADR 0005: Freeze the Waymo-linked Gaussian visualization gate

- **Status:** accepted; evaluation pending
- **Date:** 2026-08-12
- **Tracking:** #55

## Context

PlanMargin originally proposed 3D Gaussian splatting as a way to add useful
spatial context to counterfactual trajectory inspection. Adding a dependency,
rendering arbitrary particles, or training on an unrelated scene would not
satisfy that responsibility. The visualization must remain linked to the same
WOMD training evidence, fit the available M4 Pro or Colab Free compute, improve
debugging beyond the existing map/trajectory view, and preserve the restricted
data boundary.

The official Waymo Open Dataset format separates two possible inputs:

- WOMD-LiDAR supplies range images, intensity/elongation features, per-laser
  calibration, frame poses, and the first 1.1 seconds of sensor evidence for a
  motion scenario. The files are keyed by the exact WOMD scenario ID.
- WOMD camera evidence supplies VQ-GAN tokens and embeddings for the first
  second, not raw RGB images. Those features cannot support the photometric
  novel-view loss used by standard radiance-field 3D Gaussian Splatting.

The original reference implementation also requires a CUDA GPU and identifies
24 GB VRAM for paper-quality training. It is not a native M4 path. Community
Metal/MLX ports exist, but their maturity alone cannot repair the missing exact
scenario RGB input.

Sources reviewed before freezing this decision:

- the official [WOD repository and dataset summary](https://github.com/waymo-research/waymo-open-dataset);
- the official [WOMD scenario proto](https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/protos/scenario.proto);
- the official [WOMD LiDAR tutorial](https://github.com/waymo-research/waymo-open-dataset/blob/master/tutorial/tutorial_womd_lidar.ipynb)
  and [LiDAR utilities](https://github.com/waymo-research/waymo-open-dataset/blob/master/src/waymo_open_dataset/utils/womd_lidar_utils.py);
- the official [WOMD camera tutorial](https://github.com/waymo-research/waymo-open-dataset/blob/master/tutorial/tutorial_womd_camera.ipynb);
- the authors' [3D Gaussian Splatting implementation](https://github.com/graphdeco-inria/gaussian-splatting).

## Decision

### Photorealistic radiance-field track: predeclared `no_go`

Do not call a reconstruction photorealistic 3DGS, and do not train the standard
RGB radiance-field objective, unless raw calibrated multi-view images from the
exact v1 WOMD scenario become available under the accepted data terms. Camera
tokens are not a substitute. An unrelated Perception-dataset segment would
break the trajectory/evidence link and is therefore outside this milestone.

### LiDAR Gaussian-field track: gated evaluation

Evaluate an exact-scenario, non-photorealistic Gaussian field in which each
primitive has a three-dimensional mean, anisotropic covariance, opacity, and a
deterministic intensity-derived color. It may own one responsibility: provide
dense spatial context around the existing original/counterfactual trajectories
in the authenticated local debugger. It must be labeled **LiDAR Gaussian
field**, not learned RGB reconstruction, neural rendering, or evidence about
planner quality.

The feasibility spike may implement only the minimum extraction, fitting,
audit, and synthetic-rendering machinery needed to measure the following
frozen gates. Real debugger integration begins only after every mandatory gate
passes.

## Frozen inputs and split

- Use the already-selected experiment-v1 **training** scenario with
  `selection_order = 1`, the earliest item under the frozen selection ordering.
  Do not substitute a scene after checking LiDAR availability or viewing
  Gaussian results.
- Read no official held-out or test split.
- Consume at most the 11 WOMD-LiDAR input frames associated with that scenario.
- Use even-indexed frames for fitting and odd-indexed frames for geometric
  evaluation. The split is fixed before extraction.
- Transform points with the supplied calibration and frame poses into the
  scenario coordinate frame.
- Crop to 40 meters in XY around the SDC at the scenario current step and to
  `[-3, 5]` meters in relative Z.
- Remove returns inside valid tracked-object boxes expanded by 0.5 meters so
  that moving actors do not define the static-context quality score.
- Deterministically cap each source frame at 75,000 retained points before a
  0.25-meter voxel reduction.

## Frozen implementation

For each fitted voxel, calculate the mean and local covariance from at most 16
nearest fitted neighbors. Retain three orthogonal eigenvectors as orientation.
Clamp tangent standard deviations to `[0.08, 0.60]` meters and the normal
standard deviation to `[0.03, 0.20]` meters. Map robustly normalized LiDAR
intensity to a fixed perceptual color ramp and use a fixed opacity of 0.82.

This is deterministic geometry fitting, not gradient-based model training. The
implementation must emit a versioned, content-sealed manifest and a compact
binary or PLY representation under `artifacts/gaussian-field/`. Source IDs,
points, frames, fitted primitives, and local reports remain ignored.

## Go/no-go gates

All mandatory gates must pass on the frozen scenario:

| Gate | `go` threshold |
| --- | --- |
| Authorized exact input | A matching training-split LiDAR record exists, contains 11 frames, and validates against the frozen motion scenario ID without opening held-out data. |
| Determinism | Two clean fits produce identical logical fingerprints and byte-identical published field files. |
| Scale | The fitted field contains 5,000–75,000 finite Gaussian primitives and its compressed representation is at most 32 MiB. |
| Local compute | End-to-end extraction and fit complete on the M4 Pro in at most 15 minutes with peak RSS at most 12 GiB. No paid service is used. |
| Geometric quality | Across the fixed evaluation frames: median nearest-mean distance at most 0.35 m, 90th percentile at most 0.75 m, and at least 75% of retained points within 0.50 m of a fitted Gaussian mean. |
| Trajectory linkage | At least 90% of valid SDC, mutation-target, tested, and reference trajectory samples lie inside the Gaussian crop bounds expanded by 2 m, and coordinate-alignment checks pass. |
| Debugging value | A reviewer can toggle Gaussian context and trajectories independently, inspect field provenance/quality, and return to the existing evidence view without changing a scientific decision. |
| Browser performance | The exact desktop fixture loads at most 75,000 splats in at most 2 s and sustains at least 20 rendered frames/s during a fixed five-second camera orbit at 1440×900 on the M4 Pro. |
| Privacy | The authenticated loopback boundary exposes no scenario ID, source URI, raw range image, raw point list, or unrestricted export; a tracked-file leak scan is empty. |
| Data-free reliability | Synthetic Gaussian fixtures exercise schema, parser, renderer, fallback, limits, and cleanup in CI without WOD credentials. |

If any input, geometry, trajectory, performance, or privacy gate fails, record a
`no_go` with the observed aggregate values and do not force the technology into
the product. Thresholds may not be relaxed after results are observed.

## Claim boundary

A passing implementation may be described as a deterministic, trajectory-linked
LiDAR Gaussian field rendered with Gaussian splatting. It may not be described
as photorealistic 3DGS, learned scene reconstruction, a production Waymo scene,
or planner-safety evidence. The official held-out split remains unopened
regardless of this decision.
