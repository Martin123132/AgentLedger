from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from .model import utc_now_iso
from .redaction import redact_text
from .report_reader import load_report


FEEDBACK_SCHEMA = "agentledger.feedback.v1"
FEEDBACK_SUMMARY_SCHEMA = "agentledger.feedback_summary.v1"
FEEDBACK_FILE_NAME = "alpha-feedback.jsonl"
FEEDBACK_CATEGORIES = ("friction", "bug", "docs", "privacy", "performance", "idea", "other")
FEEDBACK_SEVERITIES = ("low", "medium", "high")


class FeedbackError(ValueError):
    pass


def feedback_file(run_dir: Path) -> Path:
    return run_dir / FEEDBACK_FILE_NAME


def _validate_choice(name: str, value: str, choices: tuple[str, ...]) -> None:
    if value not in choices:
        joined = ", ".join(choices)
        raise FeedbackError(f"{name} must be one of: {joined}.")


def _load_run(run_dir: Path) -> dict[str, Any]:
    if not run_dir.exists():
        raise FeedbackError(f"Run directory not found: {run_dir}")
    try:
        return load_report(run_dir)
    except FileNotFoundError as exc:
        raise FeedbackError(f"Unable to read report in {run_dir}: {exc}") from exc
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise FeedbackError(f"Unable to read report in {run_dir}: {exc}") from exc


def build_feedback_entry(
    *,
    run_dir: Path,
    note: str,
    category: str,
    severity: str,
    source: str,
) -> dict[str, Any]:
    clean_note = note.strip()
    if not clean_note:
        raise FeedbackError("Feedback note must not be empty.")
    _validate_choice("category", category, FEEDBACK_CATEGORIES)
    _validate_choice("severity", severity, FEEDBACK_SEVERITIES)

    report = _load_run(run_dir)
    redacted_note = redact_text(clean_note)
    redacted_source = redact_text(source.strip() or "tester")
    return {
        "schema_version": FEEDBACK_SCHEMA,
        "id": uuid.uuid4().hex,
        "created_at": utc_now_iso(),
        "run_id": str(report.get("run_id") or run_dir.name),
        "run_dir": str(run_dir),
        "category": category,
        "severity": severity,
        "source": redacted_source,
        "note": redacted_note,
        "redacted": redacted_note != clean_note or redacted_source != (source.strip() or "tester"),
    }


def append_feedback(
    *,
    run_dir: Path,
    note: str,
    category: str,
    severity: str,
    source: str,
) -> tuple[Path, dict[str, Any]]:
    entry = build_feedback_entry(
        run_dir=run_dir,
        note=note,
        category=category,
        severity=severity,
        source=source,
    )
    path = feedback_file(run_dir)
    try:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    except OSError as exc:
        raise FeedbackError(f"Unable to write feedback file: {path}: {exc}") from exc
    return path, entry


def read_feedback(run_dir: Path) -> tuple[Path, list[dict[str, Any]]]:
    _load_run(run_dir)
    path = feedback_file(run_dir)
    if not path.exists():
        return path, []

    entries: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise FeedbackError(f"Unable to read feedback file: {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FeedbackError(f"Invalid feedback JSON at {path}:{line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise FeedbackError(f"Invalid feedback entry at {path}:{line_number}: expected object.")
        entries.append(item)
    return path, entries


def _feedback_run_dirs(out_root: Path) -> list[Path]:
    if not out_root.exists():
        raise FeedbackError(f"No AgentLedger output directory found: {out_root}")
    if not out_root.is_dir():
        raise FeedbackError(f"AgentLedger output path is not a directory: {out_root}")
    return sorted(
        [
            child
            for child in out_root.iterdir()
            if child.is_dir() and (child / "agentledger-report.json").exists()
        ],
        key=lambda path: path.name,
        reverse=True,
    )


def _count_values(entries: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        value = str(entry.get(field) or "unknown")
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def summarize_feedback(
    *,
    out_root: Path,
    limit: int,
    category: str | None = None,
    severity: str | None = None,
) -> dict[str, Any]:
    if limit <= 0:
        raise FeedbackError("--limit must be greater than zero.")
    if category is not None:
        _validate_choice("category", category, FEEDBACK_CATEGORIES)
    if severity is not None:
        _validate_choice("severity", severity, FEEDBACK_SEVERITIES)

    run_dirs = _feedback_run_dirs(out_root)
    errors: list[str] = []
    all_entries: list[dict[str, Any]] = []
    run_summaries: list[dict[str, Any]] = []

    for run_dir in run_dirs:
        try:
            path, entries = read_feedback(run_dir)
        except FeedbackError as exc:
            errors.append(str(exc))
            continue

        filtered = [
            entry
            for entry in entries
            if (category is None or entry.get("category") == category)
            and (severity is None or entry.get("severity") == severity)
        ]
        if path.exists() or filtered:
            run_summaries.append(
                {
                    "run_id": filtered[0].get("run_id") if filtered else run_dir.name,
                    "run_dir": str(run_dir),
                    "feedback_file": str(path),
                    "entry_count": len(filtered),
                }
            )
        all_entries.extend(filtered)

    all_entries.sort(
        key=lambda entry: (
            str(entry.get("created_at") or ""),
            str(entry.get("id") or ""),
        ),
        reverse=True,
    )
    returned_entries = all_entries[:limit]

    return {
        "schema_version": FEEDBACK_SUMMARY_SCHEMA,
        "ok": not errors,
        "out": str(out_root),
        "filters": {
            "category": category,
            "severity": severity,
            "limit": limit,
        },
        "total_entries": len(all_entries),
        "returned_entries": len(returned_entries),
        "run_count": len(run_dirs),
        "runs_with_feedback": sum(1 for item in run_summaries if item["entry_count"] > 0),
        "categories": _count_values(all_entries, "category"),
        "severities": _count_values(all_entries, "severity"),
        "runs": run_summaries,
        "entries": returned_entries,
        "errors": errors,
    }
