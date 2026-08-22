# TensorRT trajectory runner

This C++17 executable loads a serialized PlanMargin TensorRT engine, validates
the fixed tensor contract, warms the engine, and reports GPU-event latency
percentiles and throughput as one JSON record.

It is intentionally NVIDIA-only. Build it in the free Colab qualification
notebook or another Linux CUDA/TensorRT environment:

```bash
cmake -S cpp/tensorrt -B build/tensorrt \
  -DTENSORRT_ROOT=/path/to/TensorRT
cmake --build build/tensorrt --parallel
build/tensorrt/planmargin_tensorrt_runner \
  --engine artifacts/experiment-v4/tensorrt-qualification/trajectory-fp32.engine \
  --batch 1 --warmup 50 --iterations 500
```

The benchmark uses CUDA events around `enqueueV3`, so it measures device
inference and deliberately excludes file I/O and host preprocessing.
