# Real-WOMD 1,024-scenario scale study

PlanMargin's second PyTorch trajectory-model study tests whether the existing
TensorRT-friendly temporal Conv1d architecture remains useful when the corpus
grows from 128 to 1,024 real WOMD scenarios. This is an engineering scale study,
not a preregistered superiority experiment.

## Protocol

- source: Waymo Open Motion Dataset v1.3.1 training TFExamples;
- source shards: 16;
- scenario count: 1,024;
- maximum contribution: 128 windows per scenario;
- split unit: complete scenario, never window;
- split: 820 train / 102 validation / 102 test scenarios;
- optimizer: deterministic PyTorch AdamW on the M4 Pro MPS backend;
- training: 24 epochs, batch size 512;
- output: deterministic model bundle plus dynamic-batch ONNX opset 18;
- baseline: constant-velocity extrapolation from the same recorded history.

The source records and cache remain local under the WOD terms. The tracked
result contains aggregate counts, metrics, gates, and model hashes only.

## Result

| Complete-scenario test evidence | Model | Constant velocity |
| --- | ---: | ---: |
| ADE | **0.418 m** | 0.870 m |
| FDE | **1.167 m** | 2.342 m |
| Windows | 12,832 | 12,832 |

Across all splits the bounded cache contained 126,992 real-data windows. A
second clean training run from the same sealed cache produced byte-identical
model and ONNX files:

- model SHA-256: `6e557177c57126fc51fb066033147f316d253126aecb165b3f767d4f04ef8660`;
- ONNX SHA-256: `38934ad17b8ea04698feccf116c6c75a030788124b096c25d99a942386aa73d7`.

The larger corpus is intentionally more diverse than the earlier 128-scenario
study, so its absolute errors are not compared as if both tests were the same
distribution. The supported statement is that the same small deployable model
beats its constant-velocity baseline on a 102-scenario real-WOMD holdout and is
byte-reproducible on the tested MPS toolchain.

## Reproduce locally

```bash
uv run --frozen planmargin-train-torch-trajectory \
  --cache artifacts/experiment-v7/womd-window-cache.npz \
  --output artifacts/experiment-v7/torch-trajectory-model \
  --scenario-count 1024 \
  --shard-count 16 \
  --max-windows-per-scenario 128 \
  --epochs 24 \
  --batch-size 512 \
  --device mps \
  --refresh-cache
```
