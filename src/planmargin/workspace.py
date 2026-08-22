"""Inspect and prepare the local PlanMargin product workspace.

The public repository is intentionally data-free.  This module makes that
boundary executable: ``doctor`` reports exactly which product surfaces are
ready, while ``bootstrap-sensor`` downloads only the pinned authorized WOD
Perception components and builds the local sensor scene.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from planmargin.evidence_api import EvidencePaths, EvidenceRepository

SEGMENT_ID = "10023947602400723454_1120_000_1140_000"
WOD_BUCKET = "gs://waymo_open_dataset_v_2_0_1/training"
WOD_COMPONENTS = (
    "camera_image",
    "camera_box",
    "camera_calibration",
    "lidar",
    "lidar_calibration",
    "vehicle_pose",
)
SHARP_REVISION = "1eaa046834b81852261262b41b0919f5c1efdd2e"
SHARP_ARCHIVE = f"https://github.com/apple/ml-sharp/archive/{SHARP_REVISION}.tar.gz"
SHARP_ARCHIVE_SHA256 = (
    "3bfb4ec58d31611687293194815fa0763182db9bb4042d2a069c2063fa972682"
)
SHARP_MODEL_URL = "https://ml-site.cdn-apple.com/models/sharp/sharp_2572gikvuh.pt"
SHARP_MODEL_SHA256 = "94211a75198c47f61fca7d739ba08a215418d8d398d48fddf023baccc24f073d"

ReadinessLevel = Literal["public", "evidence", "full"]


@dataclass(frozen=True)
class Capability:
    """One user-visible workspace capability and its remediation."""

    capability: str
    ready: bool
    scope: str
    detail: str
    next_command: str | None = None


@dataclass(frozen=True)
class ReadinessReport:
    """Machine-readable product readiness, not a scientific result."""

    public_ready: bool
    native_build_ready: bool
    evidence_ready: bool
    proposal_replay_ready: bool
    sensor_ready: bool
    torch_trajectory_ready: bool
    tensorrt_qualified: bool
    research_program_ready: bool
    full_workbench_ready: bool
    capabilities: tuple[Capability, ...]


def _regular_files(paths: tuple[Path, ...]) -> bool:
    return all(path.is_file() and not path.is_symlink() for path in paths)


def _public_bundle_ready(root: Path) -> bool:
    directory = root / "release" / "huggingface" / "planmargin-public-evidence"
    return _regular_files(
        (
            directory / "README.md",
            directory / "manifest.json",
            directory / "verify.py",
            directory / "data" / "campaign.jsonl",
        )
    )


def _native_build_ready() -> tuple[bool, str]:
    compiler = shutil.which("c++")
    if compiler is None:
        return False, "No C++ compiler is available."
    probe = subprocess.run(
        [compiler, "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.returncode != 0:
        message = (probe.stderr or probe.stdout).strip().splitlines()
        return False, message[-1] if message else "The C++ compiler probe failed."
    return True, probe.stdout.strip().splitlines()[0]


def _evidence_ready(root: Path) -> tuple[bool, str]:
    try:
        EvidenceRepository(EvidencePaths.from_root(root)).open()
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError) as error:
        return False, str(error)
    return (
        True,
        "The sealed campaign, analytics database, and planning replay verified.",
    )


def _proposal_replay_ready(root: Path) -> tuple[bool, str]:
    repository = EvidenceRepository(EvidencePaths.from_root(root))
    try:
        repository.open()
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError) as error:
        return False, str(error)
    count = repository.proposal_replay_count
    if count == 0:
        return (
            False,
            "No separately retained exact campaign proposal replay is present.",
        )
    return True, f"{count} exact campaign proposal replay package(s) verified."


def _sensor_ready(root: Path) -> tuple[bool, str]:
    repository = EvidenceRepository(EvidencePaths.from_root(root))
    try:
        summary, _ = repository.sensor_scene()
        for frame_index in range(int(summary["frame_count"])):
            repository.sensor_frame(frame_index)
        repository.sensor_annotations()
        repository.sensor_asset("reconstruction")
        repository.sensor_asset("reconstruction_reference")
        repository.sensor_asset("lidar")
        repository.sensor_trajectory()
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError) as error:
        return False, str(error)
    return (
        True,
        f"{summary['frame_count']} camera frames, native annotations, 3DGS, and LiDAR verified.",
    )


def _gaussian_study_ready(root: Path) -> tuple[bool, str]:
    repository = EvidenceRepository(EvidencePaths.from_root(root))
    try:
        summary, _ = repository.gaussian_field()
    except (FileNotFoundError, NotADirectoryError, ValueError, OSError) as error:
        return False, str(error)
    return (
        True,
        "The planning-linked Gaussian study is sealed with decision "
        f"{summary['decision']!r} and trajectory linkage "
        f"{summary['trajectory_linkage_fraction']:.2%}.",
    )


def _beam_study_ready(root: Path) -> tuple[bool, str]:
    from planmargin import beam_features

    outputs = (
        root / "artifacts" / "beam-features" / "final-program-audit-v1",
        root / beam_features.DEFAULT_OUTPUT_DIR,
    )
    previous = Path.cwd()
    failures: list[str] = []
    manifest = None
    try:
        os.chdir(root)
        for output in outputs:
            if not output.is_dir():
                continue
            try:
                manifest = beam_features.audit(output)
            except (
                FileNotFoundError,
                NotADirectoryError,
                ValueError,
                OSError,
            ) as error:
                failures.append(f"{output.name}: {error}")
            else:
                break
    finally:
        os.chdir(previous)
    if manifest is None:
        detail = "; ".join(failures) or "No sealed Beam feature output is present"
        return False, detail
    source = manifest["source"]
    return (
        True,
        f"Beam reconciled {source['accepted_event_count']} accepted events from "
        f"{source['shard_count']} sealed shards into eight Parquet partitions and DuckDB.",
    )


def _rl_study_ready(root: Path) -> tuple[bool, str]:
    import jsonschema

    from planmargin import rl_controller

    directory = root / rl_controller.DEFAULT_OUTPUT_DIR
    report_path = directory / "training-report.json"
    checkpoint_path = directory / "controller.pmzip"
    try:
        if not _regular_files((report_path, checkpoint_path)):
            raise FileNotFoundError(
                "The RL qualification report or checkpoint is missing"
            )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        schema = json.loads(
            (
                root / "schemas" / "rl-controller-training-report-v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator(schema).validate(report)
        sealed = dict(report)
        expected_seal = sealed.pop("report_sha256")
        if (
            rl_controller._sha256(rl_controller._canonical_json(sealed))
            != expected_seal
        ):
            raise ValueError("The RL qualification report seal is invalid")
        checkpoint = checkpoint_path.read_bytes()
        if len(checkpoint) != report["checkpoint_bytes"]:
            raise ValueError("The RL checkpoint size does not match its report")
        if rl_controller._sha256(checkpoint) != report["checkpoint_sha256"]:
            raise ValueError("The RL checkpoint hash does not match its report")
        parameters = rl_controller.load_checkpoint(checkpoint)
        if (
            rl_controller.parameter_fingerprint(parameters)
            != report["parameter_fingerprint"]
        ):
            raise ValueError("The RL checkpoint parameters do not match its report")
        expected_status = (
            "synthetic_go" if all(report["gates"].values()) else "synthetic_no_go"
        )
        if report["status"] != expected_status:
            raise ValueError("The RL decision is inconsistent with its frozen gates")
    except (
        FileNotFoundError,
        NotADirectoryError,
        ValueError,
        OSError,
        json.JSONDecodeError,
        jsonschema.ValidationError,
    ) as error:
        return False, str(error)
    return (
        True,
        f"The deterministic JAX controller and sealed {report['status']!r} decision verified.",
    )


def _trajectory_model_ready(root: Path) -> tuple[bool, str]:
    from planmargin import trajectory_model

    directory = root / trajectory_model.DEFAULT_OUTPUT_DIR
    report_path = directory / "training-report.json"
    model_path = directory / "trajectory-model.pmzip"
    try:
        if not _regular_files((report_path, model_path)):
            raise FileNotFoundError("The real WOMD trajectory model is missing")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        sealed = dict(report)
        expected_seal = sealed.pop("report_sha256")
        if (
            trajectory_model._sha256(trajectory_model._canonical_json(sealed))
            != expected_seal
        ):
            raise ValueError("The trajectory-model report seal is invalid")
        payload = model_path.read_bytes()
        if (
            len(payload) != report["model_bytes"]
            or trajectory_model._sha256(payload) != report["model_sha256"]
        ):
            raise ValueError("The trajectory-model artifact does not match its report")
        trajectory_model.load_model(payload)
        if (
            report.get("synthetic") is not False
            or report.get("status") != "visualization_qualified"
        ):
            raise ValueError("The real-data model is not visualization-qualified")
    except (
        FileNotFoundError,
        ValueError,
        OSError,
        json.JSONDecodeError,
        KeyError,
    ) as error:
        return False, str(error)
    metrics = report["metrics"]["test"]
    return (
        True,
        "The real WOMD JAX model verified with scenario-level holdout "
        f"({metrics['ade_m']:.3f} m ADE, {metrics['fde_m']:.3f} m FDE; no baseline-superiority claim).",
    )


def _torch_trajectory_ready(root: Path) -> tuple[bool, str]:
    from planmargin import torch_trajectory_model

    directory = root / torch_trajectory_model.DEFAULT_OUTPUT_DIR
    report_path = directory / "training-report.json"
    model_path = directory / "trajectory-model.pmtorch"
    onnx_path = directory / "trajectory-model.onnx"
    try:
        if not _regular_files((report_path, model_path, onnx_path)):
            raise FileNotFoundError("The PyTorch/ONNX trajectory model is missing")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        sealed = dict(report)
        expected_seal = sealed.pop("report_sha256")
        if (
            torch_trajectory_model._sha256(
                torch_trajectory_model._canonical_json(sealed)
            )
            != expected_seal
        ):
            raise ValueError("The PyTorch trajectory report seal is invalid")
        model = model_path.read_bytes()
        onnx = onnx_path.read_bytes()
        if (
            len(model) != report["model_bytes"]
            or torch_trajectory_model._sha256(model) != report["model_sha256"]
            or len(onnx) != report["onnx_bytes"]
            or torch_trajectory_model._sha256(onnx) != report["onnx_sha256"]
        ):
            raise ValueError("The PyTorch/ONNX artifacts do not match their report")
        torch_trajectory_model.load_model(model)
        if (
            report.get("synthetic") is not False
            or report.get("status") != "deployment_candidate"
            or not all(report.get("gates", {}).values())
        ):
            raise ValueError("The real-data deployment gates did not all pass")
    except (
        FileNotFoundError,
        ValueError,
        OSError,
        json.JSONDecodeError,
        KeyError,
    ) as error:
        return False, str(error)
    metrics = report["metrics"]["test"]
    return (
        True,
        "The real WOMD PyTorch/ONNX model verified on complete held-out scenarios "
        f"({metrics['ade_m']:.3f} m ADE vs {metrics['constant_velocity_ade_m']:.3f} m baseline).",
    )


def _tensorrt_qualified(root: Path) -> tuple[bool, str]:
    path = root / "experiments" / "tensorrt-qualification-v1.json"
    try:
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError("No published TensorRT qualification report is present")
        report = json.loads(path.read_text(encoding="utf-8"))
        if (
            report.get("record_type")
            != "planmargin.tensorrt_qualification_report"
            or report.get("source_model_training_data", {}).get("synthetic")
            is not False
            or report.get("redistribution") != "aggregate_only"
            or report.get("status") != "qualified"
            or not all(report.get("gates", {}).values())
        ):
            raise ValueError("The TensorRT qualification gates did not all pass")
    except (FileNotFoundError, ValueError, OSError, json.JSONDecodeError) as error:
        return False, str(error)
    fp16 = report["engines"]["fp16"]["batches"]["1"]
    return (
        True,
        "TensorRT FP32/FP16 parity and CUDA-event benchmarks verified; FP16 batch-1 "
        f"p50 is {fp16['latency_ms']['p50']:.3f} ms.",
    )


def inspect_workspace(root: Path) -> ReadinessReport:
    """Return the exact public, private-evidence, and sensor readiness state."""
    root = root.resolve(strict=True)
    public_ready = _public_bundle_ready(root)
    native_build_ready, native_build_detail = _native_build_ready()
    evidence_ready, evidence_detail = _evidence_ready(root)
    proposal_replay_ready, proposal_replay_detail = _proposal_replay_ready(root)
    sensor_ready, sensor_detail = _sensor_ready(root)
    gaussian_ready, gaussian_detail = _gaussian_study_ready(root)
    beam_ready, beam_detail = _beam_study_ready(root)
    rl_ready, rl_detail = _rl_study_ready(root)
    trajectory_model_ready, trajectory_model_detail = _trajectory_model_ready(root)
    torch_trajectory_ready, torch_trajectory_detail = _torch_trajectory_ready(root)
    tensorrt_qualified, tensorrt_detail = _tensorrt_qualified(root)
    research_program_ready = (
        gaussian_ready
        and beam_ready
        and trajectory_model_ready
        and torch_trajectory_ready
        and tensorrt_qualified
    )
    raw_directory = root / "data" / "raw" / "perception" / SEGMENT_ID
    raw_ready = _regular_files(
        tuple(raw_directory / f"{component}.parquet" for component in WOD_COMPONENTS)
    )
    sharp_path = (
        root / "artifacts" / "real-3dgs" / "waymo-front" / "099-1552440205262596.ply"
    )
    capabilities = (
        Capability(
            "Public aggregate review",
            public_ready,
            "public",
            (
                "The deterministic aggregate evidence bundle is present."
                if public_ready
                else "The tracked aggregate evidence bundle is incomplete."
            ),
            ".venv/bin/python scripts/build_public_evidence_bundle.py",
        ),
        Capability(
            "Native rebuild toolchain",
            native_build_ready,
            "local development",
            native_build_detail,
            "sudo xcodebuild -license  # macOS only; review before accepting",
        ),
        Capability(
            "Campaign investigation",
            evidence_ready,
            "authorized local",
            evidence_detail,
            "uv run --frozen planmargin-run-matched-campaign --readiness-only",
        ),
        Capability(
            "Exact proposal replay",
            proposal_replay_ready,
            "authorized local",
            proposal_replay_detail,
            "uv run --frozen planmargin-retain-proposal-replay --help",
        ),
        Capability(
            "Authorized Perception inputs",
            raw_ready,
            "authorized local",
            (
                "The six pinned WOD v2 Perception Parquet components are present."
                if raw_ready
                else "The pinned WOD v2 Perception components are not all present."
            ),
            "uv run --frozen planmargin-bootstrap-sensor --accept-waymo-terms",
        ),
        Capability(
            "Apple SHARP reconstruction",
            sharp_path.is_file() and not sharp_path.is_symlink(),
            "authorized local derivative",
            (
                "The pinned source-frame SHARP PLY is present."
                if sharp_path.is_file()
                else "The source-frame SHARP PLY has not been generated."
            ),
            "uv run --frozen planmargin-bootstrap-sensor --accept-waymo-terms",
        ),
        Capability(
            "Sensor Lab",
            sensor_ready,
            "authorized local",
            sensor_detail,
            "uv run --frozen planmargin-bootstrap-sensor --accept-waymo-terms",
        ),
        Capability(
            "Planning-linked Gaussian feasibility",
            gaussian_ready,
            "authorized local research",
            gaussian_detail,
            "uv run --frozen planmargin-build-gaussian-field",
        ),
        Capability(
            "Apache Beam feature dataflow",
            beam_ready,
            "authorized local research",
            beam_detail,
            "uv run --frozen planmargin-build-beam-features",
        ),
        Capability(
            "Historical synthetic JAX RL qualification",
            rl_ready,
            "local research record",
            rl_detail,
            "uv run --frozen planmargin-train-rl-controller",
        ),
        Capability(
            "Real WOMD JAX trajectory model",
            trajectory_model_ready,
            "authorized local research",
            trajectory_model_detail,
            "uv run --frozen planmargin-train-trajectory-model --epochs 64",
        ),
        Capability(
            "Real WOMD PyTorch/ONNX trajectory model",
            torch_trajectory_ready,
            "authorized local research",
            torch_trajectory_detail,
            "uv run --frozen --extra nvidia planmargin-train-torch-trajectory",
        ),
        Capability(
            "NVIDIA TensorRT deployment qualification",
            tensorrt_qualified,
            "public aggregate / free Colab",
            tensorrt_detail,
            "Run notebooks/planmargin_tensorrt_colab.ipynb in a free T4 runtime",
        ),
        Capability(
            "Gemini explanation adapter",
            bool(os.environ.get("GEMINI_API_KEY")),
            "optional external",
            (
                "A Gemini key is configured; the adapter still requires explicit free-tier confirmation."
                if os.environ.get("GEMINI_API_KEY")
                else "Not configured. The deterministic local evidence assistant remains available."
            ),
            None,
        ),
    )
    return ReadinessReport(
        public_ready=public_ready,
        native_build_ready=native_build_ready,
        evidence_ready=evidence_ready,
        proposal_replay_ready=proposal_replay_ready,
        sensor_ready=sensor_ready,
        torch_trajectory_ready=torch_trajectory_ready,
        tensorrt_qualified=tensorrt_qualified,
        research_program_ready=research_program_ready,
        full_workbench_ready=(
            evidence_ready
            and proposal_replay_ready
            and sensor_ready
            and research_program_ready
        ),
        capabilities=capabilities,
    )


def _print_report(report: ReadinessReport) -> None:
    state = (
        "FULL WORKBENCH READY" if report.full_workbench_ready else "PARTIAL WORKSPACE"
    )
    print(f"PlanMargin doctor: {state}\n")
    for capability in report.capabilities:
        marker = "READY" if capability.ready else "MISSING"
        print(f"[{marker:7}] {capability.capability} ({capability.scope})")
        print(f"          {capability.detail}")
        if not capability.ready and capability.next_command:
            print(f"          Next: {capability.next_command}")
    print()
    print(
        "Public clone: "
        + ("ready" if report.public_ready else "not ready")
        + " | Native rebuild: "
        + ("ready" if report.native_build_ready else "not ready")
        + " | Local evidence: "
        + ("ready" if report.evidence_ready else "not ready")
        + " | Exact replay: "
        + ("ready" if report.proposal_replay_ready else "not ready")
        + " | Sensor Lab: "
        + ("ready" if report.sensor_ready else "not ready")
        + " | Research program: "
        + ("ready" if report.research_program_ready else "not ready")
    )


def doctor_main() -> None:
    parser = argparse.ArgumentParser(
        description="Report exact PlanMargin product readiness"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--require", choices=("public", "evidence", "full"), default="public"
    )
    args = parser.parse_args()
    report = inspect_workspace(args.root)
    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        _print_report(report)
    ready = {
        "public": report.public_ready,
        "evidence": report.evidence_ready,
        "full": report.full_workbench_ready,
    }[args.require]
    if not ready:
        raise SystemExit(1)


def _download_perception(root: Path, *, accept_terms: bool) -> None:
    destination = root / "data" / "raw" / "perception" / SEGMENT_ID
    destination.mkdir(parents=True, exist_ok=True)
    missing = [
        component
        for component in WOD_COMPONENTS
        if not (destination / f"{component}.parquet").is_file()
    ]
    if not missing:
        print("WOD Perception inputs: already present")
        return
    if not accept_terms:
        raise SystemExit(
            "Downloading WOD requires --accept-waymo-terms after you register at "
            "waymo.com/open and review the current non-commercial license."
        )
    gcloud = shutil.which("gcloud")
    if gcloud is None:
        raise SystemExit(
            "Google Cloud CLI is required to download authorized WOD files"
        )
    for component in missing:
        source = f"{WOD_BUCKET}/{component}/{SEGMENT_ID}.parquet"
        target = destination / f"{component}.parquet"
        partial = target.with_suffix(".parquet.partial")
        print(f"Downloading authorized {component} component...")
        subprocess.run(
            [gcloud, "storage", "cp", source, str(partial)],
            check=True,
        )
        if not partial.is_file() or partial.stat().st_size == 0:
            raise SystemExit(f"Downloaded component is empty: {component}")
        partial.replace(target)


def _safe_extract(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, mode="r:gz") as source:
        members = source.getmembers()
        roots = {Path(member.name).parts[0] for member in members if member.name}
        if len(roots) != 1:
            raise SystemExit("Apple SHARP archive has an unexpected layout")
        resolved = destination.resolve()
        for member in members:
            if not (member.isfile() or member.isdir()):
                raise SystemExit("Apple SHARP archive contains an unsupported entry")
            target = (destination / member.name).resolve()
            if not target.is_relative_to(resolved):
                raise SystemExit("Apple SHARP archive contains an unsafe path")
        source.extractall(destination)
    return destination / roots.pop()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download_verified(url: str, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    urllib.request.urlretrieve(url, partial)
    if _sha256(partial) != expected_sha256:
        partial.unlink(missing_ok=True)
        raise SystemExit(f"Downloaded file failed SHA-256 verification: {url}")
    partial.replace(destination)


def _install_sharp(root: Path) -> Path:
    tool = root / "data" / "tools" / "ml-sharp"
    executable = tool / ".venv" / "bin" / "sharp"
    if executable.is_file():
        return executable
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("uv is required to install the pinned Apple SHARP environment")
    tool.parent.mkdir(parents=True, exist_ok=True)
    if not tool.is_dir():
        print("Downloading pinned Apple SHARP source...")
        with tempfile.TemporaryDirectory(prefix="planmargin-sharp-") as temporary:
            temporary_path = Path(temporary)
            archive = temporary_path / "sharp.tar.gz"
            _download_verified(SHARP_ARCHIVE, archive, SHARP_ARCHIVE_SHA256)
            extracted = _safe_extract(archive, temporary_path / "source")
            shutil.move(str(extracted), str(tool))
    subprocess.run([uv, "venv", "--python", "3.13", str(tool / ".venv")], check=True)
    subprocess.run(
        [
            uv,
            "pip",
            "sync",
            str(tool / "requirements.txt"),
            "--python",
            str(tool / ".venv" / "bin" / "python"),
        ],
        cwd=tool,
        check=True,
    )
    if not executable.is_file():
        raise SystemExit("Apple SHARP installation completed without its CLI")
    return executable


def _sharp_checkpoint(root: Path) -> Path:
    candidates = (
        root / "data" / "tools" / "ml-sharp" / "checkpoints" / "sharp_2572gikvuh.pt",
        Path.home()
        / ".cache"
        / "torch"
        / "hub"
        / "checkpoints"
        / "sharp_2572gikvuh.pt",
        Path.home()
        / "Library"
        / "Caches"
        / "torch"
        / "hub"
        / "checkpoints"
        / "sharp_2572gikvuh.pt",
    )
    for candidate in candidates:
        if candidate.is_file() and _sha256(candidate) == SHARP_MODEL_SHA256:
            return candidate
    destination = candidates[0]
    print("Downloading and verifying the pinned Apple SHARP model (about 2.6 GB)...")
    _download_verified(SHARP_MODEL_URL, destination, SHARP_MODEL_SHA256)
    return destination


def bootstrap_sensor_main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the authorized local Camera/3DGS/LiDAR Sensor Lab"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--accept-waymo-terms", action="store_true")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-sharp-install", action="store_true")
    parser.add_argument(
        "--device", choices=("default", "cpu", "mps", "cuda"), default="default"
    )
    args = parser.parse_args()
    root = args.root.resolve(strict=True)
    if not args.skip_download:
        _download_perception(root, accept_terms=args.accept_waymo_terms)
    sharp = (
        root / "data" / "tools" / "ml-sharp" / ".venv" / "bin" / "sharp"
        if args.skip_sharp_install
        else _install_sharp(root)
    )
    checkpoint = _sharp_checkpoint(root)
    command = [
        sys.executable,
        str(root / "scripts" / "prepare_perception_scene.py"),
        "--root",
        str(root),
        "--generate-sharp",
        "--sharp-command",
        str(sharp),
        "--device",
        args.device,
        "--sharp-checkpoint",
        str(checkpoint),
    ]
    subprocess.run(command, check=True)
    report = inspect_workspace(root)
    _print_report(report)
    if not report.sensor_ready:
        raise SystemExit("Sensor bootstrap finished without a verified Sensor Lab")
