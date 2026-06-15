from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_notes


DEFAULT_REPOSITORY = "Martin123132/AgentLedger"
SCHEMA_VERSION = "agentledger.github_release_check.v1"
GH_RELEASE_FIELDS = [
    "tagName",
    "name",
    "url",
    "isDraft",
    "isPrerelease",
    "targetCommitish",
    "createdAt",
    "publishedAt",
    "body",
]


class GitHubReleaseCheckError(ValueError):
    pass


def release_tag(version: str) -> str:
    return f"v{release_notes.normalize_version(version)}"


def _add_check(checks: list[dict[str, str]], name: str, ok: bool, detail: str) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if ok else "failed",
            "detail": detail,
        }
    )


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def run_gh_release_view(*, tag: str, repository: str, gh: str = "gh") -> dict[str, Any]:
    command = [
        gh,
        "release",
        "view",
        tag,
        "--repo",
        repository,
        "--json",
        ",".join(GH_RELEASE_FIELDS),
    ]
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"{gh} exited {completed.returncode}"
        raise GitHubReleaseCheckError(f"gh release view failed: {detail}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise GitHubReleaseCheckError(f"gh release view returned invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise GitHubReleaseCheckError("gh release view JSON must be an object.")
    return payload


def load_release_payload(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise GitHubReleaseCheckError(f"Invalid release JSON in {path}: {error}") from error
    if not isinstance(payload, dict):
        raise GitHubReleaseCheckError("release JSON must be an object.")
    return payload


def check_github_release(
    *,
    version: str,
    release: dict[str, Any],
    repository: str = DEFAULT_REPOSITORY,
    require_prerelease: bool = True,
) -> dict[str, Any]:
    expected_tag = release_tag(version)
    normalized = release_notes.normalize_version(version)
    checks: list[dict[str, str]] = []

    tag_name = _string(release.get("tagName"))
    _add_check(
        checks,
        "release tag",
        tag_name == expected_tag,
        f"tagName is {tag_name!r}; expected {expected_tag!r}",
    )

    is_draft = _as_bool(release.get("isDraft"))
    _add_check(
        checks,
        "not draft",
        is_draft is False,
        f"isDraft is {is_draft!r}; expected False",
    )

    is_prerelease = _as_bool(release.get("isPrerelease"))
    _add_check(
        checks,
        "prerelease status",
        (is_prerelease is True) if require_prerelease else (is_prerelease is not None),
        f"isPrerelease is {is_prerelease!r}; expected True",
    )

    url = _string(release.get("url")).strip()
    _add_check(
        checks,
        "release url",
        url.startswith(f"https://github.com/{repository}/releases/"),
        f"url is {url!r}; expected a GitHub release URL for {repository}",
    )

    body = _string(release.get("body"))
    try:
        release_notes.validate_publish_ready(version=version, notes_text=body)
    except release_notes.ReleaseNotesError as error:
        _add_check(checks, "release body", False, str(error))
    else:
        _add_check(
            checks,
            "release body",
            True,
            "release body is publish-ready and has validation evidence",
        )

    published_at = _string(release.get("publishedAt")).strip()
    _add_check(
        checks,
        "published timestamp",
        bool(published_at),
        f"publishedAt is {published_at!r}",
    )

    failed = [check for check in checks if check["status"] == "failed"]
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not failed,
        "status": "ready" if not failed else "failed",
        "repository": repository,
        "version": version,
        "release_label": normalized,
        "tag": expected_tag,
        "release": {
            "tag_name": tag_name or None,
            "name": _string(release.get("name")) or None,
            "url": url or None,
            "is_draft": is_draft,
            "is_prerelease": is_prerelease,
            "target_commitish": _string(release.get("targetCommitish")) or None,
            "created_at": _string(release.get("createdAt")) or None,
            "published_at": published_at or None,
        },
        "checks": checks,
        "errors": [f"{check['name']}: {check['detail']}" for check in failed],
    }


def format_text(result: dict[str, Any]) -> str:
    outcome = "OK" if result["ok"] else "FAILED"
    lines = [
        f"GitHub release check {outcome}: {result['tag']}",
        f"Repository: {result['repository']}",
        f"Release URL: {result['release'].get('url') or 'n/a'}",
    ]
    for check in result["checks"]:
        prefix = "OK" if check["status"] == "passed" else "FAIL"
        lines.append(f"- {prefix}: {check['name']} - {check['detail']}")
    return "\n".join(lines)


def format_markdown(result: dict[str, Any]) -> str:
    outcome = "passed" if result["ok"] else "failed"
    release = result["release"]
    lines = [
        "# AgentLedger GitHub Release Check",
        "",
        f"- Result: {outcome}",
        f"- Repository: {result['repository']}",
        f"- Version: {result['version']}",
        f"- Tag: {result['tag']}",
        f"- Release URL: {release.get('url') or 'n/a'}",
        f"- Prerelease: {release.get('is_prerelease')}",
        f"- Draft: {release.get('is_draft')}",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in result["checks"]:
        detail = check["detail"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {check['name']} | {check['status']} | {detail} |")
    if result["errors"]:
        lines.extend(["", "## Errors", ""])
        for error in result["errors"]:
            lines.append(f"- {error}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a published GitHub prerelease for AgentLedger."
    )
    parser.add_argument("--version", required=True, help="Package version, for example 0.1.8a0.")
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPOSITORY,
        help=f"GitHub repository. Defaults to {DEFAULT_REPOSITORY}.",
    )
    parser.add_argument(
        "--release-json",
        type=Path,
        help="Read saved gh release JSON instead of calling gh release view.",
    )
    parser.add_argument("--gh", default="gh", help="GitHub CLI executable. Defaults to gh.")
    parser.add_argument(
        "--allow-final-release",
        action="store_true",
        help="Do not require isPrerelease=true.",
    )
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", type=Path, help="Write formatted output to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    tag = release_tag(args.version)
    try:
        if args.release_json:
            release = load_release_payload(args.release_json)
        else:
            release = run_gh_release_view(tag=tag, repository=args.repo, gh=args.gh)
        result = check_github_release(
            version=args.version,
            release=release,
            repository=args.repo,
            require_prerelease=not args.allow_final_release,
        )
    except (OSError, GitHubReleaseCheckError, release_notes.ReleaseNotesError) as error:
        print(f"check_github_release.py: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        rendered = json.dumps(result, indent=2) + "\n"
    elif args.format == "markdown":
        rendered = format_markdown(result)
    else:
        rendered = format_text(result) + "\n"

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"GitHub release check written: {args.output}")
    else:
        print(rendered, end="")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
