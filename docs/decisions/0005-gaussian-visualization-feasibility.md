# ADR 0005: Freeze the Waymo-linked Gaussian visualization gate

- **Status:** accepted; evaluated `no_go`
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
  `selection_order = 2`, which is the scenario in the sealed Stage 0 rollout
  collection and authenticated real debugger. Do not substitute a scene after
  checking this scenario or viewing Gaussian results.
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

## Result

The frozen scenario was evaluated twice locally on the M4 Pro. A private,
content-sealed binding validates the downloaded sensor-only record against the
selected scenario and its source hash (the sensor proto has no internal ID).
The field file
was byte-identical and the logical fingerprint was identical across clean fits.
The input, determinism, scale, compute, and geometric-quality gates passed:

| Aggregate | Observed |
| --- | ---: |
| Frames | 11 (6 fit / 5 evaluation) |
| Gaussian primitives | 75,000 |
| Binary PLY size | 4.86 MiB |
| Fit-and-score runtime | 3.76 s |
| Peak RSS | 702.1 MiB |
| Median nearest-mean distance | 0.105 m |
| 90th-percentile nearest-mean distance | 0.172 m |
| Evaluation points within 0.50 m | 98.44% |
| Median / maximum XY coordinate error | 0.151 m / 0.171 m |
| Valid trajectory samples inside expanded crop | **23.66%** |

The trajectory-linkage threshold was 90%, so the result is `no_go`. This is not
a reconstruction failure: the sensor field covers the first 1.1 seconds around
the current pose, while the debugger compares 8-second rollout trajectories
that travel beyond the frozen 40-meter crop. Expanding the crop, shortening the
trajectory metric, substituting another scene, or reclassifying the gate after
seeing this result would violate the precommitted protocol.

Consequently PlanMargin retains the existing map-and-trajectory debugger and
does not ship the Gaussian field, its private endpoint, or a renderer. The
ignored private manifest remains the machine-readable audit record. The
data-free decoder, fitter, PLY writer, schema, and privacy tests remain as the
reproducible feasibility implementation—not as a product capability.

## Claim boundary

A passing implementation may be described as a deterministic, trajectory-linked
LiDAR Gaussian field rendered with Gaussian splatting. It may not be described
as photorealistic 3DGS, learned scene reconstruction, a production Waymo scene,
or planner-safety evidence. The official held-out split remains unopened
regardless of this decision.

## Pre-execution correction

The first committed protocol named `selection_order = 1` solely because it was
the earliest frozen selection. A metadata-only lookup confirmed that its LiDAR
object existed, after which inspection of the already-sealed product contract
showed that the real debugger trajectory belongs to `selection_order = 2`.
Order 1's LiDAR payload was downloaded but never decoded, rendered, fitted, or
scored. Before any Gaussian result was observed, the input was corrected to the
existing debugger scenario so the trajectory-linkage gate is meaningful. This
correction is preserved in Git history and does not change any quantitative
threshold. No further scenario substitution is permitted.
