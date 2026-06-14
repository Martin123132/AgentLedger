from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .redaction import REDACTED
from .report_reader import (
    changed_file_count,
    command_exit_code,
    command_test_framework,
    load_report,
    report_command_text,
)


PASS = "pass"
WARN = "warn"
BLOCK = "block"


@dataclass(frozen=True)
class CheckPolicy:
    require_tests: bool = False
    dirty: str = WARN
    max_changed_files: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "require_tests": self.require_tests,
            "dirty": self.dirty,
            "max_changed_files": self.max_changed_files,
        }


def build_check(run_dir: Path, policy: CheckPolicy | None = None) -> dict[str, Any]:
    policy = policy or CheckPolicy()
    run_dir = run_dir.resolve()
    report_path = run_dir / "agentledger-report.json"
    try:
        report = load_report(run_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        return _result(
            run_dir,
            report_path,
            [
                _rule(
                    "report_loaded",
                    BLOCK,
                    f"Unable to read AgentLedger report: {exc}",
                )
            ],
        )

    rules = [_rule("report_loaded", PASS, f"Loaded report: {report_path}")]
    rules.extend(_schema_rules(report))
    rules.extend(_report_file_rules(run_dir))
    rules.extend(_command_rules(report))
    rules.extend(_test_evidence_rules(report, policy))
    rules.extend(_repo_state_rules(report, policy))
    rules.extend(_warning_rules(report))
    rules.extend(_artifact_rules(report))
    rules.extend(_redaction_rules(report, run_dir))

    payload = _result(run_dir, report_path, rules)
    payload.update(
        {
            "run_id": str(report.get("run_id") or run_dir.name),
            "command": report_command_text(report),
            "exit_code": command_exit_code(report),
            "changed_files": changed_file_count(report),
            "test_framework": command_test_framework(report),
            "privacy_mode": str(report.get("privacy_mode") or "standard"),
            "policy": policy.to_dict(),
        }
    )
    return payload


def format_check(result: dict[str, Any]) -> str:
    lines = [
        f"AgentLedger check: {result['status']}",
        f"Run: {result['run_dir']}",
        f"Report: {result['report']}",
    ]
    if "command" in result:
        lines.append(f"Command: {result['command']}")
        lines.append(f"Exit code: {result['exit_code'] if result['exit_code'] is not None else 'n/a'}")
        lines.append(f"Changed files: {result['changed_files']}")
        lines.append(f"Test framework: {result['test_framework']}")
        lines.append(f"Privacy mode: {result['privacy_mode']}")
    for rule in result["rules"]:
        lines.append(f"[{str(rule['status']).upper()}] {rule['id']}: {rule['message']}")
    return "\n".join(lines)


def check_exit_code(status: str, allow_warnings: bool = False) -> int:
    if status == BLOCK:
        return 2
    if status == WARN and not allow_warnings:
        return 1
    return 0


def _schema_rules(report: dict[str, Any]) -> list[dict[str, str]]:
    schema = report.get("schema_version")
    if schema != "agentledger.report.v1":
        return [_rule("schema_version", BLOCK, f"Unexpected report schema: {schema}")]
    return [_rule("schema_version", PASS, "Report schema is agentledger.report.v1.")]


def _report_file_rules(run_dir: Path) -> list[dict[str, str]]:
    missing = [
        str(run_dir / filename)
        for filename in ("agentledger-report.md", "agentledger-report.html")
        if not (run_dir / filename).exists()
    ]
    if missing:
        return [_rule("report_files", BLOCK, f"Missing expected report files: {', '.join(missing)}")]
    return [_rule("report_files", PASS, "Markdown and HTML reports are present.")]


def _command_rules(report: dict[str, Any]) -> list[dict[str, str]]:
    command = report.get("command")
    if not isinstance(command, dict):
        return [_rule("command_exit", WARN, "No command was captured; snapshot-only reports need human review.")]

    exit_code = command_exit_code(report)
    if exit_code == 0:
        return [_rule("command_exit", PASS, "Captured command exited 0.")]
    if exit_code is None:
        return [_rule("command_exit", BLOCK, "Captured command is missing an exit code.")]
    return [_rule("command_exit", BLOCK, f"Captured command failed with exit code {exit_code}.")]


def _test_evidence_rules(report: dict[str, Any], policy: CheckPolicy) -> list[dict[str, str]]:
    command = report.get("command")
    if not isinstance(command, dict):
        status = BLOCK if policy.require_tests else WARN
        return [_rule("test_evidence", status, "No command was captured, so test evidence could not be detected.")]
    if command.get("test_detected") is True:
        framework = command_test_framework(report)
        return [_rule("test_evidence", PASS, f"Verification command detected: {framework}.")]
    status = BLOCK if policy.require_tests else WARN
    return [_rule("test_evidence", status, "Command was not recognized as a test or verification command.")]


def _repo_state_rules(report: dict[str, Any], policy: CheckPolicy) -> list[dict[str, str]]:
    changed = changed_file_count(report)
    if policy.max_changed_files is not None and changed > policy.max_changed_files:
        return [
            _rule(
                "repo_state",
                BLOCK,
                f"Repository had {changed} changed files after the run; maximum is {policy.max_changed_files}.",
            )
        ]
    if changed:
        suffix = "file" if changed == 1 else "files"
        if policy.dirty == PASS:
            return [_rule("repo_state", PASS, f"Repository had {changed} changed {suffix} after the run; allowed by policy.")]
        if policy.dirty == BLOCK:
            return [_rule("repo_state", BLOCK, f"Repository had {changed} changed {suffix} after the run.")]
        return [_rule("repo_state", WARN, f"Repository had {changed} changed {suffix} after the run.")]
    return [_rule("repo_state", PASS, "Repository had no uncommitted changes after the run.")]


def _warning_rules(report: dict[str, Any]) -> list[dict[str, str]]:
    warnings = report.get("warnings") or []
    count = len([item for item in warnings if str(item).strip()])
    if count:
        suffix = "warning" if count == 1 else "warnings"
        return [_rule("report_warnings", WARN, f"Report contains {count} {suffix}.")]
    return [_rule("report_warnings", PASS, "Report contains no top-level warnings.")]


def _artifact_rules(report: dict[str, Any]) -> list[dict[str, str]]:
    artifacts = [artifact for artifact in report.get("artifacts") or [] if isinstance(artifact, dict)]
    failed = [artifact for artifact in artifacts if not artifact.get("ok")]
    blocking = [
        artifact
        for artifact in failed
        if artifact.get("name") == "jester_diff" and artifact.get("exit_code") is not None
    ]
    if blocking:
        names = ", ".join(str(artifact.get("name") or "unnamed") for artifact in blocking)
        return [_rule("artifact_status", BLOCK, f"Blocking artifact failures: {names}.")]
    if failed:
        names = ", ".join(str(artifact.get("name") or "unnamed") for artifact in failed)
        return [_rule("artifact_status", WARN, f"Non-blocking artifact warnings: {names}.")]
    return [_rule("artifact_status", PASS, "No artifact failures were recorded.")]


def _redaction_rules(report: dict[str, Any], run_dir: Path) -> list[dict[str, str]]:
    if _has_redaction_marker(report, run_dir):
        return [_rule("redaction", WARN, "Redaction markers are present; review evidence before sharing.")]
    return [_rule("redaction", PASS, "No redaction markers were found in the report or command transcript tails.")]


def _has_redaction_marker(report: dict[str, Any], run_dir: Path) -> bool:
    marker_prefixes = (REDACTED, "[REDACTED ")
    if any(marker in json.dumps(report, sort_keys=True) for marker in marker_prefixes):
        return True

    command = report.get("command")
    if not isinstance(command, dict):
        return False
    for key in ("stdout_path", "stderr_path"):
        value = command.get(key)
        if not value:
            continue
        path = Path(str(value))
        if not path.is_absolute():
            path = run_dir / path
        text = _read_text_prefix(path)
        if any(marker in text for marker in marker_prefixes):
            return True
    return False


def _read_text_prefix(path: Path, limit: int = 200_000) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def _result(run_dir: Path, report_path: Path, rules: list[dict[str, str]]) -> dict[str, Any]:
    status = _aggregate_status(rules)
    rule_counts = _rule_counts(rules)
    return {
        "schema_version": "agentledger.check.v1",
        "status": status,
        "ok": status == PASS,
        "run_dir": str(run_dir),
        "report": str(report_path),
        "summary": _summary(status, rule_counts),
        "rule_counts": rule_counts,
        "blocking_rules": _rules_with_status(rules, BLOCK),
        "warning_rules": _rules_with_status(rules, WARN),
        "rules": rules,
    }


def _aggregate_status(rules: list[dict[str, str]]) -> str:
    statuses = {rule["status"] for rule in rules}
    if BLOCK in statuses:
        return BLOCK
    if WARN in statuses:
        return WARN
    return PASS


def _rule_counts(rules: list[dict[str, str]]) -> dict[str, int]:
    return {
        PASS: sum(1 for rule in rules if rule["status"] == PASS),
        WARN: sum(1 for rule in rules if rule["status"] == WARN),
        BLOCK: sum(1 for rule in rules if rule["status"] == BLOCK),
        "total": len(rules),
    }


def _rules_with_status(rules: list[dict[str, str]], status: str) -> list[dict[str, str]]:
    return [
        {
            "id": rule["id"],
            "message": rule["message"],
        }
        for rule in rules
        if rule["status"] == status
    ]


def _summary(status: str, rule_counts: dict[str, int]) -> str:
    if status == PASS:
        return f"All {rule_counts['total']} checks passed."
    if status == WARN:
        suffix = "warning" if rule_counts[WARN] == 1 else "warnings"
        return f"{rule_counts[WARN]} {suffix}; review before accepting."
    suffix = "blocker" if rule_counts[BLOCK] == 1 else "blockers"
    return f"{rule_counts[BLOCK]} {suffix}; do not accept until resolved."


def _rule(rule_id: str, status: str, message: str) -> dict[str, str]:
    return {"id": rule_id, "status": status, "message": message}
