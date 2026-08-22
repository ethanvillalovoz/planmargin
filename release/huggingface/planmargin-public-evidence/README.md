---
pretty_name: PlanMargin Public Campaign Evidence
license: other
language:
  - en
tags:
  - autonomous-driving
  - counterfactual-testing
  - reproducible-research
  - waymax
size_categories:
  - n<1K
---

# PlanMargin public research evidence

This package contains PlanMargin's public, aggregate-only research evidence. It
lets a reviewer inspect the counterfactual-search campaign, the real-WOMD
trajectory-model result, and the measured NVIDIA TensorRT qualification without
downloading scenario-level Waymo Open Dataset data.

## What is included

- one aggregate campaign record;
- two method records;
- three preregistered hypothesis decisions;
- one trajectory-model result trained on 128 real WOMD scenarios;
- one sealed TensorRT qualification report from a free-tier Tesla T4;
- one C++17 TensorRT runtime benchmark;
- a deterministic SHA-256 manifest.

## What is intentionally excluded

No Waymo scenario IDs, source shards, record indices, camera frames, LiDAR points,
3D Gaussian files, per-cell records, proposal parameters, or trajectories are in
this package. Those records remain in an authorized local evidence store.

The campaign evaluated 3,200 proposals across 100 matched cells and found zero
qualifying planner failures. Bayesian search improved the support-and-pipeline-valid
rate from 54.5625% to 69.3750%; H3 was supported, while H1 and H2 were untestable
because neither method found a qualifying failure.

The trajectory model produced 0.3225 m ADE and 0.8888 m FDE on a complete-scenario
test split, beating the constant-velocity baseline. The FP16 TensorRT engine ran
at 0.1967 ms batch-1 p50 latency and 1.009M samples/s at batch 256; a separate
C++17 driver measured 0.1243 ms batch-1 p50 latency. These deployment timings use
deterministic physical probes for timing and numerical parity. Model quality is
reported only on the real-WOMD scenario split.

## Use

```bash
hf download ethanvillalovoz/planmargin-public-evidence \
  --repo-type dataset \
  --local-dir planmargin-public-evidence
python verify.py
```

The model weights and ONNX graph are available from the public
[trajectory-model-v1 GitHub release](https://github.com/ethanvillalovoz/planmargin/releases/tag/trajectory-model-v1).
TensorRT engines are intentionally rebuilt for the target GPU and TensorRT version.
The repository's distribution-policy checks verify that this bundle contains
aggregate records only and excludes licensed scenario-level artifacts.

## Source and attribution

PlanMargin is an independent research project and is not affiliated with or
endorsed by Waymo. This dataset package was made using the Waymo Open Dataset,
provided by Waymo LLC under the Waymo Dataset License Agreement for
Non-Commercial Use, available at
[waymo.com/open/terms](https://waymo.com/open/terms/), and access and use of this
work are governed by the terms and conditions therein. This package contains
only aggregate research outputs, not a copy of the Waymo Open Dataset.

## Claim boundary

The counterfactual study used ten training scenarios, five seeds, and two search
methods. The trajectory model used 128 WOMD training scenarios with a 102/13/13
scenario split. Neither result evaluates the production Waymo Driver, establishes
real-world safety, or represents a production autonomy benchmark.
