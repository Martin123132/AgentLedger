from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_report(run_dir: Path) -> dict[str, Any]:
    report_path = run_dir / "agentledger-report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Missing report file: {report_path}")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid report payload in {report_path}")
    return payload


def _parse_diff_stat_count(diff_stat: str) -> int | None:
    match = re.search(r"(\d+)\s+files?\s+changed", diff_stat)
    if match:
        return int(match.group(1))
    match_single = re.search(r"(\d+)\s+file changed", diff_stat)
    if match_single:
        return int(match_single.group(1))
    return None


def _status_entries(status_text: str) -> tuple[int, int]:
    if not status_text:
        return 0, 0
    tracked = 0
    untracked = 0
    for line in status_text.splitlines():
        if len(line) < 3:
            continue
        status = line[:2]
        if not status.strip():
            continue
        path = line[3:].strip()
        if not path:
            continue
        if status.startswith("??"):
            untracked += 1
        else:
            tracked += 1
    return tracked, untracked


def changed_file_count(report: dict[str, Any]) -> int:
    after = report.get("after") or {}
    diff_stat = str(after.get("diff_stat") or "").strip()
    tracked_from_diff = _parse_diff_stat_count(diff_stat)
    if tracked_from_diff is None:
        tracked_from_diff = 0
    diff_tracked = sum(1 for line in str(after.get("diff") or "").splitlines() if line.startswith("diff --git "))
    if diff_tracked > tracked_from_diff:
        tracked_from_diff = diff_tracked
    status_tracked, status_untracked = _status_entries(str(after.get("status") or ""))
    return max(tracked_from_diff, status_tracked) + status_untracked


def change_attribution(report: dict[str, Any]) -> dict[str, Any] | None:
    payload = report.get("change_attribution")
    return payload if isinstance(payload, dict) else None


def attributed_file_count(report: dict[str, Any]) -> int | None:
    attribution = change_attribution(report)
    if not attribution or attribution.get("available") is not True:
        return None
    changes = attribution.get("changed_during_run")
    if not isinstance(changes, dict):
        return None
    value = changes.get("changed_file_count")
    return value if isinstance(value, int) and value >= 0 else None


def _first_non_empty(payload: dict[str, Any] | None, keys: tuple[str, ...]) -> Any | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def artifact_status_counts(artifacts: list[dict[str, Any]]) -> tuple[int, int]:
    passed = 0
    warned = 0
    for artifact in artifacts:
        if artifact.get("ok"):
            passed += 1
        else:
            warned += 1
    return passed, warned


def _find_tokometer_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [artifact for artifact in artifacts if isinstance(artifact, dict) and artifact.get("name") == "tokometer_summary"]


def tokometer_summary(report: dict[str, Any]) -> str | None:
    artifacts = report.get("artifacts") or []
    tokos = _find_tokometer_artifacts([artifact for artifact in artifacts if isinstance(artifact, dict)])
    if not tokos:
        return None
    tok = tokos[-1]
    status = "ok" if tok.get("ok") else "warn"
    summary = str(tok.get("summary") or "").strip()
    path = tok.get("output_path")
    if not path:
        return f"{status}: {summary or 'no output path'}"
    output_path = Path(path)
    if not output_path.exists():
        return f"{status}: {summary or 'summary file missing'}"
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return f"{status}: {summary or 'summary file not readable'}"
    latest = payload.get("latest") if isinstance(payload, dict) else None
    latest_total = _first_non_empty(
        latest,
        ("total", "totalTokens", "activeTotal", "tokensTotal", "usageTotal", "totalUsage"),
    )
    latest_active = _first_non_empty(
        latest,
        ("active", "activeTokens", "activeTotal", "activeUsage", "tokensActive"),
    )
    if latest_total is None and latest_active is None:
        return f"{status}: {summary or 'latest usage unavailable'}"
    pieces = []
    if latest_total is not None:
        pieces.append(f"total={latest_total}")
    if latest_active is not None:
        pieces.append(f"active={latest_active}")
    return f"{status}: {'; '.join(pieces)}"


def report_command_text(report: dict[str, Any]) -> str:
    command = report.get("command")
    if not isinstance(command, dict):
        return "No command executed"
    parts = command.get("command") or []
    if isinstance(parts, list):
        return " ".join(str(item) for item in parts) if parts else "No command executed"
    return str(parts)


def integration_warnings(report: dict[str, Any]) -> list[str]:
    artifacts = report.get("artifacts") or []
    return [
        f"{artifact.get('name')}: {artifact.get('summary')}"
        for artifact in artifacts
        if isinstance(artifact, dict)
        and not artifact.get("ok")
        and (
            isinstance(artifact.get("name"), str)
            and (artifact["name"].startswith("repomori_") or artifact["name"] == "jester_diff")
        )
    ]


def command_exit_code(report: dict[str, Any]) -> int | None:
    command = report.get("command")
    if not isinstance(command, dict):
        return None
    value = command.get("exit_code")
    return int(value) if isinstance(value, int) else None


def command_test_framework(report: dict[str, Any]) -> str:
    command = report.get("command")
    if not isinstance(command, dict):
        return "n/a"
    return str(command.get("test_framework") or "n/a")


def command_exit_trend(old_code: int | None, new_code: int | None) -> str:
    if old_code is None or new_code is None:
        return "not comparable"
    if old_code == 0 and new_code == 0:
        return "unchanged"
    if old_code != 0 and new_code == 0:
        return "improved"
    if old_code == 0 and new_code != 0:
        return "regressed"
    return "still failing"
