# NVIDIA inference qualification

PlanMargin's deployable trajectory path is a deliberately small temporal
convolutional residual network trained on real WOMD motion tracks. It accepts
one second of local-frame history, predicts three seconds of future motion, and
exports to ONNX with a dynamic batch axis.

## What is measured

The free-Colab protocol builds separate TensorRT FP32 and FP16 engines and
records for both device-only and end-to-end execution:

- p50, p95, and p99 CUDA-event device latency after 50 warm-up executions;
- p50, p95, and p99 host-clock latency from pinned-host inputs through H2D,
  `enqueueV3`, D2H, and synchronized pinned-host output;
- throughput at batch sizes 1, 8, and 256;
- FP32 and FP16 numerical drift from the same PyTorch prediction;
- CPU-versus-GPU batch-1 latency;
- GPU identity, compute capability, memory, exact framework versions, and
  SHA-256 hashes for the ONNX graph and both engines.

Dataset I/O, feature extraction, and engine deserialization are excluded and
called out as such. The C++17 runner reports both distributions in one JSON
record and bases application-facing throughput on the end-to-end mean.

## Reproduce for free

Open [`notebooks/planmargin_tensorrt_colab.ipynb`](../notebooks/planmargin_tensorrt_colab.ipynb)
in a free Colab T4 runtime and run every cell. The notebook downloads the
hash-pinned 1,024-scenario model-only release, qualifies both engine precisions,
compiles the C++17 runner, and downloads an aggregate-only evidence bundle. It
does not need WOMD access and never downloads or publishes source records.
Weights and ONNX are public model-only artifacts; TensorRT engines remain local
because they are rebuilt for the selected GPU.

The same Python entry points can be used on any Linux NVIDIA host:

```bash
uv sync --frozen --extra nvidia
uv pip install --python .venv/bin/python tensorrt-cu12==11.2.1.2
uv run --frozen planmargin-qualify-tensorrt \
  --model-dir artifacts/experiment-v7/torch-trajectory-model \
  --output artifacts/experiment-v7/tensorrt-qualification
```

The C++ runner and build instructions live in [`cpp/tensorrt`](../cpp/tensorrt).

## Result boundary

The scaled run is sealed in
`experiments/tensorrt-qualification-v2.json`; its independent C++17 result is in
`experiments/tensorrt-cpp-benchmark-v2.json`. On a free Tesla T4, FP32 batch-1
end-to-end p50 was 0.277 ms and passed numerical parity. The C++17 pinned-host
runner measured 0.153 ms p50. FP16 batch-1 end-to-end p50 was 0.393 ms and
batch-256 throughput was 0.975M samples/s. Its 0.0065 m RMSE passed, but maximum
drift reached 0.101 m at batch 256 and exceeded the frozen 0.075 m gate.

The result is therefore a measured **no-go for scaled-model FP16 promotion**,
not a missing run. FP32 remains a measured deployment path. The earlier
128-scenario model keeps its independent qualified report in
`experiments/tensorrt-qualification-v1.json`; its values are never inherited by
the scaled model.

## Claim boundary

This is inference qualification for a bounded research trajectory predictor.
It is not a benchmark of the Waymo Driver, a production autonomy claim, or a
safety claim. The WOMD test partition here consists of complete scenarios held
out from this repository's training partition; it is not Waymo's official
challenge test server.
