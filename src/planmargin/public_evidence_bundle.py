"""Deterministic packaging for PlanMargin's public aggregate evidence."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ARCHIVE_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def build_archive(source: Path, output: Path) -> Path:
    """Write sorted regular files with fixed metadata for stable SHA-256 output."""
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(source.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(source).as_posix()
            info = ZipInfo(relative, date_time=ARCHIVE_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compresslevel=9)
    return output
