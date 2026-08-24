"""Data-free tests for product readiness and authorized sensor bootstrap."""

from __future__ import annotations

from pathlib import Path

import pytest

from planmargin import workspace


def _bootstrap_readiness(value: bool) -> dict[str, bool]:
    return {
        "evidence": value,
        "proposal_replay": value,
        "sensor": value,
        "gaussian": value,
        "beam": value,
        "trajectory": value,
        "torch_trajectory": value,
    }


def test_empty_clone_reports_each_private_capability_without_faking_readiness(
    tmp_path: Path,
) -> None:
    (
        tmp_path / "release" / "huggingface" / "planmargin-public-evidence" / "data"
    ).mkdir(parents=True)
    bundle = tmp_path / "release" / "huggingface" / "planmargin-public-evidence"
    for relative in (
        "README.md",
        "manifest.json",
        "verify.py",
        "data/campaign.jsonl",
        "data/trajectory-model.json",
        "data/trajectory-model-v2.json",
        "data/active-risk-v1.json",
        "data/active-risk-v2.json",
        "data/tensorrt-qualification.json",
        "data/tensorrt-cpp-benchmark.json",
        "data/tensorrt-qualification-v2.json",
        "data/tensorrt-cpp-benchmark-v2.json",
    ):
        (bundle / relative).write_text("{}\n", encoding="utf-8")

    report = workspace.inspect_workspace(tmp_path)

    assert report.public_ready
    assert isinstance(report.native_build_ready, bool)
    assert not report.evidence_ready
    assert not report.proposal_replay_ready
    assert not report.sensor_ready
    assert not report.torch_trajectory_ready
    assert not report.tensorrt_qualified
    assert not report.scaled_tensorrt_measured
    assert not report.scaled_tensorrt_qualified
    assert not report.research_program_ready
    assert not report.full_workbench_ready
    details = {item.capability: item.detail for item in report.capabilities}
    assert details["Campaign investigation"] == (
        "No authorized local campaign artifacts are present."
    )
    assert details["Exact proposal replay"] == (
        "No retained exact proposal replay is present."
    )
    assert details["Planning-linked Gaussian feasibility"] == (
        "No planning-linked Gaussian study is present."
    )
    assert "Errno" not in " ".join(details.values())
    assert {item.scope for item in report.capabilities} >= {
        "public",
        "authorized local",
        "authorized local derivative",
        "optional external",
    }


def test_scaled_t4_no_go_is_a_complete_decision_not_a_missing_run() -> None:
    root = Path(__file__).parents[1]

    measured, qualified, detail = workspace._scaled_tensorrt_decision(root)

    assert measured
    assert not qualified
    assert "measured no-go" in detail
    assert "0.101 m" in detail


def test_download_requires_explicit_terms_acceptance(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="accept-waymo-terms"):
        workspace._download_perception(tmp_path, accept_terms=False)


def test_download_skips_network_when_all_pinned_components_exist(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "data" / "raw" / "perception" / workspace.SEGMENT_ID
    directory.mkdir(parents=True)
    for component in workspace.WOD_COMPONENTS:
        (directory / f"{component}.parquet").write_bytes(b"parquet")
    monkeypatch.setattr(
        workspace.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("download command should not run"),
    )

    workspace._download_perception(tmp_path, accept_terms=False)


def test_safe_extract_rejects_archive_links(tmp_path: Path) -> None:
    import io
    import tarfile

    archive = tmp_path / "sharp.tar.gz"
    with tarfile.open(archive, "w:gz") as target:
        regular = tarfile.TarInfo("sharp/file.txt")
        regular.size = 2
        target.addfile(regular, io.BytesIO(b"ok"))
        link = tarfile.TarInfo("sharp/link")
        link.type = tarfile.SYMTYPE
        link.linkname = "/tmp/outside"
        target.addfile(link)

    with pytest.raises(SystemExit, match="unsupported entry"):
        workspace._safe_extract(archive, tmp_path / "extract")


def test_verified_download_rejects_wrong_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_download(_: str, destination: Path) -> None:
        destination.write_bytes(b"not the pinned payload")

    monkeypatch.setattr(workspace.urllib.request, "urlretrieve", fake_download)
    output = tmp_path / "payload.bin"

    with pytest.raises(SystemExit, match="SHA-256"):
        workspace._download_verified("https://example.invalid/file", output, "0" * 64)
    assert not output.with_suffix(".bin.partial").exists()


def test_full_bootstrap_plan_covers_every_real_data_product_phase(
    tmp_path: Path,
) -> None:
    steps = workspace._bootstrap_workbench_steps(
        tmp_path,
        _bootstrap_readiness(False),
        device="mps",
        include_frontend=True,
    )
    commands = [step.command for step in steps]
    entrypoints = [command[0] for command in commands]

    assert entrypoints[0] == "npm"
    assert "planmargin-run-matched-campaign" in entrypoints
    assert "planmargin-retain-proposal-replay" in entrypoints
    assert "planmargin-build-beam-features" in entrypoints
    assert "planmargin-train-trajectory-model" in entrypoints
    assert "planmargin-bootstrap-sensor" in entrypoints
    assert "planmargin-build-gaussian-field" in entrypoints
    assert "planmargin-train-torch-trajectory" in entrypoints
    assert "planmargin-train-rl-controller" not in entrypoints
    assert commands[-1][-2:] == ("--require", "full")
    sensor = commands[entrypoints.index("planmargin-bootstrap-sensor")]
    assert sensor[-2:] == ("--device", "mps")


def test_full_bootstrap_reuses_a_complete_workspace(tmp_path: Path) -> None:
    steps = workspace._bootstrap_workbench_steps(
        tmp_path,
        _bootstrap_readiness(True),
        device="default",
        include_frontend=True,
    )

    assert [step.command[0] for step in steps] == ["npm", "planmargin-doctor"]
    assert all(not step.authorized for step in steps)
