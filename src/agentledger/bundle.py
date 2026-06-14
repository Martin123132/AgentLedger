from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


BUNDLE_MANIFEST_NAME = "agentledger-bundle-manifest.json"
BUNDLE_MANIFEST_SCHEMA = "agentledger.bundle.v1"


def _archive_name(run_dir: Path, path: Path) -> str:
    return path.relative_to(run_dir.parent).as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_bundle_manifest(run_dir: Path, files: list[Path]) -> dict:
    entries = [
        {
            "path": _archive_name(run_dir, path),
            "size": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in files
    ]
    return {
        "schema_version": BUNDLE_MANIFEST_SCHEMA,
        "digest_algorithm": "sha256",
        "bundle_root": run_dir.name,
        "run_id": _read_run_id(run_dir) or run_dir.name,
        "file_count": len(entries),
        "files": entries,
    }


def write_zip_bundle(run_dir: Path, output_path: Path | None = None) -> Path:
    output_path = output_path or run_dir.with_suffix(".zip")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(path for path in run_dir.rglob("*") if path.is_file())
    manifest = build_bundle_manifest(run_dir, files)
    manifest_name = f"{run_dir.name}/{BUNDLE_MANIFEST_NAME}"
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, _archive_name(run_dir, path))
        archive.writestr(manifest_name, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return output_path


def find_bundle_manifest_member(names: list[str]) -> str | None:
    for name in names:
        if name == BUNDLE_MANIFEST_NAME or name.endswith(f"/{BUNDLE_MANIFEST_NAME}"):
            return name
    return None


def validate_bundle_manifest(archive: ZipFile) -> tuple[str | None, dict, list[str]]:
    names = archive.namelist()
    non_directory_names = [name for name in names if not name.endswith("/")]
    manifest_member = find_bundle_manifest_member(non_directory_names)
    if manifest_member is None:
        return None, {}, [f"Missing {BUNDLE_MANIFEST_NAME} in bundle."]

    errors = []
    duplicate_members = sorted({name for name in non_directory_names if non_directory_names.count(name) > 1})
    if duplicate_members:
        errors.append(f"Duplicate bundle members: {', '.join(duplicate_members)}")

    try:
        manifest = json.loads(archive.read(manifest_member).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return manifest_member, {}, [f"Invalid JSON in {manifest_member}"]
    if not isinstance(manifest, dict):
        return manifest_member, {}, [f"Bundle manifest payload is not a JSON object: {manifest_member}"]
    if manifest.get("schema_version") != BUNDLE_MANIFEST_SCHEMA:
        errors.append(f"Unexpected bundle manifest schema: {manifest.get('schema_version')}")
    if manifest.get("digest_algorithm") != "sha256":
        errors.append(f"Unexpected bundle digest algorithm: {manifest.get('digest_algorithm')}")

    files = manifest.get("files")
    if not isinstance(files, list):
        errors.append("Bundle manifest files field is not a list.")
        return manifest_member, manifest, errors

    expected_members = set(non_directory_names) - {manifest_member}
    listed_members = set()
    member_names = set(non_directory_names)
    for item in files:
        if not isinstance(item, dict):
            errors.append("Bundle manifest contains a non-object file entry.")
            continue
        member = item.get("path")
        if not isinstance(member, str) or not member.strip():
            errors.append("Bundle manifest contains a file entry without a path.")
            continue
        if not _is_safe_member_path(member):
            errors.append(f"Unsafe bundle member path in manifest: {member}")
            continue
        listed_members.add(member)
        if member not in member_names:
            errors.append(f"Missing bundle member listed in manifest: {member}")
            continue

        data = archive.read(member)
        expected_size = item.get("size")
        if not isinstance(expected_size, int) or expected_size < 0:
            errors.append(f"Invalid size for bundle member: {member}")
        elif len(data) != expected_size:
            errors.append(f"Size mismatch for bundle member: {member}")

        expected_sha = item.get("sha256")
        if not isinstance(expected_sha, str) or not expected_sha:
            errors.append(f"Missing sha256 for bundle member: {member}")
        elif hashlib.sha256(data).hexdigest() != expected_sha:
            errors.append(f"Checksum mismatch for bundle member: {member}")

    missing_from_manifest = sorted(expected_members - listed_members)
    extra_in_manifest = sorted(listed_members - expected_members)
    if missing_from_manifest:
        errors.append(f"Bundle members missing from manifest: {', '.join(missing_from_manifest)}")
    if extra_in_manifest:
        errors.append(f"Manifest entries not present in bundle: {', '.join(extra_in_manifest)}")
    if manifest.get("file_count") != len(files):
        errors.append("Bundle manifest file_count does not match files length.")

    return manifest_member, manifest, errors


def _read_run_id(run_dir: Path) -> str | None:
    report_path = run_dir / "agentledger-report.json"
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    run_id = payload.get("run_id")
    return str(run_id) if isinstance(run_id, str) and run_id.strip() else None


def _is_safe_member_path(member: str) -> bool:
    path = Path(member)
    return ":" not in member and not path.is_absolute() and ".." not in path.parts
