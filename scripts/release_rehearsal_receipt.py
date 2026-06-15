from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_artifact_doctor
import verify_release_rehearsal


SCHEMA_VERSION = "agentledger.release_rehearsal_receipt.v1"
KEY_ARTIFACT_KINDS = (
    "draft-release-notes",
    "release-command-index-markdown",
    "release-rehearsal-summary-markdown",
    "release-metadata-json",
    "release-readiness-markdown",
    "release-check-json",
    "release-check-summary",
)


class ReleaseRehearsalReceiptError(ValueError):
    pass


def _as_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseRehearsalReceiptError(f"{field} must be an object.")
    return value


def _quote_powershell_arg(value: str) -> str:
    if value and not any(char.isspace() for char in value) and "'" not in value:
        return value
    return "'" + value.replace("'", "''") + "'"


def _artifact_path(output_dir: Path, relative: str) -> Path:
    relative_path = PurePosixPath(relative)
    return output_dir.joinpath(*relative_path.parts)


def _key_artifacts(manifest: dict[str, Any] | None, output_dir: Path) -> list[dict[str, Any]]:
    if not manifest:
        return []
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        return []

    keys: list[dict[str, Any]] = []
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        kind = artifact.get("kind")
        relative = artifact.get("file")
        if kind not in KEY_ARTIFACT_KINDS or not isinstance(relative, str):
            continue
        path = _artifact_path(output_dir, relative)
        keys.append(
            {
                "kind": kind,
                "file": relative,
                "path": str(path),
                "bytes": artifact.get("bytes"),
                "sha256": artifact.get("sha256"),
            }
        )
    return keys


def _find_artifact_path(
    key_artifacts: list[dict[str, Any]],
    *,
    kind: str,
    fallback: Path,
) -> Path:
    for artifact in key_artifacts:
        if artifact.get("kind") == kind and artifact.get("path"):
            return Path(str(artifact["path"]))
    return fallback


def _next_prepare_commands(
    *,
    package_version: str | None,
    release_date: str | None,
    release_label: str | None,
    output_dir: Path,
    key_artifacts: list[dict[str, Any]],
) -> list[str]:
    if not package_version or not release_date or not release_label:
        return []
    draft_notes = _find_artifact_path(
        key_artifacts,
        kind="draft-release-notes",
        fallback=output_dir / f"agentledger-{release_label}-release.md",
    )
    notes_arg = _quote_powershell_arg(str(draft_notes))
    base = (
        f"python scripts/prepare_release.py --version {package_version} "
        f"--date {release_date} --release-notes-output {notes_arg}"
    )
    return [f"{base} --dry-run", base]


def build_release_rehearsal_receipt(
    manifest_path: Path,
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    manifest_file = manifest_path.resolve()
    output_root = (output_dir or manifest_file.parent).resolve()
    manifest: dict[str, Any] | None = None
    manifest_error: str | None = None

    try:
        manifest = verify_release_rehearsal.load_manifest(manifest_file)
    except (OSError, verify_release_rehearsal.ReleaseRehearsalVerifyError) as error:
        manifest_error = str(error)

    verification = verify_release_rehearsal.verify_release_rehearsal_manifest(
        manifest_file,
        output_dir=output_root,
    )
    package_version = verification.get("package_version")
    doctor: dict[str, Any] | None = None
    doctor_error: str | None = None

    if package_version:
        try:
            doctor = release_artifact_doctor.check_release_artifacts(
                version=str(package_version),
                stage="rehearsal",
                rehearsal_manifest=manifest_file,
                rehearsal_output_dir=output_root,
            )
        except (
            OSError,
            release_artifact_doctor.ReleaseArtifactDoctorError,
        ) as error:
            doctor_error = str(error)
    else:
        doctor_error = "release rehearsal manifest did not provide package_version."

    key_artifacts = _key_artifacts(manifest, output_root)
    release_label = verification.get("release_version")
    release_date = verification.get("release_date")
    next_commands = _next_prepare_commands(
        package_version=str(package_version) if package_version else None,
        release_date=str(release_date) if release_date else None,
        release_label=str(release_label) if release_label else None,
        output_dir=output_root,
        key_artifacts=key_artifacts,
    )

    ok = bool(verification["ok"]) and bool(doctor and doctor["ok"])
    next_actions: list[str] = []
    if manifest_error:
        next_actions.append("Regenerate the release rehearsal manifest.")
    if doctor:
        next_actions.extend(str(action) for action in doctor.get("next_actions", []))
    elif doctor_error:
        next_actions.append(doctor_error)
    if not verification["ok"]:
        next_actions.append("Rerun `scripts/rehearse_release.py`, then verify the new manifest.")
    if ok and next_commands:
        next_actions.append("Run the dry-run prepare command first, review the draft notes, then run the write command.")

    handling = _as_mapping(manifest.get("handling", {}), "manifest handling") if manifest else {}

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "status": "ready" if ok else "blocked",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest_json": str(manifest_file),
        "output_dir": str(output_root),
        "package_version": package_version,
        "release_version": release_label,
        "release_date": release_date,
        "branch": verification.get("branch"),
        "head": verification.get("head"),
        "artifact_count": verification.get("artifact_count"),
        "verified_artifacts": verification.get("verified_artifacts"),
        "key_artifacts": key_artifacts,
        "verification": verification,
        "doctor": doctor,
        "errors": [error for error in [manifest_error, doctor_error] if error]
        + [str(error) for error in verification.get("errors", [])],
        "next_commands": next_commands if ok else [],
        "next_actions": list(dict.fromkeys(next_actions)),
        "handling": {
            "do_not_commit": handling.get("do_not_commit", []),
            "store_outside_repo": handling.get("store_outside_repo"),
        },
    }


def format_text(result: dict[str, Any]) -> str:
    outcome = "READY" if result["ok"] else "BLOCKED"
    doctor = result.get("doctor") or {}
    verification = result.get("verification") or {}
    lines = [
        (
            "Release rehearsal receipt "
            f"{outcome}: {result.get('package_version') or 'unknown'} -> "
            f"{result.get('release_version') or 'unknown'}"
        ),
        f"Manifest: {result['manifest_json']}",
        f"Output directory: {result['output_dir']}",
        f"Release date: {result.get('release_date') or 'n/a'}",
        f"Branch: {result.get('branch') or 'n/a'}",
        f"HEAD: {result.get('head') or 'n/a'}",
        f"Artifacts: {result['verified_artifacts']} verified of {result['artifact_count']}",
        f"Verification: {verification.get('status') or 'n/a'}",
        f"Doctor: {doctor.get('status') or 'n/a'}",
    ]
    if result["key_artifacts"]:
        lines.append("Key artifacts:")
        for artifact in result["key_artifacts"]:
            lines.append(f"- {artifact['kind']}: {artifact['path']}")
    if result["next_commands"]:
        lines.append("Next commands:")
        for command in result["next_commands"]:
            lines.append(f"- {command}")
    if result["errors"]:
        lines.append("Errors:")
        for error in result["errors"]:
            lines.append(f"- {error}")
    if result["next_actions"]:
        lines.append("Next actions:")
        for action in result["next_actions"]:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def _escape_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("|", "\\|")
    text = " ".join(text.splitlines())
    return text or "n/a"


def format_markdown(result: dict[str, Any]) -> str:
    outcome = "ready" if result["ok"] else "blocked"
    doctor = result.get("doctor") or {}
    verification = result.get("verification") or {}
    lines = [
        "# AgentLedger Release Rehearsal Receipt",
        "",
        f"- Result: {outcome}",
        f"- Package version: {result.get('package_version') or 'n/a'}",
        f"- Release label: {result.get('release_version') or 'n/a'}",
        f"- Release date: {result.get('release_date') or 'n/a'}",
        f"- Manifest: `{result['manifest_json']}`",
        f"- Output directory: `{result['output_dir']}`",
        f"- Branch: {result.get('branch') or 'n/a'}",
        f"- HEAD: {result.get('head') or 'n/a'}",
        f"- Artifacts: {result['verified_artifacts']} verified of {result['artifact_count']}",
        f"- Verification: {verification.get('status') or 'n/a'}",
        f"- Doctor: {doctor.get('status') or 'n/a'}",
    ]
    if result["key_artifacts"]:
        lines.extend(["", "## Key Artifacts", "", "| Kind | File | Bytes |", "| --- | --- | --- |"])
        for artifact in result["key_artifacts"]:
            lines.append(
                "| "
                + " | ".join(
                    [
                        _escape_cell(artifact.get("kind")),
                        _escape_cell(artifact.get("file")),
                        _escape_cell(artifact.get("bytes")),
                    ]
                )
                + " |"
            )
    if result["next_commands"]:
        lines.extend(["", "## Next Commands", "", "```powershell"])
        lines.extend(result["next_commands"])
        lines.append("```")
    if result["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in result["errors"]:
            lines.append(f"- {error}")
    if result["next_actions"]:
        lines.extend(["", "## Next Actions", ""])
        for action in result["next_actions"]:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize a verified AgentLedger release rehearsal and the next prepare-release commands."
    )
    parser.add_argument("manifest", type=Path, help="Path to release-rehearsal-manifest.json.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory containing the manifest artifacts. Defaults to the manifest's parent directory.",
    )
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", type=Path, help="Write formatted receipt to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = build_release_rehearsal_receipt(
            args.manifest,
            output_dir=args.output_dir,
        )
    except (OSError, ReleaseRehearsalReceiptError) as error:
        print(f"release_rehearsal_receipt.py: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        rendered = json.dumps(result, indent=2) + "\n"
    elif args.format == "markdown":
        rendered = format_markdown(result)
    else:
        rendered = format_text(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Release rehearsal receipt written: {args.output}")
    else:
        print(rendered, end="")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
