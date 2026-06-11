from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def write_zip_bundle(run_dir: Path, output_path: Path | None = None) -> Path:
    output_path = output_path or run_dir.with_suffix(".zip")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(run_dir.parent))
    return output_path
