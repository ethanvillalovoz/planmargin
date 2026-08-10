# Stage 0: WOMD access and Waymax baseline

## Question

Can the local Apple-silicon environment securely stream one authorized WOMD
scenario and reproduce a complete, unmodified Waymax rollout bit-for-bit?

## Configuration

- WOMD Motion Dataset 1.3.1 validation split
- fixed shard `00000-of-00150`, first TFExample only
- Waymax 0.1.0 at commit
  `a64dfec9be8576b60d9cecc94f406d9812d4a7d0`
- `StateDynamics`
- expert log-playback for the SDC and log playback for uncontrolled objects
- seed 0
- 80 future steps, or eight simulated seconds
- local JAX CPU backend on an arm64 Mac

The full transitive Python environment is pinned in `uv.lock`.

## Command

```bash
./scripts/verify_womd_access.sh
uv sync --frozen
uv run planmargin-waymax-smoke-test \
  --output artifacts/stage-0/waymax-smoke-test.json
```

## Result

The run passed. Both 80-step rollouts produced the same trajectory SHA-256.

The observed process peak resident memory was 1,522,040,832 bytes (about
1.42 GiB). The first rollout, including JIT compilation, took 0.110 seconds;
the warm repeat took 0.087 seconds. Streaming and parsing the first 2.75 MB
record took 4.78 seconds during this run. These are feasibility observations,
not controlled performance benchmarks.

At the final timestep, the SDC had zero built-in Waymax log divergence,
overlap, and offroad values, as expected for expert playback. The ignored local
JSON report contains metric summaries, environment versions, timings, hashes,
and the scenario identifier. It contains no raw WOMD trajectory or map data and
must not be committed.

## Interpretation and limitations

This result validates access, parsing, environment compatibility, full-horizon
execution, and exact repeatability for one scenario. It does not validate a
learned planner, mutation logic, scenario representativeness, planner quality,
or safety. Metric aggregates exclude padded object slots and are not used as a
project claim; only the SDC baseline values are integrity checks.

That next step is now complete. The
[ten-scenario selection report](scenario-selection.md) records the bounded
preferred-family probe, declared fallback decision, and deterministic baseline
validation. The next experiment can introduce the first bounded lead-vehicle
mutation.

## Dataset attribution

This software was made using the Waymo Open Dataset, provided by Waymo LLC
under the [Waymo Dataset License Agreement for Non-Commercial Use](https://waymo.com/open/terms/),
and access and use are governed by that agreement.
