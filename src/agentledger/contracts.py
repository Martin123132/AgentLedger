from __future__ import annotations

from typing import Any


CONTRACTS_SCHEMA = "agentledger.contracts.v1"
CONTRACTS_DOC = "docs/json-contracts.md"

JSON_CONTRACTS: list[dict[str, Any]] = [
    {
        "command": "doctor --json",
        "schema_version": "agentledger.doctor.v1",
        "purpose": "Check local AgentLedger setup readiness.",
        "stable_fields": ["status", "required_ok", "optional", "checks"],
        "exit_codes": {"0": "ready", "2": "blocked"},
    },
    {
        "command": "open-latest --format json",
        "schema_version": "agentledger.open_latest.v1",
        "purpose": "Locate the latest local evidence without parsing text output.",
        "stable_fields": [
            "ok",
            "repo",
            "out",
            "latest_run",
            "paths",
            "missing_reports",
            "errors",
        ],
        "exit_codes": {"0": "latest run resolved", "2": "latest run or report files missing"},
    },
    {
        "command": "history --format json",
        "schema_version": "agentledger.history.v1",
        "purpose": "List recent runs from an AgentLedger output directory.",
        "stable_fields": ["out", "runs"],
        "exit_codes": {"0": "history listed", "2": "invalid output directory or options"},
    },
    {
        "command": "inspect-report --format json <run-dir>",
        "schema_version": "agentledger.inspect_report.v1",
        "purpose": "Summarize one run report.",
        "stable_fields": [
            "run_dir",
            "command",
            "exit_code",
            "test_framework",
            "changed_files",
            "artifacts",
            "tokometer",
            "privacy_mode",
        ],
        "exit_codes": {"0": "report inspected", "2": "report missing or unreadable"},
    },
    {
        "command": "check --format json <run-dir>",
        "schema_version": "agentledger.check.v1",
        "purpose": "Evaluate a run report against review policy.",
        "stable_fields": [
            "status",
            "ok",
            "run_dir",
            "report",
            "summary",
            "rule_counts",
            "warning_rules",
            "blocking_rules",
            "rules",
            "policy",
        ],
        "exit_codes": {
            "0": "pass, or warn with warnings allowed",
            "1": "warn",
            "2": "block or invalid input",
        },
    },
    {
        "command": "review --format json",
        "schema_version": "agentledger.review.v1",
        "purpose": "Combine policy status with direct evidence paths.",
        "stable_fields": [
            "status",
            "ok",
            "summary",
            "run_dir",
            "command_exit_code",
            "paths",
            "check",
            "review_exit_code",
        ],
        "exit_codes": {
            "0": "pass, or warn with warnings allowed",
            "1": "warn",
            "2": "block or invalid input",
        },
    },
    {
        "command": "verify-bundle --format json <bundle.zip>",
        "schema_version": "agentledger.verify_bundle.v1",
        "purpose": "Validate a portable evidence bundle.",
        "stable_fields": [
            "ok",
            "bundle",
            "run_id",
            "manifest",
            "signature",
            "reports",
            "command",
            "changed_files",
            "artifacts",
            "errors",
        ],
        "exit_codes": {"0": "bundle valid", "2": "bundle missing, invalid, or verification failed"},
    },
    {
        "command": "compare --format json <old-run> <new-run>",
        "schema_version": "agentledger.compare.v1",
        "purpose": "Compare two captured runs.",
        "stable_fields": [
            "changed_files",
            "exit_code",
            "artifacts",
            "command",
            "tokometer",
            "test_framework",
            "privacy_mode",
        ],
        "exit_codes": {"0": "reports compared", "2": "one or both reports missing or unreadable"},
    },
    {
        "command": "contracts --format json",
        "schema_version": CONTRACTS_SCHEMA,
        "purpose": "List AgentLedger JSON command contracts.",
        "stable_fields": [
            "schema_version",
            "agentledger_version",
            "docs",
            "compatibility",
            "contracts",
        ],
        "exit_codes": {"0": "contracts listed"},
    },
]


def build_contracts_payload(agentledger_version: str) -> dict[str, Any]:
    return {
        "schema_version": CONTRACTS_SCHEMA,
        "agentledger_version": agentledger_version,
        "docs": CONTRACTS_DOC,
        "compatibility": {
            "stability": "alpha",
            "unknown_fields": "ignore",
            "breaking_changes": "schema_version changes when payload meaning or shape breaks compatibility",
        },
        "contracts": JSON_CONTRACTS,
    }


def format_contracts_text(agentledger_version: str) -> str:
    lines = [
        f"AgentLedger JSON contracts ({agentledger_version})",
        f"Schema: {CONTRACTS_SCHEMA}",
        f"Docs: {CONTRACTS_DOC}",
        "Commands:",
    ]
    for contract in JSON_CONTRACTS:
        lines.append(f"- {contract['command']}: {contract['schema_version']}")
    return "\n".join(lines)
