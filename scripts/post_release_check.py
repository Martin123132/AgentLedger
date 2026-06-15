from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tempfile
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_github_release
import release_evidence_packet
import release_notes


SCHEMA_VERSION = "agentledger.post_release_check.v1"
GITHUB_RELEASE_CHECK_JSON = "agentledger-github-release-check.json"
GITHUB_RELEASE_CHECK_MARKDOWN = "agentledger-github-release-check.md"
RELEASE_EVIDENCE_PACKET_JSON = "agentledger-release-evidence.json"
RELEASE_EVIDENCE_PACKET_MARKDOWN = "agentledger-release-evidence.md"
POST_RELEASE_SUMMARY_JSON = "agentledger-post-release-check.json"
POST_RELEASE_SUMMARY_MARKDOWN = "agentledger-post-release-check.md"


def default_output_dir(version: str) -> Path:
    release_label = release_notes.normalize_version(version)
    return Path(tempfile.gettempdir()) / f"agentledger-post-release-{release_label}"


def _ensure_public_safe_output(path: Path, label: str) -> None:
    release_evidence_packet._ensure_public_safe_path(path, label)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_post_release_markdown(summary: dict[str, Any]) -> str:
    status = "passed" if summary.get("ok") else "failed"
    lines = [
        "# AgentLedger Post-Release Check",
        "",
        f"- Result: {status}",
        f"- Version: {summary.get('version')}",
        f"- Tag: {summary.get('tag')}",
        f"- Repository: {summary.get('repository')}",
        f"- Output directory: {summary.get('output_dir')}",
        "",
        "## Outputs",
        "",
        f"- GitHub release check JSON: {summary.get('github_release_check_json') or 'not written'}",
        f"- GitHub release check Markdown: {summary.get('github_release_check_markdown') or 'not written'}",
        f"- Release evidence packet JSON: {summary.get('release_evidence_packet_json') or 'not written'}",
        f"- Release evidence packet Markdown: {summary.get('release_evidence_packet_markdown') or 'not written'}",
    ]
    if summary.get("errors"):
        lines.extend(["", "## Errors", ""])
        for error in summary["errors"]:
            lines.append(f"- {error}")
    lines.extend(
        [
            "",
            "## Handling Notes",
            "",
            "- Keep post-release artifacts outside the repo unless they have been reviewed.",
            "- Do not commit `.agentledger/` evidence folders, zip bundles, or signing keys.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def run_post_release_check(
    *,
    version: str,
    release_check_json: Path,
    release_check_summary_file: Path,
    release_notes_file: Path,
    output_dir: Path,
    release_json: Path | None = None,
    repository: str = check_github_release.DEFAULT_REPOSITORY,
    gh: str = "gh",
    require_prerelease: bool = True,
) -> dict[str, Any]:
    out = output_dir.resolve()
    github_json = out / GITHUB_RELEASE_CHECK_JSON
    github_markdown = out / GITHUB_RELEASE_CHECK_MARKDOWN
    packet_json = out / RELEASE_EVIDENCE_PACKET_JSON
    packet_markdown = out / RELEASE_EVIDENCE_PACKET_MARKDOWN
    summary_json = out / POST_RELEASE_SUMMARY_JSON
    summary_markdown = out / POST_RELEASE_SUMMARY_MARKDOWN

    for label, path in [
        ("output directory", out),
        ("release-check JSON", release_check_json),
        ("release-check Markdown summary", release_check_summary_file),
        ("release notes", release_notes_file),
        ("GitHub release check JSON output", github_json),
        ("GitHub release check Markdown output", github_markdown),
        ("release evidence packet JSON output", packet_json),
        ("release evidence packet Markdown output", packet_markdown),
        ("post-release summary JSON output", summary_json),
        ("post-release summary Markdown output", summary_markdown),
    ]:
        _ensure_public_safe_output(path, label)
    if release_json is not None:
        _ensure_public_safe_output(release_json, "saved GitHub release JSON")

    if release_json is not None:
        release = check_github_release.load_release_payload(release_json)
    else:
        tag = check_github_release.release_tag(version)
        release = check_github_release.run_gh_release_view(tag=tag, repository=repository, gh=gh)

    github_result = check_github_release.check_github_release(
        version=version,
        release=release,
        repository=repository,
        require_prerelease=require_prerelease,
    )
    _write_json(github_json, github_result)
    _write_text(github_markdown, check_github_release.format_markdown(github_result))

    summary: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "ok": False,
        "status": "failed",
        "version": version,
        "tag": check_github_release.release_tag(version),
        "repository": repository,
        "output_dir": str(out),
        "github_release_check_json": str(github_json),
        "github_release_check_markdown": str(github_markdown),
        "release_evidence_packet_json": None,
        "release_evidence_packet_markdown": None,
        "summary_json": str(summary_json),
        "summary_markdown": str(summary_markdown),
        "errors": list(github_result.get("errors", [])),
    }

    if github_result["ok"]:
        packet = release_evidence_packet.build_release_evidence_packet(
            version=version,
            release_check_json=release_check_json,
            release_check_summary_file=release_check_summary_file,
            release_notes_file=release_notes_file,
            github_release_check_json=github_json,
        )
        _write_json(packet_json, packet)
        _write_text(packet_markdown, release_evidence_packet.render_release_evidence_packet_markdown(packet))
        summary.update(
            ok=True,
            status="ready",
            release_evidence_packet_json=str(packet_json),
            release_evidence_packet_markdown=str(packet_markdown),
            errors=[],
        )

    _write_json(summary_json, summary)
    _write_text(summary_markdown, render_post_release_markdown(summary))
    return summary


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run AgentLedger post-release checks and build a public-safe evidence packet."
    )
    parser.add_argument("--version", required=True, help="Package version, for example 0.1.8a0.")
    parser.add_argument("--release-check-json", type=Path, required=True)
    parser.add_argument("--release-check-summary", type=Path, required=True)
    parser.add_argument("--release-notes", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for post-release artifacts. Defaults to a temp directory for the release label.",
    )
    parser.add_argument(
        "--release-json",
        type=Path,
        help="Read saved gh release JSON instead of calling gh release view.",
    )
    parser.add_argument(
        "--repo",
        default=check_github_release.DEFAULT_REPOSITORY,
        help=f"GitHub repository. Defaults to {check_github_release.DEFAULT_REPOSITORY}.",
    )
    parser.add_argument("--gh", default="gh", help="GitHub CLI executable. Defaults to gh.")
    parser.add_argument(
        "--allow-final-release",
        action="store_true",
        help="Do not require the GitHub release to be marked as a prerelease.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        output_dir = args.output_dir or default_output_dir(args.version)
        summary = run_post_release_check(
            version=args.version,
            release_check_json=args.release_check_json,
            release_check_summary_file=args.release_check_summary,
            release_notes_file=args.release_notes,
            output_dir=output_dir,
            release_json=args.release_json,
            repository=args.repo,
            gh=args.gh,
            require_prerelease=not args.allow_final_release,
        )
    except (
        OSError,
        check_github_release.GitHubReleaseCheckError,
        release_evidence_packet.ReleaseEvidencePacketError,
        release_notes.ReleaseNotesError,
    ) as error:
        print(f"post_release_check.py: {error}", file=sys.stderr)
        return 2

    print(f"Post-release check: {summary['version']} -> {summary['tag']}")
    print(f"Status: {summary['status']}")
    print(f"Summary: {summary['summary_markdown']}")
    print(f"JSON: {summary['summary_json']}")
    print(f"GitHub release check JSON: {summary['github_release_check_json']}")
    print(f"GitHub release check Markdown: {summary['github_release_check_markdown']}")
    if summary.get("release_evidence_packet_json"):
        print(f"Release evidence packet JSON: {summary['release_evidence_packet_json']}")
        print(f"Release evidence packet Markdown: {summary['release_evidence_packet_markdown']}")
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
