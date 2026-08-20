"""Build a deterministic zip from the reviewed Hugging Face staging package."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path("dist/planmargin-public-evidence-v1")
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root / "release" / "huggingface" / "planmargin-public-evidence"
    output = (root / args.output).resolve()
    if not output.is_relative_to((root / "dist").resolve()):
        raise SystemExit("Output must remain under dist/")
    archive = shutil.make_archive(str(output), "zip", root_dir=source)
    print(archive)


if __name__ == "__main__":
    main()
