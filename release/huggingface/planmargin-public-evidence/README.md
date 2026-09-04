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
- the original 128-scenario and scaled 1,024-scenario trajectory-model results;
- two active-risk qualification decisions over 2,097 real proposal targets;
- two sealed TensorRT decisions from a free-tier Tesla T4;
- two C++17 TensorRT runtime benchmarks;
- one residual-only FP16 Apple-MPS proxy awaiting TensorRT measurement;
- one shielded-controller synthetic qualification no-go;
- one sustained command-dropout protection qualification;
- one timed assistance-handoff qualification;
- one sealed simulation test-operations report;
- a deterministic SHA-256 manifest.

## What is intentionally excluded

No Waymo scenario IDs, source shards, record indices, camera frames, LiDAR points,
3D Gaussian files, per-cell records, proposal parameters, or trajectories are in
this package. Those records remain in an authorized local evidence store.

The campaign evaluated 3,200 proposals across 100 matched cells and found zero
qualifying planner failures. Bayesian search improved the support-and-pipeline-valid
rate from 54.5625% to 69.3750%; H3 was supported, while H1 and H2 were untestable
because neither method found a qualifying failure.

The scaled trajectory model produced 0.4184 m ADE and 1.1668 m FDE on 12,832
complete-scenario test windows, versus 0.8705 m and 2.3419 m for constant
velocity. A clean repeat produced byte-identical weights and ONNX.

The active-risk ensemble did not pass promotion: mean scene-held-out Spearman
was 0.1372, it beat matched random selection at budget eight in 3 of 9 scenes,
and interval coverage was 0.5451. No learned selector was exported.

The original 128-scenario TensorRT model remains qualified: FP16 ran at 0.1967
ms batch-1 p50 latency and 1.009M samples/s at batch 256; a separate C++17
driver measured 0.1243 ms. The scaled-model run measured 0.277 ms FP32 batch-1
end-to-end p50 and 0.153 ms in C++17. FP16 RMSE passed, but 0.101 m maximum drift
exceeded its frozen 0.075 m gate, so scaled FP16 promotion is a measured no-go.

The residual-only FP16 candidate passed the unchanged numerical gates on Apple
MPS, but has not been measured by TensorRT and remains unpromoted. The shielded
RL follow-up reached a 2.686% collision rate in its synthetic evaluation and
missed its frozen 1% gate, so it did not advance to a real-WOMD campaign.

The off-nominal behavior track used ten deterministic real-WOMD training
scenes. Sustained command loss manifested in all ten unprotected runs, while the
conservative fallback succeeded in all ten protected scenes and passed 80/80
gates. A separate timed assistance contract passed 90/90 gates, including exact
fault, request, resolution, and recovery transitions. Together they add 120
physical rollouts and 9,600 Waymax steps. They are bounded research tests, not
production fault-protection, human remote assistance, or safety claims.

The test-operations record reconciles campaign, analytics, replay, fault, and
assistance evidence into seven independently owned SLOs. It contains aggregate
health and issue-triage data only.

## Use

```bash
hf download ethanvillalovoz/planmargin-public-evidence \
  --repo-type dataset \
  --local-dir planmargin-public-evidence
python verify.py
```

The model weights and ONNX graph are available from the public
[trajectory-model-v2 GitHub release](https://github.com/ethanvillalovoz/planmargin/releases/tag/trajectory-model-v2).
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
methods. The scaled trajectory model used 1,024 WOMD training scenarios with an
820/102/102 scenario split. These results do not evaluate the production Waymo
Driver, establish real-world safety, or represent a production autonomy benchmark.
