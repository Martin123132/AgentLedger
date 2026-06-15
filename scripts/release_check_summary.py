from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


RELEASE_CHECK_SCHEMA = "agentledger.release_check.v1"
RELEASE_METADATA_SCHEMA = "agentledger.release_metadata_check.v1"
RELEASE_PROCESS_SCHEMA = "agentledger.release_process_check.v1"


class ReleaseCheckSummaryError(ValueError):
    pass


def _as_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseCheckSummaryError(f"{field} must be an object.")
    return value


def _as_list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReleaseCheckSummaryError(f"{field} must be a list.")
    return value


def _text(value: Any, fallback: str = "n/a") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _escape_cell(value: Any) -> str:
    text = _text(value, "")
    text = text.replace("|", "\\|")
    text = " ".join(text.splitlines())
    return text or "n/a"


def validate_release_check(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version != RELEASE_CHECK_SCHEMA:
        raise ReleaseCheckSummaryError(
            f"Expected schema_version {RELEASE_CHECK_SCHEMA}, got {_text(schema_version)!r}."
        )
    if not isinstance(payload.get("ok"), bool):
        raise ReleaseCheckSummaryError("ok must be a boolean.")

    for field in ["status", "repo", "branch", "head", "agentledger_version", "package_version"]:
        value = payload.get(field)
        if payload["ok"] and (not isinstance(value, str) or not value.strip()):
            raise ReleaseCheckSummaryError(f"{field} must be a non-empty string.")
        if value is not None and not isinstance(value, str):
            raise ReleaseCheckSummaryError(f"{field} must be a string when present.")

    steps = _as_list(payload.get("steps"), "steps")
    for index, step in enumerate(steps):
        step_payload = _as_mapping(step, f"steps[{index}]")
        if not isinstance(step_payload.get("name"), str) or not step_payload["name"].strip():
            raise ReleaseCheckSummaryError(f"steps[{index}].name must be a non-empty string.")
        if step_payload.get("status") not in {"passed", "failed"}:
            raise ReleaseCheckSummaryError(f"steps[{index}].status must be passed or failed.")

    metadata = payload.get("release_metadata")
    if metadata is None:
        if payload["ok"]:
            raise ReleaseCheckSummaryError("release_metadata is required when ok is true.")
        return

    metadata_payload = _as_mapping(metadata, "release_metadata")
    if metadata_payload.get("schema_version") != RELEASE_METADATA_SCHEMA:
        raise ReleaseCheckSummaryError(
            "release_metadata.schema_version must be "
            f"{RELEASE_METADATA_SCHEMA}."
        )
    if not isinstance(metadata_payload.get("ok"), bool):
        raise ReleaseCheckSummaryError("release_metadata.ok must be a boolean.")
    _as_list(metadata_payload.get("checks"), "release_metadata.checks")

    process = payload.get("release_process")
    if process is None:
        if payload["ok"]:
            raise ReleaseCheckSummaryError("release_process is required when ok is true.")
        return

    process_payload = _as_mapping(process, "release_process")
    if process_payload.get("schema_version") != RELEASE_PROCESS_SCHEMA:
        raise ReleaseCheckSummaryError(
            "release_process.schema_version must be "
            f"{RELEASE_PROCESS_SCHEMA}."
        )
    if not isinstance(process_payload.get("ok"), bool):
        raise ReleaseCheckSummaryError("release_process.ok must be a boolean.")
    summary = _as_mapping(process_payload.get("summary"), "release_process.summary")
    for field in ["total", "passed", "failed"]:
        if not isinstance(summary.get(field), int):
            raise ReleaseCheckSummaryError(f"release_process.summary.{field} must be an integer.")


def release_metadata_counts(metadata: dict[str, Any] | None) -> tuple[int, int]:
    if not metadata:
        return (0, 0)
    checks = [check for check in metadata.get("checks", []) if isinstance(check, dict)]
    passed = sum(1 for check in checks if check.get("status") == "passed")
    failed = sum(1 for check in checks if check.get("status") == "failed")
    return passed, failed


def release_process_counts(process: dict[str, Any] | None) -> tuple[int, int, int]:
    if not process:
        return (0, 0, 0)
    summary = process.get("summary", {})
    if not isinstance(summary, dict):
        return (0, 0, 0)
    total = summary.get("total")
    passed = summary.get("passed")
    failed = summary.get("failed")
    return (
        total if isinstance(total, int) else 0,
        passed if isinstance(passed, int) else 0,
        failed if isinstance(failed, int) else 0,
    )


def render_release_check_markdown(payload: dict[str, Any]) -> str:
    validate_release_check(payload)

    metadata = payload.get("release_metadata")
    metadata_payload = metadata if isinstance(metadata, dict) else None
    process = payload.get("release_process")
    process_payload = process if isinstance(process, dict) else None
    metadata_passed, metadata_failed = release_metadata_counts(metadata_payload)
    process_total, process_passed, process_failed = release_process_counts(process_payload)
    result = "passed" if payload.get("ok") else "failed"
    working_tree = "dirty" if payload.get("working_tree_dirty") else "clean"

    lines = [
        "# AgentLedger Release Readiness",
        "",
        f"- Result: {result}",
        f"- Status: {_text(payload.get('status'))}",
        f"- Version: {_text(payload.get('agentledger_version'))}",
        f"- Package version: {_text(payload.get('package_version'))}",
        f"- Branch: {_text(payload.get('branch'))}",
        f"- HEAD: {_text(payload.get('head'))}",
        f"- Wheel: {_text(payload.get('wheel'))}",
        f"- Working tree: {working_tree}",
        f"- Require clean git: {str(bool(payload.get('require_clean_git'))).lower()}",
        f"- Skip editable install: {str(bool(payload.get('skip_editable_install'))).lower()}",
        "",
        "## Release Metadata",
        "",
    ]

    if metadata_payload:
        lines.extend(
            [
                f"- Status: {_text(metadata_payload.get('status'))}",
                f"- Project: {_text(metadata_payload.get('project_name'))}",
                f"- Release label: {_text(metadata_payload.get('release_label'))}",
                f"- License: {_text(metadata_payload.get('license'))}",
                f"- Checks: {metadata_passed} passed, {metadata_failed} failed",
            ]
        )
        errors = [str(error) for error in metadata_payload.get("errors", []) if str(error).strip()]
        if errors:
            lines.append("")
            lines.append("Metadata errors:")
            for error in errors:
                lines.append(f"- {error}")
    else:
        lines.append("- Status: not available")
        lines.append("- Checks: 0 passed, 0 failed")

    lines.extend(["", "## Release Process", ""])
    if process_payload:
        lines.extend(
            [
                f"- Status: {_text(process_payload.get('status'))}",
                f"- Document: {_text(process_payload.get('doc'))}",
                f"- Command index schema: {_text(process_payload.get('index_schema_version'))}",
                f"- Checks: {process_passed} passed, {process_failed} failed, {process_total} total",
            ]
        )
        errors = [str(error) for error in process_payload.get("errors", []) if str(error).strip()]
        if errors:
            lines.append("")
            lines.append("Release-process errors:")
            for error in errors:
                lines.append(f"- {error}")
    else:
        lines.append("- Status: not available")
        lines.append("- Checks: 0 passed, 0 failed, 0 total")

    lines.extend(
        [
            "",
            "## Steps",
            "",
            "| Step | Status | Seconds | Error |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for step in payload["steps"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_cell(step.get("name")),
                    _escape_cell(step.get("status")),
                    _escape_cell(step.get("seconds")),
                    _escape_cell(step.get("error")),
                ]
            )
            + " |"
        )

    if payload.get("error"):
        lines.extend(["", "## Error", "", str(payload["error"])])

    return "\n".join(lines).rstrip() + "\n"


def load_release_check(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as error:
        raise ReleaseCheckSummaryError(f"Invalid JSON in {path}: {error}") from error
    return _as_mapping(payload, "release check summary")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render release-check JSON as a concise Markdown summary."
    )
    parser.add_argument("summary_json", type=Path, help="Path to agentledger-release-check.json.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Write Markdown to this file instead of stdout.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        payload = load_release_check(args.summary_json)
        markdown = render_release_check_markdown(payload)
    except (OSError, ReleaseCheckSummaryError) as error:
        print(f"release_check_summary.py: {error}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
