# Stage 0: ten-scenario feasibility set

## Outcome

The deterministic preferred-family probe found seven strict SDC-left-turn and
oncoming-path-conflict candidates in training shard `00000-of-01000`. Because
that was fewer than the required ten, the predeclared fallback activated. The
Stage 0 feasibility set therefore contains ten same-route lead-vehicle braking
scenarios; scenario families were not mixed.

## Scan and validation

- WOMD Motion Dataset 1.3.1 training split
- 1 complete shard and 455 records scanned in stored order
- 1,224,394,311 bytes of serialized record payload processed
- 7 strict preferred-family candidates found
- 15 fallback-family candidates passed the sustained-braking and kinematic
  continuity screens
- first 11 screened fallback candidates validated in record order
- 1 rejected because the SDC baseline went offroad
- 10 retained after two identical full-horizon IDM rollouts each
- 75.08 seconds total observed runtime
- 950,697,984 bytes peak process RSS, approximately 0.89 GiB

These are feasibility observations on one machine, not controlled throughput
benchmarks.

## Retained set

The complete per-scenario manifest is generated locally under the ignored
`artifacts/` directory. Scenario identifiers, object indices, derived motion
features, and trajectory hashes are deliberately not published in this
repository.

For every retained scenario:

- both 80-step simulated-trajectory hashes matched exactly;
- the SDC remained valid through timestep 90;
- maximum SDC overlap was zero; and
- maximum SDC offroad was zero.

The local machine-readable report contains the complete thresholds, derived
interaction features, full trajectory hashes, timings, environment versions,
source provenance, and limitations. It contains no raw trajectory or map
content and must not be committed.

## Interpretation

The result supports using lead braking for the first mutation and controller
spike. It does not show that lead braking is more important than unprotected
left turns. It shows only that the fallback produced a coherent ten-scenario
feasibility set inside the declared one-shard probe budget.

The sample is intentionally ordered and non-random. It must not be used for
final comparative claims. Unprotected-left-turn mining remains a later
extension requiring a larger scan budget and separate protection-status
validation.

## Reproduction

```bash
uv run --frozen planmargin-select-scenarios \
  --output artifacts/stage-0/scenario-selection.json
```

## Dataset attribution

This software was made using the Waymo Open Dataset, provided by Waymo LLC
under the [Waymo Dataset License Agreement for Non-Commercial Use](https://waymo.com/open/terms/),
and access and use are governed by that agreement.
