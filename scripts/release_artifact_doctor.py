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
import finalize_release_notes
import release_check_summary
import release_evidence_packet
import release_notes
import verify_release_rehearsal


ROOT = SCRIPT_DIR.parent
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"
SCHEMA_VERSION = "agentledger.release_artifact_doctor.v1"
STAGES = ("rehearsal", "final-notes", "post-release", "evidence-packet")


class ReleaseArtifactDoctorError(ValueError):
    pass


def _as_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseArtifactDoctorError(f"{field} must be an object.")
    return value


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ReleaseArtifactDoctorError(f"Invalid JSON: {error}") from error
    return _as_mapping(payload, "JSON payload")


def _add_check(
    checks: list[dict[str, Any]],
    *,
    name: str,
    path: Path | None = None,
    status: str,
    detail: str,
    next_action: str | None = None,
) -> None:
    check: dict[str, Any] = {
        "name": name,
        "status": status,
        "detail": detail,
    }
    if path is not None:
        check["path"] = str(path)
        check["file"] = path.name
    if next_action:
        check["next_action"] = next_action
    checks.append(check)


def _require_path(
    checks: list[dict[str, Any]],
    *,
    name: str,
    path: Path | None,
    next_action: str,
) -> Path | None:
    if path is None:
        _add_check(
            checks,
            name=name,
            status="failed",
            detail="Path was not provided.",
            next_action=next_action,
        )
        return None

    try:
        release_evidence_packet._ensure_public_safe_path(path, name)
    except release_evidence_packet.ReleaseEvidencePacketError as error:
        _add_check(
            checks,
            name=name,
            path=path,
            status="failed",
            detail=str(error),
            next_action="Use a reviewed temp release artifact outside `.agentledger/`, zip bundles, and signing-key paths.",
        )
        return None

    if not path.exists():
        _add_check(
            checks,
            name=name,
            path=path,
            status="failed",
            detail="File does not exist.",
            next_action=next_action,
        )
        return None
    if not path.is_file():
        _add_check(
            checks,
            name=name,
            path=path,
            status="failed",
            detail="Path is not a file.",
            next_action=next_action,
        )
        return None
    _add_check(
        checks,
        name=name,
        path=path,
        status="passed",
        detail="File exists.",
    )
    return path


def _safe_validate(
    checks: list[dict[str, Any]],
    *,
    name: str,
    path: Path | None = None,
    action,
    next_action: str,
) -> Any:
    try:
        value = action()
    except (
        OSError,
        ReleaseArtifactDoctorError,
        release_notes.ReleaseNotesError,
        release_check_summary.ReleaseCheckSummaryError,
        release_evidence_packet.ReleaseEvidencePacketError,
        finalize_release_notes.FinalizeReleaseNotesError,
        check_github_release.GitHubReleaseCheckError,
        verify_release_rehearsal.ReleaseRehearsalVerifyError,
    ) as error:
        _add_check(
            checks,
            name=name,
            path=path,
            status="failed",
            detail=str(error),
            next_action=next_action,
        )
        return None
    _add_check(checks, name=name, path=path, status="passed", detail="OK.")
    return value


def _validate_release_check_for_final_notes(
    *,
    version: str,
    release_check_json: Path,
    release_check_summary_file: Path,
) -> tuple[int, int]:
    payload = release_check_summary.load_release_check(release_check_json)
    summary_text = release_check_summary_file.read_text(encoding="utf-8-sig")
    return finalize_release_notes.validate_release_check_for_publish(
        payload=payload,
        version=version,
        summary_text=summary_text,
    )


def _validate_release_check_for_packet(
    *,
    version: str,
    release_check_json: Path,
    release_check_summary_file: Path,
) -> None:
    payload = release_check_summary.load_release_check(release_check_json)
    summary_text = release_check_summary_file.read_text(encoding="utf-8-sig")
    release_evidence_packet.validate_release_check_inputs(
        version=version,
        release_check_payload=payload,
        release_check_summary_text=summary_text,
    )


def _validate_changelog(*, version: str, changelog: Path) -> None:
    changelog_text = changelog.read_text(encoding="utf-8-sig")
    release_notes.extract_changelog_section(changelog_text, version)


def _validate_release_notes(*, version: str, release_notes_file: Path) -> None:
    notes_text = release_notes_file.read_text(encoding="utf-8-sig")
    release_notes.validate_publish_ready(version=version, notes_text=notes_text)


def _validate_github_release_check(*, version: str, github_release_check_json: Path) -> None:
    payload = _read_json(github_release_check_json)
    release_evidence_packet.validate_github_release_check(
        version=version,
        github_release_check_payload=payload,
    )


def _validate_rehearsal_manifest(
    *,
    version: str,
    rehearsal_manifest: Path,
    rehearsal_output_dir: Path | None = None,
) -> dict[str, Any]:
    result = verify_release_rehearsal.verify_release_rehearsal_manifest(
        rehearsal_manifest,
        output_dir=rehearsal_output_dir,
    )
    if not result["ok"]:
        errors = result.get("errors") or ["release rehearsal manifest verification failed."]
        raise ReleaseArtifactDoctorError("; ".join(str(error) for error in errors))
    if result.get("package_version") != version:
        raise ReleaseArtifactDoctorError(
            "release rehearsal manifest package_version "
            f"{result.get('package_version')!r} does not match requested version {version!r}."
        )
    release_label = release_notes.normalize_version(version)
    if result.get("release_version") != release_label:
        raise ReleaseArtifactDoctorError(
            "release rehearsal manifest release_version "
            f"{result.get('release_version')!r} does not match requested release label {release_label!r}."
        )
    return result


def check_release_artifacts(
    *,
    version: str,
    stage: str,
    rehearsal_manifest: Path | None = None,
    rehearsal_output_dir: Path | None = None,
    release_check_json: Path | None = None,
    release_check_summary_file: Path | None = None,
    release_notes_file: Path | None = None,
    github_release_check_json: Path | None = None,
    changelog: Path = DEFAULT_CHANGELOG,
) -> dict[str, Any]:
    if stage not in STAGES:
        raise ReleaseArtifactDoctorError(f"stage must be one of: {', '.join(STAGES)}.")

    checks: list[dict[str, Any]] = []
    normalized = release_notes.normalize_version(version)

    if stage == "rehearsal":
        rehearsal_manifest_path = _require_path(
            checks,
            name="release rehearsal manifest",
            path=rehearsal_manifest,
            next_action=(
                "Run `python scripts/rehearse_release.py --version <version> --date <date> "
                "--output-dir <dir>`, then `python scripts/verify_release_rehearsal.py <manifest>`."
            ),
        )
        if rehearsal_manifest_path:
            rehearsal_result = _safe_validate(
                checks,
                name="release rehearsal manifest verification",
                path=rehearsal_manifest_path,
                action=lambda: _validate_rehearsal_manifest(
                    version=version,
                    rehearsal_manifest=rehearsal_manifest_path,
                    rehearsal_output_dir=rehearsal_output_dir,
                ),
                next_action="Rerun `scripts/rehearse_release.py`, then verify the new manifest.",
            )
            if rehearsal_result:
                checks[-1]["detail"] = (
                    f"Verified {rehearsal_result['verified_artifacts']} of "
                    f"{rehearsal_result['artifact_count']} rehearsal artifacts."
                )

        failed = [check for check in checks if check["status"] == "failed"]
        next_actions = [
            check["next_action"]
            for check in checks
            if check["status"] == "failed" and check.get("next_action")
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "ok": not failed,
            "status": "ready" if not failed else "blocked",
            "version": version,
            "release_label": normalized,
            "stage": stage,
            "checks": checks,
            "next_actions": list(dict.fromkeys(next_actions)),
        }

    release_check_json_path = _require_path(
        checks,
        name="release-check JSON",
        path=release_check_json,
        next_action="Run `scripts/release-check.ps1 -RequireCleanGit -JsonOutput <path>`.",
    )
    release_check_summary_path = _require_path(
        checks,
        name="release-check Markdown summary",
        path=release_check_summary_file,
        next_action="Run `python scripts/release_check_summary.py <release-check-json> --output <summary.md>`.",
    )

    if stage == "final-notes":
        changelog_path = _require_path(
            checks,
            name="CHANGELOG.md",
            path=changelog,
            next_action="Pass `--changelog <path>` or run from the AgentLedger repository root.",
        )
        if changelog_path:
            _safe_validate(
                checks,
                name="changelog release section",
                path=changelog_path,
                action=lambda: _validate_changelog(version=version, changelog=changelog_path),
                next_action="Run `python scripts/prepare_release.py --version <version> --date <date>` after a dry run.",
            )

    if release_check_json_path and release_check_summary_path:
        if stage == "final-notes":
            _safe_validate(
                checks,
                name="release-check readiness for final notes",
                path=release_check_json_path,
                action=lambda: _validate_release_check_for_final_notes(
                    version=version,
                    release_check_json=release_check_json_path,
                    release_check_summary_file=release_check_summary_path,
                ),
                next_action="Regenerate the release-check JSON and Markdown summary from a clean branch.",
            )
        else:
            _safe_validate(
                checks,
                name="release-check readiness for packet",
                path=release_check_json_path,
                action=lambda: _validate_release_check_for_packet(
                    version=version,
                    release_check_json=release_check_json_path,
                    release_check_summary_file=release_check_summary_path,
                ),
                next_action="Regenerate the release-check JSON and Markdown summary from the same clean run.",
            )

    if stage in {"post-release", "evidence-packet"}:
        release_notes_path = _require_path(
            checks,
            name="publish-ready release notes",
            path=release_notes_file,
            next_action="Run `scripts/finalize_release_notes.py` with real CI URLs and merge SHA.",
        )
        if release_notes_path:
            _safe_validate(
                checks,
                name="release notes publish readiness",
                path=release_notes_path,
                action=lambda: _validate_release_notes(
                    version=version,
                    release_notes_file=release_notes_path,
                ),
                next_action="Finalize release notes and replace any TODO validation placeholders with real links.",
            )

    if stage == "evidence-packet":
        github_release_check_path = _require_path(
            checks,
            name="GitHub release check JSON",
            path=github_release_check_json,
            next_action="Run `python scripts/check_github_release.py --version <version> --format json --output <path>`.",
        )
        if github_release_check_path:
            _safe_validate(
                checks,
                name="GitHub release check readiness",
                path=github_release_check_path,
                action=lambda: _validate_github_release_check(
                    version=version,
                    github_release_check_json=github_release_check_path,
                ),
                next_action="Fix or republish the GitHub release, then rerun `scripts/check_github_release.py`.",
            )

    failed = [check for check in checks if check["status"] == "failed"]
    next_actions = [
        check["next_action"]
        for check in checks
        if check["status"] == "failed" and check.get("next_action")
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not failed,
        "status": "ready" if not failed else "blocked",
        "version": version,
        "release_label": normalized,
        "stage": stage,
        "checks": checks,
        "next_actions": list(dict.fromkeys(next_actions)),
    }


def format_text(result: dict[str, Any]) -> str:
    outcome = "OK" if result["ok"] else "BLOCKED"
    lines = [
        f"Release artifact doctor {outcome}: {result['stage']}",
        f"Version: {result['version']} ({result['release_label']})",
    ]
    for check in result["checks"]:
        prefix = "OK" if check["status"] == "passed" else "FAIL"
        location = f" [{check['path']}]" if check.get("path") else ""
        lines.append(f"- {prefix}: {check['name']}{location} - {check['detail']}")
    if result["next_actions"]:
        lines.append("Next actions:")
        for action in result["next_actions"]:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def format_markdown(result: dict[str, Any]) -> str:
    outcome = "passed" if result["ok"] else "blocked"
    lines = [
        "# AgentLedger Release Artifact Doctor",
        "",
        f"- Result: {outcome}",
        f"- Stage: {result['stage']}",
        f"- Version: {result['version']}",
        f"- Release label: {result['release_label']}",
        "",
        "## Checks",
        "",
        "| Check | Status | File | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for check in result["checks"]:
        detail = str(check["detail"]).replace("|", "\\|").replace("\n", " ")
        file_name = str(check.get("file") or "n/a").replace("|", "\\|")
        lines.append(f"| {check['name']} | {check['status']} | {file_name} | {detail} |")
    if result["next_actions"]:
        lines.extend(["", "## Next Actions", ""])
        for action in result["next_actions"]:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check release artifact paths before release rehearsal, final notes, or post-release commands."
    )
    parser.add_argument("--version", required=True, help="Package version, for example 0.1.8a0.")
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--rehearsal-manifest", type=Path)
    parser.add_argument("--rehearsal-output-dir", type=Path)
    parser.add_argument("--release-check-json", type=Path)
    parser.add_argument("--release-check-summary", type=Path)
    parser.add_argument("--release-notes", type=Path)
    parser.add_argument("--github-release-check-json", type=Path)
    parser.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", type=Path, help="Write formatted result to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.output:
            release_evidence_packet._ensure_public_safe_path(args.output, "output")
        result = check_release_artifacts(
            version=args.version,
            stage=args.stage,
            rehearsal_manifest=args.rehearsal_manifest,
            rehearsal_output_dir=args.rehearsal_output_dir,
            release_check_json=args.release_check_json,
            release_check_summary_file=args.release_check_summary,
            release_notes_file=args.release_notes,
            github_release_check_json=args.github_release_check_json,
            changelog=args.changelog,
        )
    except (OSError, ReleaseArtifactDoctorError, release_notes.ReleaseNotesError) as error:
        print(f"release_artifact_doctor.py: {error}", file=sys.stderr)
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
        print(f"Release artifact doctor written: {args.output}")
    else:
        print(rendered, end="")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
