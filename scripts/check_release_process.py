from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_command_index


ROOT = SCRIPT_DIR.parent
DEFAULT_DOC = ROOT / "docs" / "release-process.md"
DEFAULT_VERSION = "0.1.9a0"
DEFAULT_DATE = "2026-06-16"
SCHEMA_VERSION = "agentledger.release_process_check.v1"


class ReleaseProcessCheckError(ValueError):
    pass


def _add_check(
    checks: list[dict[str, Any]],
    *,
    category: str,
    name: str,
    status: str,
    detail: str,
    expected: str | None = None,
    next_action: str | None = None,
) -> None:
    check: dict[str, Any] = {
        "category": category,
        "name": name,
        "status": status,
        "detail": detail,
    }
    if expected is not None:
        check["expected"] = expected
    if status == "failed" and next_action:
        check["next_action"] = next_action
    checks.append(check)


def _contains(doc_text: str, needle: str) -> bool:
    return needle in doc_text.replace("\r\n", "\n")


def check_release_process(
    *,
    version: str = DEFAULT_VERSION,
    release_date: str = DEFAULT_DATE,
    doc: Path = DEFAULT_DOC,
    repository: str = release_command_index.DEFAULT_REPOSITORY,
) -> dict[str, Any]:
    try:
        doc_text = doc.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise ReleaseProcessCheckError(f"Could not read release process doc {doc}: {error}") from error

    index = release_command_index.build_release_command_index(
        version=version,
        release_date=release_date,
        repository=repository,
    )
    checks: list[dict[str, Any]] = []

    _add_check(
        checks,
        category="schema",
        name="release command index schema",
        status="passed" if _contains(doc_text, index["schema_version"]) else "failed",
        detail=(
            "Release command index schema is documented."
            if _contains(doc_text, index["schema_version"])
            else "Release command index schema is missing from release-process.md."
        ),
        expected=index["schema_version"],
        next_action="Document the release command index schema near the release command index step.",
    )

    for name, value in index["artifacts"].items():
        _add_check(
            checks,
            category="artifact",
            name=name,
            status="passed" if _contains(doc_text, value) else "failed",
            detail=(
                f"Documented artifact path {value}."
                if _contains(doc_text, value)
                else f"Missing documented artifact path {value}."
            ),
            expected=value,
            next_action="Update docs/release-process.md or scripts/release_command_index.py so artifact filenames match.",
        )

    for placeholder in index["placeholders"]:
        _add_check(
            checks,
            category="placeholder",
            name=placeholder,
            status="passed" if _contains(doc_text, placeholder) else "failed",
            detail=(
                f"Documented placeholder {placeholder}."
                if _contains(doc_text, placeholder)
                else f"Missing placeholder {placeholder}."
            ),
            expected=placeholder,
            next_action="Update docs/release-process.md to show every placeholder that must be replaced.",
        )

    for item in index["do_not_commit"]:
        _add_check(
            checks,
            category="handling",
            name=item,
            status="passed" if _contains(doc_text, item) else "failed",
            detail=(
                f"Documented do-not-commit item {item}."
                if _contains(doc_text, item)
                else f"Missing do-not-commit item {item}."
            ),
            expected=item,
            next_action="Update docs/release-process.md handling notes to match the command index guardrails.",
        )

    for section in index["sections"]:
        for command in section["commands"]:
            _add_check(
                checks,
                category="command",
                name=section["name"],
                status="passed" if _contains(doc_text, command) else "failed",
                detail=(
                    "Documented command."
                    if _contains(doc_text, command)
                    else "Command from generated release index is missing from release-process.md."
                ),
                expected=command,
                next_action="Update docs/release-process.md or scripts/release_command_index.py so the release flow stays aligned.",
            )

    failed = [check for check in checks if check["status"] == "failed"]
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not failed,
        "status": "ready" if not failed else "failed",
        "version": index["version"],
        "release_label": index["release_label"],
        "release_date": index["release_date"],
        "repository": index["repository"],
        "doc": str(doc),
        "index_schema_version": index["schema_version"],
        "summary": {
            "total": len(checks),
            "passed": len(checks) - len(failed),
            "failed": len(failed),
        },
        "checks": checks,
        "errors": [f"{check['category']}: {check['expected']}" for check in failed],
        "next_actions": list(
            dict.fromkeys(
                check["next_action"]
                for check in failed
                if check.get("next_action")
            )
        ),
    }


def format_text(result: dict[str, Any]) -> str:
    outcome = "OK" if result["ok"] else "FAILED"
    lines = [
        f"Release process check {outcome}: {result['version']} -> {result['release_label']}",
        f"Document: {result['doc']}",
        (
            "Checks: "
            f"{result['summary']['passed']} passed, "
            f"{result['summary']['failed']} failed, "
            f"{result['summary']['total']} total"
        ),
    ]
    for check in result["checks"]:
        if check["status"] == "failed":
            lines.append(f"- FAIL: {check['category']} {check['name']} - {check['detail']}")
            lines.append(f"  Expected: {check['expected']}")
    if result["next_actions"]:
        lines.append("Next actions:")
        for action in result["next_actions"]:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def format_markdown(result: dict[str, Any]) -> str:
    outcome = "passed" if result["ok"] else "failed"
    lines = [
        "# AgentLedger Release Process Check",
        "",
        f"- Result: {outcome}",
        f"- Version: {result['version']}",
        f"- Release label: {result['release_label']}",
        f"- Release date: {result['release_date']}",
        f"- Document: `{result['doc']}`",
        (
            "- Checks: "
            f"{result['summary']['passed']} passed, "
            f"{result['summary']['failed']} failed, "
            f"{result['summary']['total']} total"
        ),
    ]
    failed = [check for check in result["checks"] if check["status"] == "failed"]
    if failed:
        lines.extend(["", "## Missing From Release Process", "", "| Category | Section | Expected |", "| --- | --- | --- |"])
        for check in failed:
            expected = str(check["expected"]).replace("|", "\\|")
            lines.append(f"| {check['category']} | {check['name']} | `{expected}` |")
    if result["next_actions"]:
        lines.extend(["", "## Next Actions", ""])
        for action in result["next_actions"]:
            lines.append(f"- {action}")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify docs/release-process.md matches the generated release command index."
    )
    parser.add_argument("--version", default=DEFAULT_VERSION, help=f"Package version. Defaults to {DEFAULT_VERSION}.")
    parser.add_argument("--date", default=DEFAULT_DATE, help=f"Release date. Defaults to {DEFAULT_DATE}.")
    parser.add_argument("--doc", type=Path, default=DEFAULT_DOC, help="Release process Markdown document.")
    parser.add_argument(
        "--repo",
        default=release_command_index.DEFAULT_REPOSITORY,
        help=f"GitHub repository. Defaults to {release_command_index.DEFAULT_REPOSITORY}.",
    )
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", type=Path, help="Write formatted result to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = check_release_process(
            version=args.version,
            release_date=args.date,
            doc=args.doc,
            repository=args.repo,
        )
    except (OSError, ReleaseProcessCheckError, release_command_index.ReleaseCommandIndexError) as error:
        print(f"check_release_process.py: {error}", file=sys.stderr)
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
        print(f"Release process check written: {args.output}")
    else:
        print(rendered, end="")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
