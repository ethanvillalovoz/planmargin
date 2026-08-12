"""Data-free tests for deterministic LiDAR Gaussian field machinery."""

from __future__ import annotations

import zlib
from pathlib import Path

import numpy as np
import pytest

from planmargin import gaussian_field
from planmargin.womd_lidar_proto import DeltaEncodedData


def _encode_delta(tensor: np.ndarray, precision: np.ndarray) -> bytes:
    quantized = np.rint(tensor / precision).astype(np.int64)
    flattened = np.transpose(quantized, (2, 0, 1)).reshape(-1)
    nonzero = flattened[flattened != 0]
    residual = nonzero.copy()
    residual[1:] -= nonzero[:-1]
    mask = flattened != 0
    changes = np.r_[0, np.flatnonzero(mask[1:] != mask[:-1]) + 1]
    runs = np.diff(np.r_[changes, len(mask)])
    if not mask[0]:
        runs = np.r_[0, runs]
    encoded = DeltaEncodedData()
    encoded.residual.extend(residual.tolist())
    encoded.mask.extend(runs.tolist())
    encoded.metadata.shape.extend(tensor.shape)
    encoded.metadata.quant_precision.extend(precision.tolist())
    return zlib.compress(encoded.SerializeToString())


def test_delta_decoder_matches_wire_layout_and_quantization() -> None:
    tensor = np.array(
        [
            [[0.0, 1.2, 0.0], [2.5, 0.0, -3.0]],
            [[1.0, 2.4, 4.0], [0.0, 0.0, 6.0]],
        ],
        dtype=np.float64,
    )
    precision = np.array([0.5, 0.1, 1.0])
    decoded = gaussian_field.decompress_delta(_encode_delta(tensor, precision))
    np.testing.assert_allclose(decoded, tensor, atol=1e-6)


def test_gaussian_fit_and_ply_are_byte_deterministic() -> None:
    grid = np.stack(
        np.meshgrid(
            np.linspace(-5.0, 5.0, 24),
            np.linspace(-5.0, 5.0, 24),
            np.linspace(-1.0, 1.0, 10),
            indexing="ij",
        ),
        axis=-1,
    ).reshape(-1, 3)
    intensity = np.linspace(0.0, 1.0, len(grid))
    first = gaussian_field.fit_gaussians(grid, intensity)
    second = gaussian_field.fit_gaussians(grid, intensity)
    assert all(np.array_equal(left, right) for left, right in zip(first, second))
    first_ply = gaussian_field.write_splat_ply(*first)
    second_ply = gaussian_field.write_splat_ply(*second)
    assert first_ply == second_ply
    assert first_ply.startswith(b"ply\nformat binary_little_endian 1.0\n")
    assert f"element vertex {len(first[0])}\n".encode() in first_ply[:1024]


def test_private_input_rejects_escape_and_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    outside = tmp_path / "outside.tfrecord"
    outside.write_bytes(b"record")
    link = artifacts / "link.tfrecord"
    link.symlink_to(outside)
    with pytest.raises(gaussian_field.GaussianFieldError, match="under artifacts"):
        gaussian_field._private_file(outside)
    with pytest.raises(gaussian_field.GaussianFieldError, match="symlink"):
        gaussian_field._private_file(link)


def test_trajectory_linkage_scores_all_valid_samples() -> None:
    trace = {
        "x_m": [0.0, 41.0, 43.0],
        "y_m": [0.0, 0.0, 0.0],
        "z_m": [0.0, 0.0, 0.0],
        "valid": [True, True, True],
    }
    rollouts = {
        "records": [{"trajectory": trace}],
        "scene_context": {
            "actors": {
                "mutation_target": {"original": trace, "counterfactual": trace}
            }
        },
    }
    assert gaussian_field._trajectory_linkage(rollouts, np.zeros(3)) == pytest.approx(2 / 3)
