from __future__ import annotations

import hashlib
import hmac
import json
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


BUNDLE_MANIFEST_NAME = "agentledger-bundle-manifest.json"
BUNDLE_MANIFEST_SCHEMA = "agentledger.bundle.v1"
BUNDLE_SIGNATURE_NAME = "agentledger-bundle-signature.json"
BUNDLE_SIGNATURE_SCHEMA = "agentledger.bundle.signature.v1"


class BundleError(Exception):
    pass


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


def sign_zip_bundle(bundle_path: Path, key: bytes, output_path: Path | None = None) -> tuple[Path, str, dict]:
    if not key:
        raise BundleError("Signature key is empty.")
    bundle_path = bundle_path.resolve()
    output_path = (output_path or bundle_path).resolve()
    if not bundle_path.exists():
        raise BundleError(f"Bundle not found: {bundle_path}")

    with ZipFile(bundle_path, "r") as source:
        manifest_member, _manifest, errors = validate_bundle_manifest(source)
        if errors:
            raise BundleError(f"Cannot sign invalid bundle: {'; '.join(errors)}")
        if manifest_member is None:
            raise BundleError(f"Cannot sign bundle without {BUNDLE_MANIFEST_NAME}.")
        signature_member = _sibling_member_name(manifest_member, BUNDLE_SIGNATURE_NAME)
        signature_members_to_replace = set(find_bundle_signature_members(source.namelist()))
        signature_members_to_replace.add(signature_member)
        signature = build_bundle_signature(source, manifest_member, key)
        entries = [
            (item, source.read(item.filename))
            for item in source.infolist()
            if not item.is_dir() and item.filename not in signature_members_to_replace
        ]

    write_path = output_path
    temp_path: Path | None = None
    if output_path == bundle_path:
        handle = tempfile.NamedTemporaryFile(
            delete=False,
            dir=str(output_path.parent),
            prefix=f"{output_path.stem}-",
            suffix=".tmp",
        )
        handle.close()
        temp_path = Path(handle.name)
        write_path = temp_path

    try:
        with ZipFile(write_path, "w", compression=ZIP_DEFLATED) as destination:
            for info, data in entries:
                destination.writestr(info, data)
            destination.writestr(signature_member, json.dumps(signature, indent=2, sort_keys=True) + "\n")
        if temp_path is not None:
            temp_path.replace(output_path)
    except Exception:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise
    return output_path, signature_member, signature


def build_bundle_signature(archive: ZipFile, manifest_member: str, key: bytes) -> dict:
    manifest_bytes = archive.read(manifest_member)
    return {
        "schema_version": BUNDLE_SIGNATURE_SCHEMA,
        "algorithm": "hmac-sha256",
        "signed_member": manifest_member,
        "signed_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "signature": hmac.new(key, manifest_bytes, hashlib.sha256).hexdigest(),
    }


def find_bundle_manifest_member(names: list[str]) -> str | None:
    for name in names:
        if name == BUNDLE_MANIFEST_NAME or name.endswith(f"/{BUNDLE_MANIFEST_NAME}"):
            return name
    return None


def find_bundle_signature_members(names: list[str]) -> list[str]:
    return [
        name
        for name in names
        if name == BUNDLE_SIGNATURE_NAME or name.endswith(f"/{BUNDLE_SIGNATURE_NAME}")
    ]


def find_bundle_signature_member(names: list[str]) -> str | None:
    matches = find_bundle_signature_members(names)
    return matches[0] if matches else None


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

    signature_members = set(find_bundle_signature_members(non_directory_names))
    expected_members = set(non_directory_names) - {manifest_member} - signature_members
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


def validate_bundle_signature(archive: ZipFile, key: bytes) -> tuple[str | None, dict, list[str]]:
    names = [name for name in archive.namelist() if not name.endswith("/")]
    signature_members = find_bundle_signature_members(names)
    if not signature_members:
        return None, {}, [f"Missing {BUNDLE_SIGNATURE_NAME} in bundle."]
    if len(signature_members) > 1:
        return None, {}, [f"Multiple bundle signature files found: {', '.join(sorted(signature_members))}"]

    signature_member = signature_members[0]
    try:
        signature = json.loads(archive.read(signature_member).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return signature_member, {}, [f"Invalid JSON in {signature_member}"]
    if not isinstance(signature, dict):
        return signature_member, {}, [f"Bundle signature payload is not a JSON object: {signature_member}"]

    errors = []
    if signature.get("schema_version") != BUNDLE_SIGNATURE_SCHEMA:
        errors.append(f"Unexpected bundle signature schema: {signature.get('schema_version')}")
    if signature.get("algorithm") != "hmac-sha256":
        errors.append(f"Unexpected bundle signature algorithm: {signature.get('algorithm')}")

    signed_member = signature.get("signed_member")
    if not isinstance(signed_member, str) or not signed_member.strip():
        errors.append("Bundle signature is missing signed_member.")
        return signature_member, signature, errors
    if not _is_safe_member_path(signed_member):
        errors.append(f"Unsafe signed member path in bundle signature: {signed_member}")
        return signature_member, signature, errors
    if signed_member not in names:
        errors.append(f"Signed bundle member not found: {signed_member}")
        return signature_member, signature, errors

    manifest_member = find_bundle_manifest_member(names)
    if manifest_member is not None and signed_member != manifest_member:
        errors.append(f"Bundle signature signs {signed_member}, expected {manifest_member}.")

    manifest_bytes = archive.read(signed_member)
    expected_sha = hashlib.sha256(manifest_bytes).hexdigest()
    if signature.get("signed_sha256") != expected_sha:
        errors.append(f"Signed manifest digest mismatch for {signed_member}.")

    expected_signature = hmac.new(key, manifest_bytes, hashlib.sha256).hexdigest()
    actual_signature = signature.get("signature")
    if not isinstance(actual_signature, str) or not hmac.compare_digest(actual_signature, expected_signature):
        errors.append(f"Signature mismatch for {signed_member}.")

    return signature_member, signature, errors


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


def _sibling_member_name(member: str, filename: str) -> str:
    if "/" not in member:
        return filename
    return f"{member.rsplit('/', 1)[0]}/{filename}"
