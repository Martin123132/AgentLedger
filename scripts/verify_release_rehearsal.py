from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import rehearse_release


SCHEMA_VERSION = "agentledger.release_rehearsal_manifest_verify.v1"


class ReleaseRehearsalVerifyError(ValueError):
    pass


def _as_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseRehearsalVerifyError(f"{field} must be an object.")
    return value


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ReleaseRehearsalVerifyError(f"Invalid JSON in {path}: {error}") from error
    return _as_mapping(payload, "release rehearsal manifest")


def verify_release_rehearsal_manifest(
    manifest_path: Path,
    *,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    manifest_file = manifest_path.resolve()
    output_root = (output_dir or manifest_file.parent).resolve()
    errors: list[str] = []
    manifest: dict[str, Any] | None = None

    try:
        manifest = load_manifest(manifest_file)
        rehearse_release.validate_release_rehearsal_manifest(manifest, output_root)
    except (OSError, rehearse_release.ReleaseRehearsalError, ReleaseRehearsalVerifyError) as error:
        errors.append(str(error))

    artifacts = manifest.get("artifacts", []) if isinstance(manifest, dict) else []
    artifact_count = len(artifacts) if isinstance(artifacts, list) else 0
    ok = not errors
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "status": "ready" if ok else "failed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "manifest_json": str(manifest_file),
        "output_dir": str(output_root),
        "manifest_schema_version": manifest.get("schema_version") if manifest else None,
        "package_version": manifest.get("package_version") if manifest else None,
        "release_version": manifest.get("release_version") if manifest else None,
        "release_date": manifest.get("release_date") if manifest else None,
        "branch": manifest.get("branch") if manifest else None,
        "head": manifest.get("head") if manifest else None,
        "artifact_count": artifact_count,
        "verified_artifacts": artifact_count if ok else 0,
        "errors": errors,
    }


def format_text(result: dict[str, Any]) -> str:
    status = "OK" if result["ok"] else "FAILED"
    lines = [
        f"Release rehearsal manifest {status}: {result['manifest_json']}",
        f"Output directory: {result['output_dir']}",
        f"Release: {result.get('package_version') or 'unknown'} -> {result.get('release_version') or 'unknown'}",
        f"Artifacts: {result['verified_artifacts']} verified of {result['artifact_count']}",
    ]
    for error in result["errors"]:
        lines.append(f"- ERROR: {error}")
    return "\n".join(lines).rstrip() + "\n"


def format_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# AgentLedger Release Rehearsal Manifest Verification",
        "",
        f"- Result: {result['status']}",
        f"- Manifest: `{result['manifest_json']}`",
        f"- Output directory: `{result['output_dir']}`",
        f"- Package version: {result.get('package_version') or 'n/a'}",
        f"- Release label: {result.get('release_version') or 'n/a'}",
        f"- Release date: {result.get('release_date') or 'n/a'}",
        f"- Branch: {result.get('branch') or 'n/a'}",
        f"- HEAD: {result.get('head') or 'n/a'}",
        f"- Artifacts: {result['verified_artifacts']} verified of {result['artifact_count']}",
    ]
    if result["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in result["errors"]:
            lines.append(f"- {error}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a saved AgentLedger release rehearsal manifest and generated output folder."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to release-rehearsal-manifest.json.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory containing the manifest artifacts. Defaults to the manifest's parent directory.",
    )
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", type=Path, help="Write formatted verification result to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    result = verify_release_rehearsal_manifest(
        args.manifest,
        output_dir=args.output_dir,
    )

    if args.format == "json":
        rendered = json.dumps(result, indent=2) + "\n"
    elif args.format == "markdown":
        rendered = format_markdown(result)
    else:
        rendered = format_text(result)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Release rehearsal manifest verification written: {args.output}")
    else:
        print(rendered, end="")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
