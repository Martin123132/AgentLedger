from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_github_release
import release_check_summary
import release_notes


SCHEMA_VERSION = "agentledger.release_evidence_packet.v1"
FORBIDDEN_SUFFIXES = {".zip"}
FORBIDDEN_NAMES = {".agentledger", ".agentledger-signing-key"}
FORBIDDEN_NAME_FRAGMENTS = {"signing-key"}


class ReleaseEvidencePacketError(ValueError):
    pass


def _as_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseEvidencePacketError(f"{field} must be an object.")
    return value


def _as_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReleaseEvidencePacketError(f"{field} must be a list.")
    return value


def _read_json(path: Path, label: str) -> dict[str, Any]:
    _ensure_public_safe_path(path, label)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ReleaseEvidencePacketError(f"Invalid JSON in {path}: {error}") from error
    return _as_mapping(payload, label)


def _read_text(path: Path, label: str) -> str:
    _ensure_public_safe_path(path, label)
    return path.read_text(encoding="utf-8-sig")


def _ensure_public_safe_path(path: Path, label: str) -> None:
    lower_parts = {part.lower() for part in path.parts}
    lower_name = path.name.lower()
    if lower_parts & FORBIDDEN_NAMES:
        raise ReleaseEvidencePacketError(
            f"{label} must not point inside .agentledger or use a signing-key path: {path}"
        )
    if path.suffix.lower() in FORBIDDEN_SUFFIXES:
        raise ReleaseEvidencePacketError(f"{label} must not be a zip bundle: {path}")
    if any(fragment in lower_name for fragment in FORBIDDEN_NAME_FRAGMENTS):
        raise ReleaseEvidencePacketError(f"{label} must not be a signing-key path: {path}")


def _normalize_text(text: str) -> str:
    return text.replace("\r\n", "\n").strip()


def _version_matches(value: Any, expected: str, field: str) -> None:
    if str(value or "").strip() != expected:
        raise ReleaseEvidencePacketError(f"{field} must be {expected!r}.")


def _count_status(items: list[Any]) -> tuple[int, int]:
    passed = 0
    failed = 0
    for item in items:
        if isinstance(item, dict):
            if item.get("status") == "passed":
                passed += 1
            elif item.get("status") == "failed":
                failed += 1
    return passed, failed


def _artifact_entry(kind: str, path: Path) -> dict[str, str]:
    return {
        "kind": kind,
        "file": path.name,
        "packet_content": "validated summary only",
    }


def validate_release_check_inputs(
    *,
    version: str,
    release_check_payload: dict[str, Any],
    release_check_summary_text: str,
) -> None:
    release_check_summary.validate_release_check(release_check_payload)
    if release_check_payload.get("ok") is not True:
        raise ReleaseEvidencePacketError("release-check JSON must have ok=true.")
    if release_check_payload.get("status") != "ready":
        raise ReleaseEvidencePacketError("release-check JSON must have status=ready.")
    if release_check_payload.get("working_tree_dirty"):
        raise ReleaseEvidencePacketError("release-check JSON must come from a clean working tree.")
    if release_check_payload.get("require_clean_git") is not True:
        raise ReleaseEvidencePacketError("release-check JSON must be generated with require_clean_git=true.")

    _version_matches(release_check_payload.get("package_version"), version, "package_version")
    _version_matches(release_check_payload.get("agentledger_version"), version, "agentledger_version")

    expected_summary = release_check_summary.render_release_check_markdown(release_check_payload)
    if _normalize_text(release_check_summary_text) != _normalize_text(expected_summary):
        raise ReleaseEvidencePacketError("release-check Markdown summary does not match the JSON input.")


def validate_github_release_check(
    *,
    version: str,
    github_release_check_payload: dict[str, Any],
) -> None:
    if github_release_check_payload.get("schema_version") != check_github_release.SCHEMA_VERSION:
        raise ReleaseEvidencePacketError(
            "GitHub release check schema_version must be "
            f"{check_github_release.SCHEMA_VERSION}."
        )
    if github_release_check_payload.get("ok") is not True:
        raise ReleaseEvidencePacketError("GitHub release check must have ok=true.")
    if github_release_check_payload.get("status") != "ready":
        raise ReleaseEvidencePacketError("GitHub release check must have status=ready.")

    normalized = release_notes.normalize_version(version)
    expected_tag = check_github_release.release_tag(version)
    _version_matches(github_release_check_payload.get("version"), version, "GitHub release check version")
    _version_matches(
        github_release_check_payload.get("release_label"),
        normalized,
        "GitHub release check release_label",
    )
    _version_matches(github_release_check_payload.get("tag"), expected_tag, "GitHub release check tag")

    release = _as_mapping(github_release_check_payload.get("release"), "GitHub release check release")
    if not str(release.get("url") or "").startswith(
        f"https://github.com/{github_release_check_payload.get('repository')}/releases/"
    ):
        raise ReleaseEvidencePacketError("GitHub release check must include a GitHub release URL.")

    checks = _as_list(github_release_check_payload.get("checks"), "GitHub release check checks")
    failed_checks = [check for check in checks if isinstance(check, dict) and check.get("status") == "failed"]
    if failed_checks:
        raise ReleaseEvidencePacketError("GitHub release check still contains failed checks.")

    errors = _as_list(github_release_check_payload.get("errors"), "GitHub release check errors")
    if errors:
        raise ReleaseEvidencePacketError("GitHub release check errors must be empty.")


def build_release_evidence_packet(
    *,
    version: str,
    release_check_json: Path,
    release_check_summary_file: Path,
    release_notes_file: Path,
    github_release_check_json: Path,
) -> dict[str, Any]:
    normalized = release_notes.normalize_version(version)
    release_check_payload = _read_json(release_check_json, "release-check JSON")
    release_check_summary_text = _read_text(release_check_summary_file, "release-check Markdown summary")
    release_notes_text = _read_text(release_notes_file, "release notes")
    github_release_check_payload = _read_json(github_release_check_json, "GitHub release check JSON")

    validate_release_check_inputs(
        version=version,
        release_check_payload=release_check_payload,
        release_check_summary_text=release_check_summary_text,
    )
    release_notes.validate_publish_ready(version=version, notes_text=release_notes_text)
    validate_github_release_check(
        version=version,
        github_release_check_payload=github_release_check_payload,
    )

    metadata = _as_mapping(release_check_payload.get("release_metadata"), "release metadata")
    release_steps = _as_list(release_check_payload.get("steps"), "release-check steps")
    github_checks = _as_list(github_release_check_payload.get("checks"), "GitHub release check checks")
    release = _as_mapping(github_release_check_payload.get("release"), "GitHub release")
    steps_passed, steps_failed = _count_status(release_steps)
    metadata_passed, metadata_failed = release_check_summary.release_metadata_counts(metadata)
    github_passed, github_failed = _count_status(github_checks)

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": True,
        "status": "ready",
        "version": version,
        "release_label": normalized,
        "tag": check_github_release.release_tag(version),
        "repository": github_release_check_payload.get("repository"),
        "release_url": release.get("url"),
        "private_evidence_included": False,
        "release_check": {
            "status": release_check_payload.get("status"),
            "branch": release_check_payload.get("branch"),
            "head": release_check_payload.get("head"),
            "package_version": release_check_payload.get("package_version"),
            "working_tree_dirty": bool(release_check_payload.get("working_tree_dirty")),
            "require_clean_git": bool(release_check_payload.get("require_clean_git")),
            "steps_passed": steps_passed,
            "steps_failed": steps_failed,
            "metadata_checks_passed": metadata_passed,
            "metadata_checks_failed": metadata_failed,
            "metadata_license": metadata.get("license"),
        },
        "github_release_check": {
            "status": github_release_check_payload.get("status"),
            "checks_passed": github_passed,
            "checks_failed": github_failed,
            "is_prerelease": release.get("is_prerelease"),
            "is_draft": release.get("is_draft"),
            "published_at": release.get("published_at"),
        },
        "artifacts": [
            _artifact_entry("release-check-json", release_check_json),
            _artifact_entry("release-check-summary", release_check_summary_file),
            _artifact_entry("release-notes", release_notes_file),
            _artifact_entry("github-release-check-json", github_release_check_json),
        ],
        "handling": {
            "store_outside_repo": True,
            "do_not_commit": [".agentledger/", "*.zip", ".agentledger-signing-key", "signing keys"],
            "release_notes_body_included": False,
        },
    }


def render_release_evidence_packet_markdown(packet: dict[str, Any]) -> str:
    release_check = _as_mapping(packet.get("release_check"), "release_check")
    github_release_check = _as_mapping(packet.get("github_release_check"), "github_release_check")
    artifacts = _as_list(packet.get("artifacts"), "artifacts")

    lines = [
        "# AgentLedger Release Evidence Packet",
        "",
        f"- Result: {packet.get('status')}",
        f"- Version: {packet.get('version')}",
        f"- Release label: {packet.get('release_label')}",
        f"- Tag: {packet.get('tag')}",
        f"- Repository: {packet.get('repository')}",
        f"- Release URL: {packet.get('release_url')}",
        "- Private evidence included: no",
        "",
        "## Release Readiness",
        "",
        f"- Status: {release_check.get('status')}",
        f"- Branch: {release_check.get('branch')}",
        f"- HEAD: {release_check.get('head')}",
        f"- Working tree dirty: {str(bool(release_check.get('working_tree_dirty'))).lower()}",
        f"- Require clean git: {str(bool(release_check.get('require_clean_git'))).lower()}",
        f"- Steps: {release_check.get('steps_passed')} passed, {release_check.get('steps_failed')} failed",
        (
            "- Release metadata checks: "
            f"{release_check.get('metadata_checks_passed')} passed, "
            f"{release_check.get('metadata_checks_failed')} failed"
        ),
        f"- License: {release_check.get('metadata_license')}",
        "",
        "## GitHub Release",
        "",
        f"- Status: {github_release_check.get('status')}",
        f"- Prerelease: {github_release_check.get('is_prerelease')}",
        f"- Draft: {github_release_check.get('is_draft')}",
        f"- Published: {github_release_check.get('published_at')}",
        f"- Checks: {github_release_check.get('checks_passed')} passed, {github_release_check.get('checks_failed')} failed",
        "",
        "## Artifact Inputs",
        "",
        "| Artifact | File | Packet content |",
        "| --- | --- | --- |",
    ]
    for artifact in artifacts:
        artifact_payload = _as_mapping(artifact, "artifact")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(artifact_payload.get("kind") or "n/a"),
                    str(artifact_payload.get("file") or "n/a"),
                    str(artifact_payload.get("packet_content") or "n/a"),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Handling Notes",
            "",
            "- Keep this packet and its source release artifacts outside the repo unless they have been reviewed.",
            "- Do not commit `.agentledger/` evidence folders, zip bundles, or signing keys.",
            "- The packet records validation status and artifact names only; it does not bundle release notes bodies or private evidence.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a public-safe release evidence packet from validated release artifacts."
    )
    parser.add_argument("--version", required=True, help="Package version, for example 0.1.8a0.")
    parser.add_argument("--release-check-json", type=Path, required=True)
    parser.add_argument("--release-check-summary", type=Path, required=True)
    parser.add_argument("--release-notes", type=Path, required=True)
    parser.add_argument("--github-release-check-json", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Write Markdown packet to this path.")
    parser.add_argument("--json-output", type=Path, help="Write JSON packet to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.output:
            _ensure_public_safe_path(args.output, "Markdown output")
        if args.json_output:
            _ensure_public_safe_path(args.json_output, "JSON output")
        packet = build_release_evidence_packet(
            version=args.version,
            release_check_json=args.release_check_json,
            release_check_summary_file=args.release_check_summary,
            release_notes_file=args.release_notes,
            github_release_check_json=args.github_release_check_json,
        )
        markdown = render_release_evidence_packet_markdown(packet)
    except (
        OSError,
        release_notes.ReleaseNotesError,
        release_check_summary.ReleaseCheckSummaryError,
        ReleaseEvidencePacketError,
    ) as error:
        print(f"release_evidence_packet.py: {error}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")

    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")

    if args.output or args.json_output:
        destinations = [str(path) for path in [args.output, args.json_output] if path]
        print(f"Release evidence packet written: {', '.join(destinations)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
