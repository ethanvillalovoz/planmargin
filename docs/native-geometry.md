# Measured C++20 interaction-metrics kernel

PlanMargin uses one C++20/pybind11 extension for the continuous interaction
metric that is evaluated after controller rollouts. The migration follows a
measured responsibility: aggregate signed oriented-box separation and
longitudinal time to collision across an aligned trace.

## Selection evidence

A data-free Apple-silicon profile compared the three plausible validation
kernels before native code was introduced:

| Python kernel               | Representative input    | Mean latency |
| --------------------------- | ----------------------- | -----------: |
| interaction metrics         | 80 aligned states       |     10.75 ms |
| route-to-polyline distance  | 80 points × 90 segments |     0.312 ms |
| empirical behavior features | 61 states               |     0.028 ms |

For 100 interaction traces, `cProfile` attributed about 90% of cumulative time
to signed oriented-box separation. The largest cost was 166,400 Python/NumPy
point-to-segment calls. This made interaction metrics the bounded native-kernel
candidate; it does not mean geometry dominates end-to-end Waymax execution.

## Native boundary

Python retains track-schema validation, constructs two contiguous `float64`
state matrices, and rounds the scientific outputs to the frozen six-decimal
contract. The C++20 extension owns the per-state loop and computes:

- oriented vehicle corners;
- separating-axis overlap or penetration;
- exact vertex-to-edge distance for disjoint boxes;
- same-route bumper-gap and closing-speed TTC; and
- trace minima over jointly valid states.

The previous Python implementation remains in the package as a private parity
oracle. It is not a runtime fallback that could silently change performance or
numerics.

## Parity and benchmark

Data-free tests cover the existing axis-aligned cases, invalid-state behavior,
shape and finite-value rejection, and 100 deterministic randomized 80-state
traces with arbitrary positions, yaws, velocities, and dimensions. Public
results must equal the Python reference after the frozen rounding step.

Run the isolated benchmark with:

```bash
uv run --frozen planmargin-benchmark-geometry --iterations 200
```

On the development M4 Pro, five 200-iteration runs after warm-up measured
Python medians from 10.35 to 10.75 ms and native-path medians from 17.1 to
17.8 µs: approximately 585× to 619× for this kernel. The native timing includes
Python validation and creation of the two contiguous matrices.

This is a microbenchmark on one deterministic synthetic trace. It is not an
end-to-end campaign-speedup claim: Waymax rollouts and Bayesian acquisition
remain much larger responsibilities, and the completed private campaign was
not rerun to manufacture a wall-clock comparison.
