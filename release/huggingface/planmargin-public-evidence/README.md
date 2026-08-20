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

# PlanMargin public campaign evidence

This package contains the public, aggregate-only result of PlanMargin's immutable
Waymax counterfactual-search campaign. It is sufficient to inspect the campaign
decision, compare random and Bayesian search, and reproduce the published
hypothesis decisions without downloading scenario-level Waymo Open Dataset data.

## What is included

- one aggregate campaign record;
- two method records;
- three preregistered hypothesis decisions;
- a deterministic SHA-256 manifest.

## What is intentionally excluded

No Waymo scenario IDs, source shards, record indices, camera frames, LiDAR points,
3D Gaussian files, per-cell records, proposal parameters, or trajectories are in
this package. Those records remain in an authorized local evidence store.

The campaign evaluated 3,200 proposals across 100 matched cells and found zero
qualifying planner failures. Bayesian search improved the support-and-pipeline-valid
rate from 54.5625% to 69.3750%; H3 was supported, while H1 and H2 were untestable
because neither method found a qualifying failure.

## Use

```bash
hf download YOUR_HF_USERNAME/planmargin-public-evidence \
  --repo-type dataset \
  --local-dir planmargin-public-evidence
python verify.py
```

Replace `YOUR_HF_USERNAME` after publication. This staging directory
can be uploaded only after the author has completed the Waymo distribution review.

## Source and attribution

PlanMargin is an independent research project and is not affiliated with or
endorsed by Waymo. The experiment used the Waymo Open Motion Dataset through
Waymax. Review the [Waymo Open Dataset terms](https://waymo.com/open/terms/) before
using any underlying Waymo data. This package contains only aggregate research
outputs, not a copy of the Waymo Open Dataset.

## Claim boundary

This bounded simulator study used ten training scenarios, five seeds, and two
search methods. It does not evaluate the production Waymo Driver, establish
real-world safety, or provide held-out performance evidence.
