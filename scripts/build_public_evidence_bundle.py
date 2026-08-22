"""Build a byte-for-byte deterministic public evidence archive."""

from __future__ import annotations

import argparse
from pathlib import Path

from planmargin.public_evidence_bundle import build_archive


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("dist/planmargin-public-evidence-v2")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "release" / "huggingface" / "planmargin-public-evidence"
    output = (root / args.output).resolve()
    if not output.is_relative_to((root / "dist").resolve()):
        raise SystemExit("Output must remain under dist/")
    archive = build_archive(source, output.with_suffix(".zip"))
    print(archive)


if __name__ == "__main__":
    main()
