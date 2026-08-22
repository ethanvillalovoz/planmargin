# TensorRT trajectory runner

This C++17 executable loads a serialized PlanMargin TensorRT engine, validates
the fixed tensor contract, warms the engine, and reports device-only and
application-facing end-to-end latency percentiles as one JSON record.

It is intentionally NVIDIA-only. Build it in the free Colab qualification
notebook or another Linux CUDA/TensorRT environment:

```bash
cmake -S cpp/tensorrt -B build/tensorrt \
  -DTENSORRT_ROOT=/path/to/TensorRT
cmake --build build/tensorrt --parallel
build/tensorrt/planmargin_tensorrt_runner \
  --engine artifacts/experiment-v4/tensorrt-qualification/trajectory-fp32.engine \
  --batch 1 --warmup 50 --iterations 500 --mode both
```

`device_latency_ms` uses CUDA events around `enqueueV3`. The stricter
`end_to_end_latency_ms` uses a host monotonic clock around pinned-host input,
both asynchronous host-to-device copies, `enqueueV3`, the device-to-host output
copy, and stream synchronization. Input decoding and application-specific
feature extraction remain outside both boundaries.

`--mode device` and `--mode end-to-end` isolate either measurement. The default
`--mode both` reports both and computes throughput from the end-to-end mean.
