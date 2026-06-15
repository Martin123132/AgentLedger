from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import check_release_metadata
import check_release_process
import release_command_index
import release_notes


ROOT = SCRIPT_DIR.parent
SCHEMA_VERSION = "agentledger.release_readiness_report.v1"
FORBIDDEN_TRACKED_PATHS = [
    ".agentledger",
    "*.zip",
    ".agentledger-signing-key*",
    "agentledger-signing-key*",
]


class ReleaseReadinessReportError(ValueError):
    pass


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _command_output(completed: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(
        part.strip()
        for part in [completed.stdout, completed.stderr]
        if part and part.strip()
    )


def _add_check(
    checks: list[dict[str, Any]],
    *,
    category: str,
    name: str,
    status: str,
    detail: str,
    next_action: str | None = None,
) -> None:
    check: dict[str, Any] = {
        "category": category,
        "name": name,
        "status": status,
        "detail": detail,
    }
    if status != "passed" and next_action:
        check["next_action"] = next_action
    checks.append(check)


def _status_counts(checks: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(checks),
        "passed": sum(1 for check in checks if check["status"] == "passed"),
        "warnings": sum(1 for check in checks if check["status"] == "warning"),
        "failed": sum(1 for check in checks if check["status"] == "failed"),
    }


def _git_value(repo_root: Path, *args: str) -> str | None:
    completed = _git(repo_root, *args)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def _check_release_notes_source(repo_root: Path, version: str) -> None:
    changelog = repo_root / "CHANGELOG.md"
    changelog_text = changelog.read_text(encoding="utf-8-sig")
    release_notes.extract_changelog_section(changelog_text, version)


def build_release_readiness_report(
    *,
    repo_root: Path = ROOT,
    release_process_doc: Path | None = None,
    repository: str = release_command_index.DEFAULT_REPOSITORY,
    require_clean_git: bool = False,
) -> dict[str, Any]:
    root = repo_root.resolve()
    doc = release_process_doc or root / "docs" / "release-process.md"
    checks: list[dict[str, Any]] = []
    metadata: dict[str, Any] | None = None
    process: dict[str, Any] | None = None
    working_tree_dirty: bool | None = None

    branch = _git_value(root, "branch", "--show-current")
    head = _git_value(root, "rev-parse", "--short", "HEAD")

    try:
        metadata = check_release_metadata.check_release_metadata(root)
    except OSError as error:
        _add_check(
            checks,
            category="release",
            name="release metadata",
            status="failed",
            detail=str(error),
            next_action="Restore required release metadata files and rerun the report.",
        )
    else:
        _add_check(
            checks,
            category="release",
            name="release metadata",
            status="passed" if metadata["ok"] else "failed",
            detail=(
                f"{metadata.get('project_name') or 'unknown'} "
                f"{metadata.get('project_version') or 'unknown'} "
                f"({metadata.get('release_label') or 'unknown'})"
                if metadata["ok"]
                else "; ".join(metadata.get("errors", []))
            ),
            next_action="Run `python scripts/check_release_metadata.py` and fix the reported metadata issue.",
        )

    version = metadata.get("project_version") if metadata else None
    release_date = metadata.get("release_date") if metadata else None
    if version and release_date:
        try:
            process = check_release_process.check_release_process(
                version=version,
                release_date=release_date,
                doc=doc,
                repository=repository,
            )
        except (
            OSError,
            check_release_process.ReleaseProcessCheckError,
            release_command_index.ReleaseCommandIndexError,
        ) as error:
            _add_check(
                checks,
                category="release",
                name="release process docs",
                status="failed",
                detail=str(error),
                next_action="Run `python scripts/check_release_process.py` and fix the reported release-process drift.",
            )
        else:
            summary = process["summary"]
            _add_check(
                checks,
                category="release",
                name="release process docs",
                status="passed" if process["ok"] else "failed",
                detail=(
                    f"{summary['passed']} passed, {summary['failed']} failed, "
                    f"{summary['total']} total"
                ),
                next_action="Update docs/release-process.md or scripts/release_command_index.py so the release flow stays aligned.",
            )
    else:
        _add_check(
            checks,
            category="release",
            name="release process docs",
            status="failed",
            detail="Release metadata did not provide both project_version and release_date.",
            next_action="Fix release metadata before checking release-process documentation alignment.",
        )

    if version:
        try:
            _check_release_notes_source(root, version)
        except (OSError, release_notes.ReleaseNotesError) as error:
            _add_check(
                checks,
                category="release",
                name="release notes source",
                status="failed",
                detail=str(error),
                next_action="Run `python scripts/release_notes.py --version <version> --check` and fix CHANGELOG.md.",
            )
        else:
            _add_check(
                checks,
                category="release",
                name="release notes source",
                status="passed",
                detail=f"CHANGELOG.md contains a release notes source section for {version}.",
            )
    else:
        _add_check(
            checks,
            category="release",
            name="release notes source",
            status="failed",
            detail="Release metadata did not provide project_version.",
            next_action="Fix release metadata before checking release notes source.",
        )

    diff_check = _git(root, "diff", "--check")
    _add_check(
        checks,
        category="git",
        name="diff whitespace",
        status="passed" if diff_check.returncode == 0 else "failed",
        detail="git diff --check passed." if diff_check.returncode == 0 else _command_output(diff_check),
        next_action="Fix whitespace errors reported by `git diff --check`.",
    )

    tracked = _git(root, "ls-files", *FORBIDDEN_TRACKED_PATHS)
    tracked_paths = [line.strip() for line in tracked.stdout.splitlines() if line.strip()]
    if tracked.returncode != 0:
        _add_check(
            checks,
            category="git",
            name="tracked private artifacts",
            status="failed",
            detail=_command_output(tracked),
            next_action="Fix the git pathspec check and rerun the report.",
        )
    else:
        _add_check(
            checks,
            category="git",
            name="tracked private artifacts",
            status="failed" if tracked_paths else "passed",
            detail=(
                "No generated evidence bundles or signing keys are tracked."
                if not tracked_paths
                else "Tracked generated/private paths: " + ", ".join(tracked_paths)
            ),
            next_action="Remove generated evidence bundles or signing-key files from git before release.",
        )

    status = _git(root, "status", "--short", "--untracked-files=all")
    if status.returncode != 0:
        _add_check(
            checks,
            category="git",
            name="working tree",
            status="failed",
            detail=_command_output(status),
            next_action="Fix the git status error and rerun the report.",
        )
    else:
        status_lines = [line for line in status.stdout.splitlines() if line.strip()]
        working_tree_dirty = bool(status_lines)
        if working_tree_dirty and require_clean_git:
            check_status = "failed"
            detail = "Working tree is not clean:\n" + "\n".join(status_lines)
            next_action = "Commit or remove local changes before running release checks with --require-clean-git."
        elif working_tree_dirty:
            check_status = "warning"
            detail = "Working tree has local changes; clean checkout is still required before tagging."
            next_action = "Rerun with --require-clean-git from a clean checkout before tagging."
        else:
            check_status = "passed"
            detail = "Working tree clean."
            next_action = None
        _add_check(
            checks,
            category="git",
            name="working tree",
            status=check_status,
            detail=detail,
            next_action=next_action,
        )

    summary = _status_counts(checks)
    ok = summary["failed"] == 0
    status_text = "failed"
    if ok:
        status_text = "ready_with_warnings" if summary["warnings"] else "ready"

    return {
        "schema_version": SCHEMA_VERSION,
        "ok": ok,
        "status": status_text,
        "repo": str(root),
        "branch": branch,
        "head": head,
        "repository": repository,
        "package_version": metadata.get("package_version") if metadata else None,
        "project_version": metadata.get("project_version") if metadata else None,
        "release_label": metadata.get("release_label") if metadata else None,
        "release_date": release_date,
        "require_clean_git": require_clean_git,
        "working_tree_dirty": working_tree_dirty,
        "release_metadata": metadata,
        "release_process": process,
        "summary": summary,
        "checks": checks,
        "errors": [check["detail"] for check in checks if check["status"] == "failed"],
        "warnings": [check["detail"] for check in checks if check["status"] == "warning"],
        "next_actions": list(
            dict.fromkeys(
                check["next_action"]
                for check in checks
                if check.get("next_action") and check["status"] != "passed"
            )
        ),
    }


def format_text(result: dict[str, Any]) -> str:
    outcome = "FAILED"
    if result["ok"]:
        outcome = "WARN" if result["summary"]["warnings"] else "READY"
    lines = [
        (
            "Release readiness report "
            f"{outcome}: {result.get('project_version') or 'unknown'} -> "
            f"{result.get('release_label') or 'unknown'}"
        ),
        f"Repository: {result['repo']}",
        f"Branch: {result.get('branch') or 'n/a'}",
        f"HEAD: {result.get('head') or 'n/a'}",
        (
            "Checks: "
            f"{result['summary']['passed']} passed, "
            f"{result['summary']['warnings']} warnings, "
            f"{result['summary']['failed']} failed, "
            f"{result['summary']['total']} total"
        ),
    ]
    prefixes = {"passed": "OK", "warning": "WARN", "failed": "FAIL"}
    for check in result["checks"]:
        prefix = prefixes.get(check["status"], check["status"].upper())
        lines.append(f"- {prefix}: {check['category']} {check['name']} - {check['detail']}")
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
    lines = [
        "# AgentLedger Release Readiness Report",
        "",
        f"- Result: {result['status']}",
        f"- Version: {result.get('project_version') or 'n/a'}",
        f"- Release label: {result.get('release_label') or 'n/a'}",
        f"- Release date: {result.get('release_date') or 'n/a'}",
        f"- Repository: `{result['repo']}`",
        f"- Branch: {result.get('branch') or 'n/a'}",
        f"- HEAD: {result.get('head') or 'n/a'}",
        f"- Require clean git: {str(bool(result.get('require_clean_git'))).lower()}",
        f"- Working tree dirty: {str(bool(result.get('working_tree_dirty'))).lower()}",
        (
            "- Checks: "
            f"{result['summary']['passed']} passed, "
            f"{result['summary']['warnings']} warnings, "
            f"{result['summary']['failed']} failed, "
            f"{result['summary']['total']} total"
        ),
        "",
        "## Checks",
        "",
        "| Category | Check | Status | Detail |",
        "| --- | --- | --- | --- |",
    ]
    for check in result["checks"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_cell(check.get("category")),
                    _escape_cell(check.get("name")),
                    _escape_cell(check.get("status")),
                    _escape_cell(check.get("detail")),
                ]
            )
            + " |"
        )
    if result["next_actions"]:
        lines.extend(["", "## Next Actions", ""])
        for action in result["next_actions"]:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the fast AgentLedger release-readiness report without pytest, wheel, install, or smoke checks."
    )
    parser.add_argument("--repo-root", type=Path, default=ROOT, help="Repository root. Defaults to this checkout.")
    parser.add_argument("--release-process-doc", type=Path, help="Release process Markdown document.")
    parser.add_argument(
        "--repo",
        default=release_command_index.DEFAULT_REPOSITORY,
        help=f"GitHub repository. Defaults to {release_command_index.DEFAULT_REPOSITORY}.",
    )
    parser.add_argument("--require-clean-git", action="store_true", help="Fail when the working tree is dirty.")
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", type=Path, help="Write formatted result to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = build_release_readiness_report(
            repo_root=args.repo_root,
            release_process_doc=args.release_process_doc,
            repository=args.repo,
            require_clean_git=args.require_clean_git,
        )
    except (OSError, ReleaseReadinessReportError) as error:
        print(f"release_readiness_report.py: {error}", file=sys.stderr)
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
        print(f"Release readiness report written: {args.output}")
    else:
        print(rendered, end="")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
