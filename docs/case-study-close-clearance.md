# Case study: a small margin is not a discovered regression

**Question:** Does shifting a lead vehicle's braking by 0.2 seconds and scaling
its speed to 87.9% expose a failure that the conservative reference avoids?

**Answer for this measured case:** No. The tested controller's minimum signed
clearance falls from 0.295291 m to 0.032252 m, while the reference retains
4.796619 m. Both still complete the rollout successfully. The tested-failure
gate does not pass, so PlanMargin does **not** report a qualifying regression.

This case is useful because a dashboard that highlights only “3 cm clearance”
could imply a failure that its own execution evidence does not support.

## Reproduce

Complete the [planning setup](running-experiments.md), including the optional
empirical-support build if you want to evaluate the realism gate. In **New
experiment**, select:

- Recorded scenario: **8**
- Braking onset shift: **+0.2 seconds**
- Lead speed multiplier: **0.879**

Click **Run experiment**. After completion, open **Finding gates and integrity**,
then **Open this experiment replay → Inspect minimum clearance**. Export the
result JSON if you want to compare the underlying numbers.

Equivalent command, with the workbench stopped:

```bash
uv run --frozen planmargin-run-experiment \
  --selection-order 8 --onset 0.2 --speed 0.879
```

The first execution documented here ran on Apple silicon with Python 3.11.15,
JAX 0.10.2, and Waymax revision
`a64dfec9be8576b60d9cecc94f406d9812d4a7d0`. It took about 86 seconds including
source loading. That is one observation, not a latency guarantee.

## Measured comparison

All values below are minimum signed separation to the selected lead vehicle,
in meters, over the entire 81-state trace. They are not distances between the
tested and reference controllers.

| Controller | Original scene | Changed scene | Changed rollout |
| --- | ---: | ---: | --- |
| Tested Waymax IDM configuration | 0.295291 | 0.032252 | Succeeded |
| Conservative reference IDM configuration | 4.977286 | 4.796619 | Succeeded |

Original and changed trajectories were each executed twice per controller.
All repeated trajectory hashes matched. The mutation passed the physical/map
checks and the empirical-support gate; the conformity score was 0.333333,
against the protocol's 0.05 threshold. This is **not** a safety probability.

Five gates passed. The sixth—**tested planner fails**—did not. No outcome was
relabelled to manufacture a positive finding.

## Why the rejection path matters too

Scenario 8 with the same +0.2 s onset but **0.90×** speed was rejected before
the changed planner comparison: `mutated_progress_exceeds_recorded_route`.
The altered trajectory would extend beyond the recorded path. That attempt
is retained as a rejected mutation, not a collision, pipeline success, or
missing result silently replaced with another replay.

An engineer can distinguish three separate questions:

1. Did the experiment execute correctly?
2. Was the proposed scenario change valid and supported by recorded behavior?
3. Did the tested controller fail while the reference succeeded?

The UI and exported result keep those answers separate.

## Reproduction boundary

This is an **exploratory single-case execution**, separate from the frozen
3,200-proposal development campaign. The configuration was chosen after seeing
the campaign's close-clearance cases; it is not a preregistered held-out result.
The two controllers are Waymax IDM configurations, not the Waymo Driver.

The local selection manifest hash for this run was
`8cfb6d310eefe8f0fee28b6edc0fab9ee7d9fe1968d10d14fbc1749fa105d341`;
the support-model hash was
`a4e6e3cc7c6d7318408d478db2eead533fd3a743a8b9559a038bac77eaa4a439`.
Compare those inputs before interpreting a numerical mismatch. Fresh setup
metadata, job IDs, elapsed times, and whole-result hashes may differ; controller
trajectory hashes and metrics are the relevant execution comparison.

The documented changed tested trajectory hash is
`da52cab7fe13bd0408e71f3de6f1d5cedd14acc605f9ad8a7cc5451056db0feb`;
the reference hash is
`6fcb72c2280d5ed898ae622acb5b41f7fc8050a91571eb1527fa522f2eb2f74d`.

Raw source identifiers, trajectories, and screenshots of the licensed scene are
kept local, not distributed with this case study. The experiment result retains
configuration, controller/source provenance, outcome gates, and integrity hashes
so an authorized engineer can reproduce it independently.
