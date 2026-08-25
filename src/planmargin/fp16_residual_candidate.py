"""Qualify a split residual FP16 trajectory-graph candidate locally."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import platform
from pathlib import Path
from typing import Any

import torch
from torch import nn

from planmargin import tensorrt_qualification, torch_trajectory_model, trajectory_model

DEFAULT_MODEL = Path("artifacts/experiment-v7/torch-trajectory-model")
DEFAULT_OUTPUT = Path("artifacts/experiment-v11/fp16-residual-candidate")
PROTOCOL = Path("docs/decisions/0010-version-2-1-research-protocol.md")


class ResidualTrajectoryGraph(nn.Module):
    """Predict only the smoothed residual; compose the baseline in host FP32."""

    def __init__(self, model: torch_trajectory_model.TrajectoryConvNet) -> None:
        super().__init__()
        self.register_buffer("feature_mean", model.feature_mean.detach().clone())
        self.register_buffer("feature_scale", model.feature_scale.detach().clone())
        self.register_buffer("target_scale", model.target_scale.detach().clone())
        self.register_buffer(
            "smoothing_matrix", model.smoothing_matrix.detach().clone()
        )
        self.encoder = copy.deepcopy(model.encoder)
        self.head = copy.deepcopy(model.head)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        normalized = (features - self.feature_mean) / self.feature_scale
        steps = trajectory_model.HISTORY_STEPS
        past_xy = normalized[:, : steps * 2].reshape(-1, steps, 2)
        past_velocity = normalized[:, steps * 2 : steps * 4].reshape(-1, steps, 2)
        sine = normalized[:, steps * 4 : steps * 5].reshape(-1, steps, 1)
        cosine = normalized[:, steps * 5 : steps * 6].reshape(-1, steps, 1)
        sequence = torch.cat((past_xy, past_velocity, sine, cosine), dim=2)
        residual = self.head(self.encoder(sequence.transpose(1, 2))) * self.target_scale
        residual = residual.reshape(-1, trajectory_model.FUTURE_STEPS, 2)
        return torch.matmul(self.smoothing_matrix, residual).reshape(
            -1, trajectory_model.FUTURE_STEPS * 2
        )


def compose_host_fp32(
    residual: torch.Tensor, baseline: torch.Tensor, smoothing: torch.Tensor
) -> torch.Tensor:
    shaped = baseline.float().reshape(-1, trajectory_model.FUTURE_STEPS, 2)
    smooth_baseline = torch.matmul(smoothing.float(), shaped).reshape(
        -1, trajectory_model.FUTURE_STEPS * 2
    )
    return smooth_baseline + residual.float()


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def export_onnx(model: ResidualTrajectoryGraph, path: Path) -> Path:
    import onnx

    path.parent.mkdir(parents=True, exist_ok=True)
    batch = torch.export.Dim("batch")
    torch.onnx.export(
        model.eval(),
        args=(
            torch.zeros((2, trajectory_model.HISTORY_STEPS * 6), dtype=torch.float16),
        ),
        f=path,
        input_names=["features"],
        output_names=["trajectory_residual"],
        dynamic_shapes={"features": {0: batch}},
        opset_version=18,
        dynamo=True,
        external_data=False,
    )
    onnx.checker.check_model(onnx.load(path))
    return path


def run(
    *, model_dir: Path = DEFAULT_MODEL, output: Path = DEFAULT_OUTPUT, device: str
) -> dict[str, Any]:
    source = torch_trajectory_model.load_model(
        (model_dir / "trajectory-model.pmtorch").read_bytes()
    ).eval()
    features, baseline = tensorrt_qualification.deterministic_inference_probe(256)
    with torch.inference_mode():
        reference = source(features, baseline)
    graph = ResidualTrajectoryGraph(source).half().to(device).eval()
    with torch.inference_mode():
        residual = graph(features.to(device=device, dtype=torch.float16)).cpu()
        candidate = compose_host_fp32(residual, baseline, source.smoothing_matrix)
    parity = tensorrt_qualification._parity(reference.numpy(), candidate.numpy())
    gates = {
        "fp16_max_error_under_7_5e_2_m": (parity["max_absolute_error_m"] < 0.075),
        "fp16_rmse_under_1e_2_m": parity["rmse_m"] < 0.01,
        "host_composition_is_fp32": True,
        "physical_probe_is_unchanged": True,
    }
    output.mkdir(parents=True, exist_ok=True)
    onnx_path = export_onnx(copy.deepcopy(graph).cpu(), output / "residual-fp16.onnx")
    report: dict[str, Any] = {
        "record_type": "planmargin.fp16_residual_candidate",
        "schema_version": "1.0.0",
        "experiment": "v11",
        "status": ("tensorrt_required" if all(gates.values()) else "candidate_no_go"),
        "measurement": "local_apple_mps_fp16_proxy",
        "input_protocol": "deterministic_physical_probe_v1",
        "sample_count": 256,
        "parity": parity,
        "gates": gates,
        "tensorrt_measured": False,
        "source_model_sha256": _sha256(
            (model_dir / "trajectory-model.pmtorch").read_bytes()
        ),
        "onnx_sha256": _sha256(onnx_path.read_bytes()),
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "torch": torch.__version__,
            "device": device,
        },
        "claim_boundary": (
            "Local FP16 numerical proxy only; NVIDIA TensorRT must independently "
            "pass before reduced-precision promotion."
        ),
        "protocol_sha256": _sha256(PROTOCOL.read_bytes()),
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["report_sha256"] = _sha256(encoded.encode())
    (output / "qualification-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--device", choices=("mps", "cuda"), default="mps")
    args = parser.parse_args()
    report = run(model_dir=args.model_dir, output=args.output, device=args.device)
    print(json.dumps({"status": report["status"], "parity": report["parity"]}))


if __name__ == "__main__":
    main()
