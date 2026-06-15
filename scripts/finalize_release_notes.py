from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_check_summary
import release_notes


ROOT = SCRIPT_DIR.parent
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"
GITHUB_ACTIONS_RUN_RE = re.compile(
    r"^https://github\.com/Martin123132/AgentLedger/actions/runs/\d+(?:[/?#].*)?$"
)
MERGE_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")


class FinalizeReleaseNotesError(ValueError):
    pass


def _require_actions_url(value: str, label: str) -> str:
    url = value.strip()
    if not GITHUB_ACTIONS_RUN_RE.match(url):
        raise FinalizeReleaseNotesError(
            f"{label} must be a GitHub Actions run URL for Martin123132/AgentLedger."
        )
    return url


def _require_merge_sha(value: str) -> str:
    sha = value.strip()
    if not MERGE_SHA_RE.match(sha):
        raise FinalizeReleaseNotesError("merge SHA must be 7 to 40 hexadecimal characters.")
    return sha


def _release_metadata_counts(payload: dict[str, Any]) -> tuple[int, int]:
    metadata = payload.get("release_metadata")
    if not isinstance(metadata, dict):
        return (0, 0)
    return release_check_summary.release_metadata_counts(metadata)


def validate_release_check_for_publish(
    *,
    payload: dict[str, Any],
    version: str,
    summary_text: str,
) -> tuple[int, int]:
    release_check_summary.validate_release_check(payload)
    normalized = release_notes.normalize_version(version)
    payload_version = payload.get("package_version")
    if release_notes.normalize_version(str(payload_version)) != normalized:
        raise FinalizeReleaseNotesError(
            f"release-check package version {payload_version!r} does not match {version!r}."
        )
    if not payload.get("ok"):
        raise FinalizeReleaseNotesError("release-check JSON must have ok=true.")
    if payload.get("status") != "ready":
        raise FinalizeReleaseNotesError("release-check JSON must have status=ready from a clean checkout.")
    if payload.get("working_tree_dirty"):
        raise FinalizeReleaseNotesError("release-check JSON must come from a clean working tree.")
    if not payload.get("require_clean_git"):
        raise FinalizeReleaseNotesError("release-check JSON must be produced with -RequireCleanGit.")

    metadata = payload.get("release_metadata")
    if not isinstance(metadata, dict) or not metadata.get("ok"):
        raise FinalizeReleaseNotesError("release-check metadata payload must have ok=true.")
    metadata_passed, metadata_failed = _release_metadata_counts(payload)
    if metadata_failed:
        raise FinalizeReleaseNotesError("release-check metadata must have zero failed checks.")

    required_summary_fragments = [
        "# AgentLedger Release Readiness",
        "## Release Metadata",
        f"- Checks: {metadata_passed} passed, {metadata_failed} failed",
    ]
    missing = [fragment for fragment in required_summary_fragments if fragment not in summary_text]
    if missing:
        raise FinalizeReleaseNotesError(
            "release-check Markdown summary is missing expected fragment(s): "
            + ", ".join(repr(fragment) for fragment in missing)
        )
    return metadata_passed, metadata_failed


def build_validation_lines(
    *,
    version: str,
    release_check_payload: dict[str, Any],
    metadata_passed: int,
    metadata_failed: int,
    pr_ci_url: str,
    master_ci_url: str,
    release_readiness_url: str,
    tag_ci_url: str,
    merge_sha: str,
) -> list[str]:
    normalized = release_notes.normalize_version(version)
    short_head = str(release_check_payload.get("head") or "n/a")
    package_version = str(release_check_payload.get("package_version") or version)
    return [
        (
            "- Local release-check passed for "
            f"`{package_version}` at `{short_head}`; release metadata checks: "
            f"{metadata_passed} passed, {metadata_failed} failed."
        ),
        f"- PR CI passed on Ubuntu and Windows: {pr_ci_url}.",
        f"- Master CI passed for `{merge_sha}`: {master_ci_url}.",
        f"- Release Readiness passed on master: {release_readiness_url}.",
        f"- Tag CI passed for `v{normalized}`: {tag_ci_url}.",
    ]


def finalize_release_notes(
    *,
    version: str,
    changelog: Path,
    release_check_json: Path,
    release_check_summary_file: Path,
    pr_ci_url: str,
    master_ci_url: str,
    release_readiness_url: str,
    tag_ci_url: str,
    merge_sha: str,
    include_alpha_footer: bool = True,
) -> str:
    payload = release_check_summary.load_release_check(release_check_json)
    summary_text = release_check_summary_file.read_text(encoding="utf-8-sig")
    metadata_passed, metadata_failed = validate_release_check_for_publish(
        payload=payload,
        version=version,
        summary_text=summary_text,
    )
    validation_lines = build_validation_lines(
        version=version,
        release_check_payload=payload,
        metadata_passed=metadata_passed,
        metadata_failed=metadata_failed,
        pr_ci_url=_require_actions_url(pr_ci_url, "pr-ci-url"),
        master_ci_url=_require_actions_url(master_ci_url, "master-ci-url"),
        release_readiness_url=_require_actions_url(release_readiness_url, "release-readiness-url"),
        tag_ci_url=_require_actions_url(tag_ci_url, "tag-ci-url"),
        merge_sha=_require_merge_sha(merge_sha),
    )
    notes = release_notes.build_release_notes(
        version=version,
        changelog_text=changelog.read_text(encoding="utf-8-sig"),
        validation_lines=validation_lines,
        include_alpha_footer=include_alpha_footer,
    )
    release_notes.validate_publish_ready(
        version=version,
        notes_text=notes,
        require_alpha_footer=include_alpha_footer,
    )
    return notes


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build publish-ready GitHub prerelease notes from checked release evidence."
    )
    parser.add_argument("--version", required=True, help="Package version, for example 0.1.8a0.")
    parser.add_argument(
        "--changelog",
        type=Path,
        default=DEFAULT_CHANGELOG,
        help="Path to CHANGELOG.md. Defaults to the repository changelog.",
    )
    parser.add_argument("--release-check-json", type=Path, required=True, help="Clean release-check JSON summary.")
    parser.add_argument(
        "--release-check-summary",
        type=Path,
        required=True,
        help="Markdown summary rendered from the same release-check JSON.",
    )
    parser.add_argument("--pr-ci-url", required=True, help="GitHub Actions URL for the PR CI run.")
    parser.add_argument("--master-ci-url", required=True, help="GitHub Actions URL for master CI.")
    parser.add_argument(
        "--release-readiness-url",
        required=True,
        help="GitHub Actions URL for the manual Release Readiness run.",
    )
    parser.add_argument("--tag-ci-url", required=True, help="GitHub Actions URL for tag CI.")
    parser.add_argument("--merge-sha", required=True, help="Merge commit SHA validated by master CI.")
    parser.add_argument("--output", type=Path, help="Write publish-ready notes to this file instead of stdout.")
    parser.add_argument(
        "--no-alpha-footer",
        action="store_true",
        help="Omit the alpha prerelease evidence-handling footer.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        notes = finalize_release_notes(
            version=args.version,
            changelog=args.changelog,
            release_check_json=args.release_check_json,
            release_check_summary_file=args.release_check_summary,
            pr_ci_url=args.pr_ci_url,
            master_ci_url=args.master_ci_url,
            release_readiness_url=args.release_readiness_url,
            tag_ci_url=args.tag_ci_url,
            merge_sha=args.merge_sha,
            include_alpha_footer=not args.no_alpha_footer,
        )
    except (OSError, release_notes.ReleaseNotesError, release_check_summary.ReleaseCheckSummaryError, FinalizeReleaseNotesError) as error:
        print(f"finalize_release_notes.py: {error}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(notes, encoding="utf-8")
        print(f"Final release notes ready: {args.output}")
    else:
        print(notes, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
