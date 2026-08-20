"""Data-free tests for product readiness and authorized sensor bootstrap."""

from __future__ import annotations

from pathlib import Path

import pytest

from planmargin import workspace


def test_empty_clone_reports_each_private_capability_without_faking_readiness(
    tmp_path: Path,
) -> None:
    (
        tmp_path / "release" / "huggingface" / "planmargin-public-evidence" / "data"
    ).mkdir(parents=True)
    bundle = tmp_path / "release" / "huggingface" / "planmargin-public-evidence"
    for relative in ("README.md", "manifest.json", "verify.py", "data/campaign.jsonl"):
        (bundle / relative).write_text("{}\n", encoding="utf-8")

    report = workspace.inspect_workspace(tmp_path)

    assert report.public_ready
    assert isinstance(report.native_build_ready, bool)
    assert not report.evidence_ready
    assert not report.sensor_ready
    assert not report.research_program_ready
    assert not report.full_workbench_ready
    assert {item.scope for item in report.capabilities} >= {
        "public",
        "authorized local",
        "authorized local derivative",
        "optional external",
    }


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
