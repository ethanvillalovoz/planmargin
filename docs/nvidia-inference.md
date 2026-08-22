# NVIDIA inference qualification

PlanMargin's deployable trajectory path is a deliberately small temporal
convolutional residual network trained on real WOMD motion tracks. It accepts
one second of local-frame history, predicts three seconds of future motion, and
exports to ONNX with a dynamic batch axis.

## What is measured

The free-Colab protocol builds separate TensorRT FP32 and FP16 engines and
records:

- p50, p95, and p99 device latency after 50 warm-up executions;
- throughput at batch sizes 1, 8, and 256;
- FP32 and FP16 numerical drift from the same PyTorch prediction;
- CPU-versus-GPU batch-1 latency;
- GPU identity, compute capability, memory, exact framework versions, and
  SHA-256 hashes for the ONNX graph and both engines.

The benchmark clock is a pair of CUDA events around `enqueueV3`. Dataset I/O,
feature extraction, and engine deserialization are excluded and called out as
such in the report.

## Reproduce for free

Open [`notebooks/planmargin_tensorrt_colab.ipynb`](../notebooks/planmargin_tensorrt_colab.ipynb)
in a free Colab T4 runtime and run every cell. The notebook authenticates WOMD
at the original Google Cloud source, rebuilds the model, qualifies both engine
precisions, compiles the C++17 runner, and downloads an aggregate-only evidence
bundle. It never publishes raw WOMD examples, model weights, or TensorRT
engines.

The same Python entry points can be used on any Linux NVIDIA host:

```bash
uv sync --frozen --extra nvidia
uv pip install --python .venv/bin/python tensorrt-cu12==11.2.1.2
uv run --frozen planmargin-train-torch-trajectory --device cuda --refresh-cache
uv run --frozen planmargin-qualify-tensorrt
```

The C++ runner and build instructions live in [`cpp/tensorrt`](../cpp/tensorrt).

## Claim boundary

This is inference qualification for a bounded research trajectory predictor.
It is not a benchmark of the Waymo Driver, a production autonomy claim, or a
safety claim. The WOMD test partition here consists of complete scenarios held
out from this repository's training partition; it is not Waymo's official
challenge test server.
