"""Qualify the exported trajectory network on an NVIDIA TensorRT runtime.

This module imports TensorRT lazily so the normal macOS development and CI
paths remain data-free and NVIDIA-independent. The intended execution target is
a free Colab GPU runtime using the companion notebook.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch

from planmargin import torch_trajectory_model

DEFAULT_MODEL_DIR = torch_trajectory_model.DEFAULT_OUTPUT_DIR
DEFAULT_OUTPUT_DIR = Path("artifacts/experiment-v4/tensorrt-qualification")
DEFAULT_BATCHES = (1, 8, 256)


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def latency_summary(samples_ms: Iterable[float]) -> dict[str, float]:
    values = np.asarray(tuple(samples_ms), dtype=np.float64)
    if values.ndim != 1 or len(values) == 0 or not np.isfinite(values).all():
        raise ValueError("Latency samples must be a non-empty finite vector")
    return {
        "mean": round(float(values.mean()), 6),
        "p50": round(float(np.percentile(values, 50)), 6),
        "p95": round(float(np.percentile(values, 95)), 6),
        "p99": round(float(np.percentile(values, 99)), 6),
    }


def _load_tensorrt() -> Any:
    try:
        import tensorrt as trt
    except ImportError as error:
        raise RuntimeError("TensorRT is required for NVIDIA qualification") from error
    return trt


def build_engine(
    onnx_path: Path,
    engine_path: Path,
    *,
    fp16: bool,
    max_batch: int,
    workspace_gib: int = 2,
) -> Path:
    trt = _load_tensorrt()
    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    network = builder.create_network(
        1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH)
    )
    parser = trt.OnnxParser(network, logger)
    if not parser.parse(onnx_path.read_bytes()):
        errors = [str(parser.get_error(index)) for index in range(parser.num_errors)]
        raise RuntimeError("TensorRT ONNX parse failed: " + " | ".join(errors))
    config = builder.create_builder_config()
    config.set_memory_pool_limit(
        trt.MemoryPoolType.WORKSPACE, workspace_gib * 1024 * 1024 * 1024
    )
    if fp16:
        if not builder.platform_has_fast_fp16:
            raise RuntimeError("The selected NVIDIA GPU has no fast FP16 support")
        config.set_flag(trt.BuilderFlag.FP16)
    profile = builder.create_optimization_profile()
    profile.set_shape("features", (1, 66), (min(8, max_batch), 66), (max_batch, 66))
    profile.set_shape(
        "constant_velocity", (1, 60), (min(8, max_batch), 60), (max_batch, 60)
    )
    config.add_optimization_profile(profile)
    serialized = builder.build_serialized_network(network, config)
    if serialized is None:
        raise RuntimeError("TensorRT engine build failed")
    engine_path.parent.mkdir(parents=True, exist_ok=True)
    engine_path.write_bytes(bytes(serialized))
    return engine_path


class TensorRTRunner:
    def __init__(self, engine_path: Path) -> None:
        trt = _load_tensorrt()
        self.runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
        self.engine = self.runtime.deserialize_cuda_engine(engine_path.read_bytes())
        if self.engine is None:
            raise RuntimeError(f"Could not deserialize {engine_path}")
        self.context = self.engine.create_execution_context()
        if self.context is None:
            raise RuntimeError("Could not create a TensorRT execution context")

    def infer(
        self, features: torch.Tensor, baseline: torch.Tensor, output: torch.Tensor
    ) -> None:
        batch = int(features.shape[0])
        if not self.context.set_input_shape("features", (batch, 66)):
            raise RuntimeError("TensorRT rejected the features input shape")
        if not self.context.set_input_shape("constant_velocity", (batch, 60)):
            raise RuntimeError("TensorRT rejected the baseline input shape")
        for name, tensor in (
            ("features", features),
            ("constant_velocity", baseline),
            ("trajectory", output),
        ):
            if not self.context.set_tensor_address(name, tensor.data_ptr()):
                raise RuntimeError(f"TensorRT rejected the {name} tensor address")
        if not self.context.execute_async_v3(torch.cuda.current_stream().cuda_stream):
            raise RuntimeError("TensorRT enqueueV3 failed")


def _cuda_benchmark(
    runner: TensorRTRunner,
    features: torch.Tensor,
    baseline: torch.Tensor,
    *,
    warmup: int,
    iterations: int,
) -> tuple[dict[str, float], torch.Tensor]:
    output = torch.empty((len(features), 60), device="cuda", dtype=torch.float32)
    for _ in range(warmup):
        runner.infer(features, baseline, output)
    torch.cuda.synchronize()
    samples: list[float] = []
    for _ in range(iterations):
        start = torch.cuda.Event(enable_timing=True)
        end = torch.cuda.Event(enable_timing=True)
        start.record()
        runner.infer(features, baseline, output)
        end.record()
        end.synchronize()
        samples.append(float(start.elapsed_time(end)))
    return latency_summary(samples), output.detach().cpu().clone()


def _cpu_benchmark(
    model: torch.nn.Module,
    features: torch.Tensor,
    baseline: torch.Tensor,
    *,
    warmup: int,
    iterations: int,
) -> dict[str, float]:
    model.eval()
    with torch.inference_mode():
        for _ in range(warmup):
            model(features, baseline)
        samples: list[float] = []
        for _ in range(iterations):
            start = time.perf_counter_ns()
            model(features, baseline)
            samples.append((time.perf_counter_ns() - start) / 1_000_000)
    return latency_summary(samples)


def _parity(reference: np.ndarray, candidate: np.ndarray) -> dict[str, float]:
    delta = candidate.astype(np.float64) - reference.astype(np.float64)
    return {
        "max_absolute_error_m": round(float(np.abs(delta).max()), 8),
        "rmse_m": round(float(np.sqrt(np.mean(np.square(delta)))), 8),
    }


def deterministic_inference_probe(
    sample_count: int,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Build reproducible, physically plausible tensors for deployment timing.

    Model quality is measured separately on the sealed WOMD scenario holdout.
    Deployment qualification intentionally does not require or redistribute any
    held-out records: latency and numerical parity only need stable, valid-shaped
    inputs that exercise the complete graph.
    """
    if sample_count < 1:
        raise ValueError("sample_count must be positive")
    rng = np.random.default_rng(20260821)
    history_steps = torch_trajectory_model.trajectory_model.HISTORY_STEPS
    future_steps = torch_trajectory_model.trajectory_model.FUTURE_STEPS
    step_seconds = torch_trajectory_model.trajectory_model.STEP_SECONDS
    speeds = rng.uniform(0.0, 24.0, size=(sample_count, 1)).astype(np.float32)
    lateral_speeds = rng.normal(0.0, 0.7, size=(sample_count, 1)).astype(np.float32)
    accelerations = rng.normal(0.0, 1.2, size=(sample_count, 1)).astype(np.float32)
    yaw_rates = rng.normal(0.0, 0.08, size=(sample_count, 1)).astype(np.float32)
    history_time = (
        np.arange(1 - history_steps, 1, dtype=np.float32)[None, :] * step_seconds
    )
    history_velocity_x = speeds + accelerations * history_time
    history_velocity_y = np.repeat(lateral_speeds, history_steps, axis=1)
    history_x = speeds * history_time + 0.5 * accelerations * history_time**2
    history_y = lateral_speeds * history_time
    history_yaw = yaw_rates * history_time
    features = np.concatenate(
        (
            np.stack((history_x, history_y), axis=2).reshape(sample_count, -1),
            np.stack((history_velocity_x, history_velocity_y), axis=2).reshape(
                sample_count, -1
            ),
            np.sin(history_yaw),
            np.cos(history_yaw),
        ),
        axis=1,
    ).astype(np.float32)
    future_time = (
        np.arange(1, future_steps + 1, dtype=np.float32)[None, :] * step_seconds
    )
    baseline = np.stack(
        (speeds * future_time, lateral_speeds * future_time), axis=2
    ).reshape(sample_count, -1)
    return torch.from_numpy(features), torch.from_numpy(baseline.astype(np.float32))


def qualify(
    *,
    model_dir: Path,
    cache_path: Path | None,
    output_dir: Path,
    batches: tuple[int, ...] = DEFAULT_BATCHES,
    warmup: int = 50,
    iterations: int = 500,
) -> Path:
    if not torch.cuda.is_available():
        raise RuntimeError("An NVIDIA CUDA runtime is required")
    report_path = model_dir / "training-report.json"
    training = json.loads(report_path.read_text())
    model = torch_trajectory_model.load_model(
        (model_dir / "trajectory-model.pmtorch").read_bytes()
    )
    sample_count = max(batches)
    if cache_path is None:
        cpu_features, cpu_baseline = deterministic_inference_probe(sample_count)
        input_protocol = "deterministic_physical_probe_v1"
    else:
        config = torch_trajectory_model.TorchTrainingConfig(**training["configuration"])
        scenarios = torch_trajectory_model._read_cache(cache_path)
        scenario_splits = torch_trajectory_model.split_scenarios(scenarios, config.seed)
        test = torch_trajectory_model.combine_scenarios(scenario_splits["test"])
        if len(test.features) < sample_count:
            raise RuntimeError(
                "Held-out sample count is smaller than the largest batch"
            )
        cpu_features = torch.from_numpy(test.features[:sample_count])
        cpu_baseline = torch.from_numpy(test.baseline[:sample_count])
        input_protocol = "sealed_real_womd_holdout"
    with torch.inference_mode():
        reference = model(cpu_features, cpu_baseline).numpy()
    cpu_latency = _cpu_benchmark(
        model,
        cpu_features[:1],
        cpu_baseline[:1],
        warmup=min(warmup, 20),
        iterations=min(iterations, 200),
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    engines: dict[str, Any] = {}
    before_free, total_memory = torch.cuda.mem_get_info()
    for precision, fp16 in (("fp32", False), ("fp16", True)):
        engine_path = build_engine(
            model_dir / "trajectory-model.onnx",
            output_dir / f"trajectory-{precision}.engine",
            fp16=fp16,
            max_batch=max(batches),
        )
        runner = TensorRTRunner(engine_path)
        measurements: dict[str, Any] = {}
        parity: dict[str, Any] = {}
        for batch in batches:
            features = cpu_features[:batch].cuda()
            baseline = cpu_baseline[:batch].cuda()
            latency, prediction = _cuda_benchmark(
                runner,
                features,
                baseline,
                warmup=warmup,
                iterations=iterations,
            )
            measurements[str(batch)] = {
                "latency_ms": latency,
                "throughput_samples_per_second": round(
                    batch * 1000.0 / latency["mean"], 3
                ),
            }
            parity[str(batch)] = _parity(reference[:batch], prediction.numpy())
        engines[precision] = {
            "bytes": engine_path.stat().st_size,
            "sha256": _sha256(engine_path.read_bytes()),
            "batches": measurements,
            "pytorch_fp32_parity": parity,
        }
        del runner
        torch.cuda.empty_cache()
    after_free, _ = torch.cuda.mem_get_info()

    trt = _load_tensorrt()
    result: dict[str, Any] = {
        "record_type": "planmargin.tensorrt_qualification_report",
        "schema_version": "1.0.0",
        "synthetic": False,
        "redistribution": "aggregate_only",
        "status": "qualified",
        "source_training_report_sha256": _sha256(report_path.read_bytes()),
        "source_onnx_sha256": _sha256(
            (model_dir / "trajectory-model.onnx").read_bytes()
        ),
        "measurement": {
            "clock": "CUDA events around TensorRT enqueueV3",
            "input_protocol": input_protocol,
            "input_purpose": "deployment timing and numerical parity only",
            "warmup_iterations": warmup,
            "measured_iterations": iterations,
            "batches": list(batches),
            "cpu_reference_batch_1": cpu_latency,
        },
        "engines": engines,
        "gpu": {
            "name": torch.cuda.get_device_name(0),
            "compute_capability": list(torch.cuda.get_device_capability(0)),
            "total_memory_bytes": total_memory,
            "observed_free_memory_delta_bytes": max(0, before_free - after_free),
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda": torch.version.cuda,
            "tensorrt": trt.__version__,
            "platform": platform.platform(),
        },
        "claim_boundary": "Inference qualification of PlanMargin's bounded research trajectory model; not a production autonomy or safety benchmark.",
    }
    result["gates"] = {
        "fp32_max_error_under_1e_4_m": all(
            item["max_absolute_error_m"] < 1e-4
            for item in engines["fp32"]["pytorch_fp32_parity"].values()
        ),
        "fp16_max_error_under_5e_2_m": all(
            item["max_absolute_error_m"] < 5e-2
            for item in engines["fp16"]["pytorch_fp32_parity"].values()
        ),
        "gpu_faster_than_cpu_at_batch_1": engines["fp32"]["batches"]["1"]["latency_ms"][
            "p50"
        ]
        < cpu_latency["p50"],
    }
    result["status"] = "qualified" if all(result["gates"].values()) else "no_go"
    result["report_sha256"] = _sha256(_canonical_json(result))
    output_path = output_dir / "qualification-report.json"
    output_path.write_bytes(_canonical_json(result))
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="Optional private WOMD cache; omitted by default for a redistributable probe",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--batches", type=int, nargs="+", default=list(DEFAULT_BATCHES))
    args = parser.parse_args()
    if args.warmup < 1 or args.iterations < 10 or min(args.batches) < 1:
        parser.error(
            "warmup/batches must be positive and iterations must be at least 10"
        )
    output = qualify(
        model_dir=args.model_dir,
        cache_path=args.cache,
        output_dir=args.output,
        batches=tuple(args.batches),
        warmup=args.warmup,
        iterations=args.iterations,
    )
    print(output)


if __name__ == "__main__":
    main()
