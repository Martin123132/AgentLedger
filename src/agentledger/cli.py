from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import platform
import re
import subprocess
import sys
import uuid
from zipfile import BadZipFile, ZipFile
from pathlib import Path

from . import __version__
from .bundle import (
    BUNDLE_SIGNATURE_SCHEMA,
    BundleError,
    find_bundle_signature_member,
    find_bundle_signature_members,
    sign_zip_bundle,
    validate_bundle_manifest,
    validate_bundle_signature,
    write_zip_bundle,
)
from .classify import detect_test_command
from .check import CheckPolicy, build_check, check_exit_code, format_check
from .config import AgentLedgerConfig, ConfigError, STARTER_CONFIG_TEXT, load_config
from .contracts import build_contracts_payload, format_contracts_text
from .doctor import doctor_json, format_doctor, run_doctor
from .export import write_html, write_json, write_markdown
from .feedback import (
    FEEDBACK_CATEGORIES,
    FEEDBACK_EXPORT_RESULT_SCHEMA,
    FEEDBACK_EXPORT_SCHEMA,
    FEEDBACK_SCHEMA,
    FEEDBACK_SUMMARY_SCHEMA,
    FEEDBACK_SEVERITIES,
    FeedbackError,
    append_feedback,
    read_feedback,
    summarize_feedback,
    write_feedback_export,
)
from .gittools import snapshot
from .integrations import read_tokometer_usage, run_jester_diff, run_repomori_snapshot
from .model import CommandResult, LedgerReport, utc_now_iso
from .process import run_capture, tail_text
from .redaction import redact_command, redact_text
from .report_reader import (
    artifact_status_counts,
    changed_file_count,
    command_exit_code,
    command_exit_trend,
    command_test_framework,
    integration_warnings,
    load_report,
    report_command_text,
    tokometer_summary,
)


PRIVACY_OMISSION = "[omitted by privacy-mode summary]"
DEFAULT_OUT = ".agentledger"
DEFAULT_PRIVACY_MODE = "standard"
STATUS_SCHEMA = "agentledger.status.v1"
ALPHA_GUIDE_SCHEMA = "agentledger.alpha_guide.v1"
ALPHA_SUMMARY_SCHEMA = "agentledger.alpha_summary.v1"
ALPHA_SUMMARY_FILENAME = "alpha-summary.json"
SIGNING_KEY_SCHEMA = "agentledger.signing_key.v1"
SIGN_BUNDLE_SCHEMA = "agentledger.sign_bundle.v1"
INSPECT_BUNDLE_SCHEMA = "agentledger.inspect_bundle.v1"
COMPARE_SCHEMA = "agentledger.compare.v1"
ALPHA_HANDOFF_SCHEMA = "agentledger.alpha_handoff.v1"
ALPHA_HANDOFF_MARKDOWN = "agentledger-alpha-handoff.md"
ALPHA_HANDOFF_JSON = "agentledger-alpha-handoff.json"
PACK_ALPHA_SCHEMA = "agentledger.pack_alpha.v1"
ALPHA_SUMMARY_WRITE_NEXT_ACTION = (
    "Choose a writable alpha summary path, then run agentledger alpha again."
)
ALPHA_SUMMARY_REQUIRED_FIELDS = {
    "schema_version",
    "ok",
    "summary_file",
    "started_at",
    "ended_at",
    "repo",
    "out",
    "latest_run",
    "bundle",
    "agentledger_version",
    "python_version",
    "git_version",
    "doctor",
    "status",
    "status_summary",
    "status_exit_code",
    "report_paths",
    "feedback",
    "next_actions",
    "errors",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentledger",
        description="Local-first black box recorder for AI coding-agent work.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command_name", required=True)

    contracts = sub.add_parser("contracts", help="List AgentLedger JSON command contracts.")
    contracts.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    run = sub.add_parser("run", help="Capture before/after repo state around a command.")
    run.add_argument("--repo", default=".", help="Target git repository.")
    run.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    run.add_argument("--out", default=None, help="Evidence output directory.")
    run.add_argument("--no-repomori", action="store_true", help="Skip RepoMori snapshot hooks.")
    run.add_argument("--no-jester", action="store_true", help="Skip Jester diff gate.")
    run.add_argument("--no-tokometer", action="store_true", help="Skip Tokometer path evidence.")
    run.add_argument("--no-zip", action="store_true", help="Skip zip bundle export.")
    run.add_argument(
        "--privacy-mode",
        choices=["standard", "summary"],
        default=None,
        help="Evidence detail level. summary omits command transcript content and full diffs.",
    )
    run.add_argument("task", nargs=argparse.REMAINDER, help="Command to run after --.")

    snap = sub.add_parser("snapshot", help="Capture repository state without running a command.")
    snap.add_argument("--repo", default=".", help="Target git repository.")
    snap.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    snap.add_argument("--out", default=None, help="Evidence output directory.")
    snap.add_argument("--no-repomori", action="store_true", help="Skip RepoMori snapshot hook.")
    snap.add_argument("--no-tokometer", action="store_true", help="Skip Tokometer path evidence.")
    snap.add_argument("--no-zip", action="store_true", help="Skip zip bundle export.")
    snap.add_argument(
        "--privacy-mode",
        choices=["standard", "summary"],
        default=None,
        help="Evidence detail level. summary omits full diffs from reports and bundles.",
    )

    doctor = sub.add_parser("doctor", help="Check local AgentLedger integration readiness.")
    doctor.add_argument("--repo", default=None, help="Optional target git repository to validate.")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable doctor report.")

    inspect = sub.add_parser("inspect-report", help="Print a concise summary of an existing run report folder.")
    inspect.add_argument("run_dir", help="Path to run directory.")
    inspect.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    latest = sub.add_parser("open-latest", help="Print latest report paths from a run output directory.")
    latest.add_argument("--repo", default=".", help="Target git repository for config lookup.")
    latest.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    latest.add_argument("--out", default=None, help="Evidence output directory.")
    latest.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    history = sub.add_parser("history", help="List recent AgentLedger runs from a run output directory.")
    history.add_argument("--repo", default=".", help="Target git repository for config lookup.")
    history.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    history.add_argument("--out", default=None, help="Evidence output directory.")
    history.add_argument("--limit", type=int, default=10, help="Maximum number of runs to show.")
    history.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    status = sub.add_parser("status", help="Show latest run policy, evidence, and feedback status.")
    status.add_argument("--repo", default=".", help="Target git repository for config/output lookup.")
    status.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    status.add_argument("--out", default=None, help="Evidence output directory.")
    status.add_argument("--feedback-limit", type=int, default=3, help="Recent feedback entries to inspect for counts.")
    status.add_argument("--allow-warnings", action="store_true", help="Return success for pass or warn statuses.")
    status.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    alpha_guide = sub.add_parser("alpha-guide", help="Show the first-run alpha review loop.")
    alpha_guide.add_argument("--repo", default=".", help="Target git repository for config/output lookup.")
    alpha_guide.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    alpha_guide.add_argument("--out", default=None, help="Evidence output directory.")
    alpha_guide.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    alpha = sub.add_parser("alpha", help="Run a cross-platform one-command alpha pass.")
    alpha.add_argument("--repo", default=".", help="Target git repository for config/output lookup.")
    alpha.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    alpha.add_argument("--out", default=None, help="Evidence output directory.")
    alpha.add_argument(
        "--json-output",
        default=None,
        help="Path to write alpha-summary.json. Defaults to <out>/alpha-summary.json.",
    )
    alpha.add_argument(
        "--privacy-mode",
        choices=["standard", "summary"],
        default="summary",
        help="Evidence detail level for the captured verification command.",
    )
    alpha.add_argument("--strict", action="store_true", help="Return nonzero when the latest status has warnings.")
    alpha.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    alpha.add_argument(
        "task",
        nargs=argparse.REMAINDER,
        help="Command to capture after --. Defaults to current Python -m pytest.",
    )

    alpha_summary = sub.add_parser("alpha-summary", help="Inspect one-command alpha summary JSON.")
    alpha_summary.add_argument("summary_file", nargs="?", help="Path to alpha-summary.json. Defaults to <out>/alpha-summary.json.")
    alpha_summary.add_argument("--repo", default=".", help="Target git repository for config/output lookup.")
    alpha_summary.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    alpha_summary.add_argument("--out", default=None, help="Evidence output directory.")
    alpha_summary.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    alpha_handoff = sub.add_parser("alpha-handoff", help="Write a reviewed alpha handoff packet.")
    alpha_handoff.add_argument("--repo", default=".", help="Target git repository for config/output lookup.")
    alpha_handoff.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    alpha_handoff.add_argument("--out", default=None, help="Evidence output directory.")
    alpha_handoff.add_argument("--output-dir", required=True, help="Directory to write the handoff Markdown and JSON files.")
    alpha_handoff.add_argument("--feedback-limit", type=int, default=20, help="Maximum feedback entries to include.")
    alpha_handoff.add_argument("--history-limit", type=int, default=5, help="Recent runs to include for review context.")
    alpha_handoff.add_argument("--strict", action="store_true", help="Return nonzero when the latest status has warnings.")
    alpha_handoff.add_argument(
        "--share-safe",
        "--redact-local-paths",
        action="store_true",
        dest="share_safe",
        help="Redact local absolute paths from the written handoff packet.",
    )
    alpha_handoff.add_argument("--format", choices=["text", "json"], default="text", help="Command output format.")

    pack_alpha = sub.add_parser("pack-alpha", help="Write and validate a share-safe alpha handoff packet.")
    pack_alpha.add_argument("--repo", default=".", help="Target git repository for config/output lookup.")
    pack_alpha.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    pack_alpha.add_argument("--out", default=None, help="Evidence output directory.")
    pack_alpha.add_argument("--output-dir", required=True, help="Directory to write the share-safe handoff packet.")
    pack_alpha.add_argument("--feedback-limit", type=int, default=20, help="Maximum feedback entries to include.")
    pack_alpha.add_argument("--history-limit", type=int, default=5, help="Recent runs to include for review context.")
    pack_alpha.add_argument("--strict", action="store_true", help="Return nonzero when the latest status has warnings.")
    pack_alpha.add_argument("--format", choices=["text", "json"], default="text", help="Command output format.")

    feedback = sub.add_parser("feedback", help="Record or list alpha feedback for a run.")
    feedback.add_argument("run_dir", nargs="?", help="Path to run directory. Defaults to latest run.")
    feedback.add_argument("--repo", default=".", help="Target git repository for config lookup.")
    feedback.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    feedback.add_argument("--out", default=None, help="Evidence output directory.")
    feedback.add_argument("--note", default=None, help="Feedback note to attach to the run.")
    feedback.add_argument("--category", choices=FEEDBACK_CATEGORIES, default="friction", help="Feedback category.")
    feedback.add_argument("--severity", choices=FEEDBACK_SEVERITIES, default="medium", help="Feedback severity.")
    feedback.add_argument("--source", default="tester", help="Short local label for who supplied the feedback.")
    feedback.add_argument("--list", action="store_true", dest="list_entries", help="List feedback for the run.")
    feedback.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    feedback_summary = sub.add_parser("feedback-summary", help="Summarize alpha feedback across runs.")
    feedback_summary.add_argument("--repo", default=".", help="Target git repository for config lookup.")
    feedback_summary.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    feedback_summary.add_argument("--out", default=None, help="Evidence output directory.")
    feedback_summary.add_argument("--limit", type=int, default=20, help="Maximum number of feedback entries to show.")
    feedback_summary.add_argument("--category", choices=FEEDBACK_CATEGORIES, default=None, help="Only include this feedback category.")
    feedback_summary.add_argument("--severity", choices=FEEDBACK_SEVERITIES, default=None, help="Only include this feedback severity.")
    feedback_summary.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    feedback_export = sub.add_parser("feedback-export", help="Write a reviewed shareable alpha feedback export.")
    feedback_export.add_argument("--repo", default=".", help="Target git repository for config lookup.")
    feedback_export.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    feedback_export.add_argument("--out", default=None, help="Evidence output directory.")
    feedback_export.add_argument("--output", required=True, help="Path to write the reviewed feedback export.")
    feedback_export.add_argument("--output-format", choices=["markdown", "json"], default="markdown", help="Export file format.")
    feedback_export.add_argument("--limit", type=int, default=50, help="Maximum number of feedback entries to export.")
    feedback_export.add_argument("--category", choices=FEEDBACK_CATEGORIES, default=None, help="Only include this feedback category.")
    feedback_export.add_argument("--severity", choices=FEEDBACK_SEVERITIES, default=None, help="Only include this feedback severity.")
    feedback_export.add_argument("--format", choices=["text", "json"], default="text", help="Command output format.")

    review = sub.add_parser("review", help="Summarize latest or selected run with policy status.")
    review.add_argument("run_dir", nargs="?", help="Path to run directory. Defaults to latest run.")
    review.add_argument("--repo", default=None, help="Target git repository for config/output lookup.")
    review.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    review.add_argument("--out", default=None, help="Evidence output directory.")
    review.add_argument("--format", choices=["text", "json", "markdown"], default="text", help="Output format.")
    review.add_argument("--output", default=None, help="Optional path to write the rendered review output.")
    review.add_argument(
        "--history-limit",
        type=int,
        default=3,
        help="Recent runs to include for context. Use 0 to hide history.",
    )
    review.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Return success for pass or warn statuses; block statuses still return 2.",
    )

    compare = sub.add_parser("compare", help="Compare two report folders side by side.")
    compare.add_argument("old_run_dir", help="Path to older run directory.")
    compare.add_argument("new_run_dir", help="Path to newer run directory.")
    compare.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    check = sub.add_parser("check", help="Evaluate a run report against default review policy.")
    check.add_argument("run_dir", help="Path to run directory.")
    check.add_argument("--repo", default=None, help="Target git repository for config lookup.")
    check.add_argument("--config", default=None, help="Path to .agentledger.toml policy config.")
    check.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    check.add_argument(
        "--allow-warnings",
        action="store_true",
        help="Return success for pass or warn statuses; block statuses still return 2.",
    )

    init_config = sub.add_parser("init-config", help="Write a starter .agentledger.toml policy config.")
    init_config.add_argument("--repo", default=".", help="Target repository or project directory.")
    init_config.add_argument("--config", default=None, help="Path to write config file.")
    init_config.add_argument("--force", action="store_true", help="Overwrite an existing config file.")

    signing_key = sub.add_parser("signing-key", help="Check shared signing-key file safety without printing the key.")
    signing_key.add_argument("--key-file", required=True, help="Text file containing the shared signing key.")
    signing_key.add_argument("--repo", default=".", help="Target git repository for ignore/tracking checks.")
    signing_key.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    inspect_bundle = sub.add_parser("inspect-bundle", help="Summarize a zip evidence bundle without verifying a signing key.")
    inspect_bundle.add_argument("bundle", help="Path to bundle zip file.")
    inspect_bundle.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    verify = sub.add_parser("verify-bundle", help="Validate a zip evidence bundle.")
    verify.add_argument("bundle", help="Path to bundle zip file.")
    verify.add_argument("--signature-key-file", default=None, help="Key file for HMAC-SHA256 bundle signature verification.")
    verify.add_argument(
        "--require-signature",
        action="store_true",
        help="Require and verify a bundle signature. Must be used with --signature-key-file.",
    )
    verify.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    sign = sub.add_parser("sign-bundle", help="Add or replace an HMAC-SHA256 bundle signature.")
    sign.add_argument("bundle", help="Path to bundle zip file.")
    sign.add_argument("--key-file", required=True, help="Text file containing the shared signing key.")
    sign.add_argument("--output", default=None, help="Optional output zip path. Defaults to updating the bundle in place.")
    sign.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    return parser


def _clean_task(task: list[str]) -> list[str]:
    if task and task[0] == "--":
        return task[1:]
    return task


def _handle_inspect_report(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        print(f"Run directory not found: {run_dir}")
        print("Expected a run folder containing agentledger-report.json.")
        return 2
    try:
        report = load_report(run_dir)
    except FileNotFoundError as exc:
        print(f"Unable to read report in {run_dir}: {exc}")
        print("Expected a run folder containing agentledger-report.json.")
        return 2
    except (ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"Unable to read report in {run_dir}: {exc}")
        return 2

    exit_code = command_exit_code(report)
    test_framework = command_test_framework(report)
    changed_files = changed_file_count(report)
    passed, warned = artifact_status_counts([artifact for artifact in report.get("artifacts", []) if isinstance(artifact, dict)])
    warnings = integration_warnings(report)
    tokometer = tokometer_summary(report)
    after = report.get("after") or {}

    if getattr(args, "format", "text") == "json":
        payload = {
            "schema_version": "agentledger.inspect_report.v1",
            "run_dir": str(run_dir),
            "command": report_command_text(report),
            "exit_code": exit_code if exit_code is not None else None,
            "test_framework": test_framework,
            "changed_files": changed_files,
            "artifacts": {"ok": passed, "warn": warned},
            "tokometer": tokometer,
            "privacy_mode": report.get("privacy_mode", "standard"),
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Report: {run_dir / 'agentledger-report.json'}")
    print(f"Command: {report_command_text(report)}")
    print(f"Exit code: {exit_code if exit_code is not None else 'n/a'}")
    print(f"Test framework: {test_framework}")
    print(f"Privacy mode: {report.get('privacy_mode', 'standard')}")
    print(f"Diff stat: {after.get('diff_stat') or 'no tracked diff'}")
    print(f"Changed files: {changed_files}")
    print(f"Artifacts: {passed} ok, {warned} warn")
    if tokometer:
        print(f"Tokometer: {tokometer}")
    for warning in warnings:
        print(f"Warning: {warning}")
    zip_path = run_dir.with_suffix(".zip")
    if zip_path.exists():
        print(f"Zip bundle: {zip_path}")
    return 0


def _find_bundle_member(names: list[str], target: str) -> str | None:
    for name in names:
        if name == target or name.endswith(f"/{target}"):
            return name
    return None


def _compare_reports_payload(old_report: dict, new_report: dict) -> dict:
    old_changed = changed_file_count(old_report)
    new_changed = changed_file_count(new_report)
    old_exit = command_exit_code(old_report)
    new_exit = command_exit_code(new_report)
    old_passed, old_warned = artifact_status_counts(
        [artifact for artifact in old_report.get("artifacts", []) if isinstance(artifact, dict)]
    )
    new_passed, new_warned = artifact_status_counts(
        [artifact for artifact in new_report.get("artifacts", []) if isinstance(artifact, dict)]
    )
    changed_delta = new_changed - old_changed
    changed_delta_text = f"+{changed_delta}" if changed_delta > 0 else str(changed_delta)
    old_tokometer = tokometer_summary(old_report)
    new_tokometer = tokometer_summary(new_report)
    return {
        "schema_version": COMPARE_SCHEMA,
        "changed_files": {
            "old": old_changed,
            "new": new_changed,
            "delta": changed_delta,
            "delta_text": changed_delta_text,
        },
        "exit_code": {
            "old": old_exit,
            "new": new_exit,
            "trend": command_exit_trend(old_exit, new_exit),
        },
        "artifacts": {
            "old": {"ok": old_passed, "warn": old_warned},
            "new": {"ok": new_passed, "warn": new_warned},
        },
        "command": {
            "old": report_command_text(old_report),
            "new": report_command_text(new_report),
        },
        "tokometer": {
            "old": old_tokometer,
            "new": new_tokometer,
        },
        "test_framework": {
            "old": command_test_framework(old_report),
            "new": command_test_framework(new_report),
        },
        "privacy_mode": {
            "old": str(old_report.get("privacy_mode") or "standard"),
            "new": str(new_report.get("privacy_mode") or "standard"),
        },
    }


def _handle_compare(args: argparse.Namespace) -> int:
    old_dir = Path(args.old_run_dir).resolve()
    new_dir = Path(args.new_run_dir).resolve()
    try:
        old_report = load_report(old_dir)
        new_report = load_report(new_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"Unable to read report: {exc}")
        return 2

    payload = _compare_reports_payload(old_report, new_report)

    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Comparing reports:")
    print(f"Old: {old_dir}")
    print(f"New: {new_dir}")
    print(f"Old command: {payload['command']['old']}")
    print(f"New command: {payload['command']['new']}")
    print(
        "Changed files: "
        f"{payload['changed_files']['old']} -> {payload['changed_files']['new']} "
        f"({payload['changed_files']['delta_text']})"
    )
    print(
        "Exit code: "
        f"{payload['exit_code']['old'] if payload['exit_code']['old'] is not None else 'n/a'} -> "
        f"{payload['exit_code']['new'] if payload['exit_code']['new'] is not None else 'n/a'} "
        f"({payload['exit_code']['trend']})"
    )
    print(
        f"Artifacts: {payload['artifacts']['old']['ok']} ok/{payload['artifacts']['old']['warn']} warn -> "
        f"{payload['artifacts']['new']['ok']} ok/{payload['artifacts']['new']['warn']} warn"
    )
    if payload["tokometer"]["old"] or payload["tokometer"]["new"]:
        print(f"Tokometer: {payload['tokometer']['old'] or 'n/a'} -> {payload['tokometer']['new'] or 'n/a'}")
    print(f"Test framework: {payload['test_framework']['old']} -> {payload['test_framework']['new']}")
    print(f"Privacy mode: {payload['privacy_mode']['old']} -> {payload['privacy_mode']['new']}")
    return 0


def _bundle_manifest_summary(member: str | None, manifest: dict) -> dict[str, object]:
    return {
        "member": member,
        "schema_version": manifest.get("schema_version"),
        "digest_algorithm": manifest.get("digest_algorithm"),
        "file_count": manifest.get("file_count"),
        "run_id": manifest.get("run_id"),
    }


def _bundle_signature_inspection(archive: ZipFile, names: list[str]) -> tuple[dict[str, object], list[str]]:
    non_directory_names = [name for name in names if not name.endswith("/")]
    signature_members = find_bundle_signature_members(non_directory_names)
    summary: dict[str, object] = {
        "member": None,
        "status": "not_present",
        "verified": False,
        "schema_version": None,
        "algorithm": None,
        "signed_member": None,
        "signed_sha256": None,
    }
    if not signature_members:
        return summary, []
    if len(signature_members) > 1:
        return (
            {
                **summary,
                "status": "multiple",
                "members": sorted(signature_members),
            },
            [f"Multiple bundle signature files found: {', '.join(sorted(signature_members))}"],
        )

    signature_member = signature_members[0]
    summary["member"] = signature_member
    summary["status"] = "present_unverified"
    try:
        signature = json.loads(archive.read(signature_member).decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {**summary, "status": "invalid"}, [f"Invalid JSON in {signature_member}"]
    if not isinstance(signature, dict):
        return {**summary, "status": "invalid"}, [f"Bundle signature payload is not a JSON object: {signature_member}"]

    summary.update(
        {
            "schema_version": signature.get("schema_version"),
            "algorithm": signature.get("algorithm"),
            "signed_member": signature.get("signed_member"),
            "signed_sha256": signature.get("signed_sha256"),
        }
    )
    errors = []
    if signature.get("schema_version") != BUNDLE_SIGNATURE_SCHEMA:
        errors.append(f"Unexpected bundle signature schema: {signature.get('schema_version')}")
    if signature.get("algorithm") != "hmac-sha256":
        errors.append(f"Unexpected bundle signature algorithm: {signature.get('algorithm')}")
    signed_member = signature.get("signed_member")
    if not isinstance(signed_member, str) or not signed_member.strip():
        errors.append("Bundle signature is missing signed_member.")
    elif signed_member not in non_directory_names:
        errors.append(f"Signed bundle member not found: {signed_member}")
    signed_sha = signature.get("signed_sha256")
    if not isinstance(signed_sha, str) or not signed_sha:
        errors.append("Bundle signature is missing signed_sha256.")
    elif isinstance(signed_member, str) and signed_member in non_directory_names:
        expected_sha = hashlib.sha256(archive.read(signed_member)).hexdigest()
        if signed_sha != expected_sha:
            errors.append(f"Signed manifest digest mismatch for {signed_member}.")
    raw_signature = signature.get("signature")
    if not isinstance(raw_signature, str) or not raw_signature:
        errors.append("Bundle signature is missing signature.")
    if errors:
        summary["status"] = "invalid"
    return summary, errors


def _bundle_review_summary(
    report: dict | None,
    *,
    manifest_errors: list[str],
    signature_errors: list[str],
    missing_reports: list[str],
    report_errors: list[str],
) -> dict[str, object]:
    blockers = [*manifest_errors, *missing_reports, *report_errors]
    warnings = list(signature_errors)
    if report is None:
        return _bundle_review_payload(
            report=None,
            blockers=blockers or ["Missing or unreadable bundle report."],
            warnings=warnings,
        )

    if report.get("schema_version") != "agentledger.report.v1":
        blockers.append(f"Unexpected report schema: {report.get('schema_version')}")

    command = report.get("command")
    exit_code = command_exit_code(report)
    if not isinstance(command, dict):
        warnings.append("No command was captured; snapshot-only reports need human review.")
    elif exit_code == 0:
        pass
    elif exit_code is None:
        blockers.append("Captured command is missing an exit code.")
    else:
        blockers.append(f"Captured command failed with exit code {exit_code}.")

    if isinstance(command, dict):
        if command.get("test_detected") is not True:
            warnings.append("Command was not recognized as a test or verification command.")
    else:
        warnings.append("No command was captured, so test evidence could not be detected.")

    changed = changed_file_count(report)
    if changed:
        suffix = "file" if changed == 1 else "files"
        warnings.append(f"Repository had {changed} changed {suffix} after the run.")

    report_warnings = [str(item).strip() for item in report.get("warnings") or [] if str(item).strip()]
    if report_warnings:
        suffix = "warning" if len(report_warnings) == 1 else "warnings"
        warnings.append(f"Report contains {len(report_warnings)} {suffix}.")

    artifacts = [artifact for artifact in report.get("artifacts") or [] if isinstance(artifact, dict)]
    failed_artifacts = [artifact for artifact in artifacts if not artifact.get("ok")]
    blocking_artifacts = [
        artifact
        for artifact in failed_artifacts
        if artifact.get("name") == "jester_diff" and artifact.get("exit_code") is not None
    ]
    if blocking_artifacts:
        names = ", ".join(str(artifact.get("name") or "unnamed") for artifact in blocking_artifacts)
        blockers.append(f"Blocking artifact failures: {names}.")
    elif failed_artifacts:
        names = ", ".join(str(artifact.get("name") or "unnamed") for artifact in failed_artifacts)
        warnings.append(f"Non-blocking artifact warnings: {names}.")

    return _bundle_review_payload(report=report, blockers=blockers, warnings=warnings)


def _bundle_review_payload(report: dict | None, blockers: list[str], warnings: list[str]) -> dict[str, object]:
    status = "block" if blockers else "warn" if warnings else "pass"
    if status == "block":
        suffix = "blocker" if len(blockers) == 1 else "blockers"
        summary = f"{len(blockers)} {suffix}; do not accept until resolved."
    elif status == "warn":
        suffix = "warning" if len(warnings) == 1 else "warnings"
        summary = f"{len(warnings)} {suffix}; review before accepting."
    else:
        summary = "Bundle report looks ready for human review."

    artifacts = []
    if report is not None:
        artifacts = [artifact for artifact in report.get("artifacts") or [] if isinstance(artifact, dict)]
    passed, warned = artifact_status_counts(artifacts)
    return {
        "status": status,
        "ok": status == "pass",
        "summary": summary,
        "blockers": blockers,
        "warnings": warnings,
        "run_id": report.get("run_id") if report is not None else None,
        "command": report_command_text(report) if report is not None else None,
        "exit_code": command_exit_code(report) if report is not None else None,
        "changed_files": changed_file_count(report) if report is not None else None,
        "test_framework": command_test_framework(report) if report is not None else None,
        "privacy_mode": str(report.get("privacy_mode") or "standard") if report is not None else None,
        "artifacts": {"ok": passed, "warn": warned},
    }


def _inspect_bundle_next_actions(review: dict[str, object], signature: dict[str, object]) -> list[str]:
    actions = ["Run agentledger verify-bundle on the bundle before sharing or archiving it."]
    if signature.get("status") == "present_unverified":
        actions.append("Pass --signature-key-file to verify-bundle if you have the shared signing key.")
    elif signature.get("status") in {"invalid", "multiple"}:
        actions.append("Investigate signature metadata before trusting the bundle.")
    elif signature.get("status") == "not_present":
        actions.append("Treat unsigned bundles as local evidence unless a reviewer explicitly accepts them.")

    if review.get("status") == "block":
        actions.append("Do not accept the bundle until blockers are fixed and a new bundle is produced.")
    elif review.get("status") == "warn":
        actions.append("Read the Markdown or HTML report and review warnings before accepting the work.")
    else:
        actions.append("Read the Markdown or HTML report before accepting the work.")
    actions.append("Do not commit .agentledger folders, zip bundles, signing keys, or sensitive evidence.")
    return actions


def _handle_inspect_bundle(args: argparse.Namespace) -> int:
    zip_path = Path(args.bundle).resolve()
    output_format = getattr(args, "format", "text")

    def emit(payload: dict[str, object], exit_code: int) -> int:
        if output_format == "json":
            print(json.dumps(payload, indent=2))
        else:
            _print_inspect_bundle(payload)
        return exit_code

    if not zip_path.exists():
        review = _bundle_review_summary(
            None,
            manifest_errors=[],
            signature_errors=[],
            missing_reports=[],
            report_errors=[f"Bundle not found: {zip_path}"],
        )
        payload = {
            "schema_version": INSPECT_BUNDLE_SCHEMA,
            "ok": False,
            "bundle": str(zip_path),
            "readable": False,
            "manifest": _bundle_manifest_summary(None, {}),
            "signature": {"member": None, "status": "not_present", "verified": False},
            "reports": {"json": None, "markdown": None, "html": None, "missing": []},
            "review": review,
            "errors": review["blockers"],
            "next_actions": _inspect_bundle_next_actions(review, {"status": "not_present"}),
        }
        return emit(payload, 2)

    try:
        with ZipFile(zip_path, "r") as archive:
            members = archive.namelist()
            manifest_member, manifest, manifest_errors = validate_bundle_manifest(archive)
            signature_payload, signature_errors = _bundle_signature_inspection(archive, members)
            report_member = _find_bundle_member(members, "agentledger-report.json")
            markdown_member = _find_bundle_member(members, "agentledger-report.md")
            html_member = _find_bundle_member(members, "agentledger-report.html")
            missing_reports = []
            if report_member is None:
                missing_reports.append("Missing JSON report in bundle.")
            if markdown_member is None:
                missing_reports.append("Missing markdown report in bundle.")
            if html_member is None:
                missing_reports.append("Missing HTML report in bundle.")

            report_errors = []
            report_payload = None
            if report_member is not None:
                try:
                    report_payload = json.loads(archive.read(report_member).decode("utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    report_errors.append(f"Invalid JSON in {report_member}")
                else:
                    if not isinstance(report_payload, dict):
                        report_errors.append(f"Bundle report payload is not a JSON object: {report_member}")
                        report_payload = None
    except (OSError, BadZipFile):
        review = _bundle_review_summary(
            None,
            manifest_errors=[],
            signature_errors=[],
            missing_reports=[],
            report_errors=[f"Unable to open zip file: {zip_path}"],
        )
        payload = {
            "schema_version": INSPECT_BUNDLE_SCHEMA,
            "ok": False,
            "bundle": str(zip_path),
            "readable": False,
            "manifest": _bundle_manifest_summary(None, {}),
            "signature": {"member": None, "status": "not_present", "verified": False},
            "reports": {"json": None, "markdown": None, "html": None, "missing": []},
            "review": review,
            "errors": review["blockers"],
            "next_actions": _inspect_bundle_next_actions(review, {"status": "not_present"}),
        }
        return emit(payload, 2)

    manifest_payload = _bundle_manifest_summary(manifest_member, manifest)
    manifest_payload["valid"] = not manifest_errors
    manifest_payload["errors"] = manifest_errors
    review = _bundle_review_summary(
        report_payload,
        manifest_errors=manifest_errors,
        signature_errors=signature_errors,
        missing_reports=missing_reports,
        report_errors=report_errors,
    )
    reports = {
        "json": report_member,
        "markdown": markdown_member,
        "html": html_member,
        "missing": missing_reports,
    }
    payload = {
        "schema_version": INSPECT_BUNDLE_SCHEMA,
        "ok": review["ok"],
        "bundle": str(zip_path),
        "readable": True,
        "manifest": manifest_payload,
        "signature": signature_payload,
        "reports": reports,
        "review": review,
        "errors": review["blockers"],
        "next_actions": _inspect_bundle_next_actions(review, signature_payload),
    }
    return emit(payload, 2 if report_payload is None else 0)


def _print_inspect_bundle(payload: dict[str, object]) -> None:
    review = payload["review"] if isinstance(payload.get("review"), dict) else {}
    manifest = payload["manifest"] if isinstance(payload.get("manifest"), dict) else {}
    signature = payload["signature"] if isinstance(payload.get("signature"), dict) else {}
    reports = payload["reports"] if isinstance(payload.get("reports"), dict) else {}
    print(f"AgentLedger bundle inspection: {review.get('status', 'block')}")
    print(f"Summary: {review.get('summary', 'Bundle could not be inspected.')}")
    print(f"Bundle: {payload.get('bundle')}")
    print(f"Readable: {'yes' if payload.get('readable') else 'no'}")
    print(f"Run ID: {review.get('run_id') or manifest.get('run_id') or 'n/a'}")
    print(f"Manifest: {manifest.get('member') or 'missing'}")
    print(f"Files listed: {manifest.get('file_count') if manifest.get('file_count') is not None else 'n/a'}")
    print(f"Signature: {signature.get('status') or 'not_present'}")
    if signature.get("member"):
        print(f"Signature member: {signature['member']}")
    print(f"JSON report: {reports.get('json') or 'missing'}")
    print(f"Markdown report: {reports.get('markdown') or 'missing'}")
    print(f"HTML report: {reports.get('html') or 'missing'}")
    if review.get("command") is not None:
        print(f"Command: {review['command']}")
        print(f"Exit code: {review['exit_code'] if review.get('exit_code') is not None else 'n/a'}")
        print(f"Changed files: {review.get('changed_files')}")
        print(f"Test framework: {review.get('test_framework')}")
        print(f"Privacy mode: {review.get('privacy_mode')}")
        artifacts = review.get("artifacts") if isinstance(review.get("artifacts"), dict) else {}
        print(f"Artifacts: {artifacts.get('ok', 0)} ok, {artifacts.get('warn', 0)} warn")
    blockers = review.get("blockers") if isinstance(review.get("blockers"), list) else []
    warnings = review.get("warnings") if isinstance(review.get("warnings"), list) else []
    if blockers:
        print("Blockers:")
        for blocker in blockers:
            print(f"- {blocker}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    print("Next:")
    for action in next_actions:
        print(f"- {action}")


def _handle_verify_bundle(args: argparse.Namespace) -> int:
    zip_path = Path(args.bundle).resolve()
    output_format = getattr(args, "format", "text")
    signature_payload: dict[str, object] = {
        "required": bool(args.require_signature),
        "member": None,
        "status": "not_present",
        "verified": False,
    }

    def fail(messages: str | list[str], **extra: object) -> int:
        errors = [messages] if isinstance(messages, str) else messages
        if output_format == "json":
            payload: dict[str, object] = {
                "schema_version": "agentledger.verify_bundle.v1",
                "ok": False,
                "bundle": str(zip_path),
                "errors": errors,
            }
            payload.update(extra)
            print(json.dumps(payload, indent=2))
        else:
            for message in errors:
                print(message)
        return 2

    if not zip_path.exists():
        return fail(f"Bundle not found: {zip_path}")
    if args.require_signature and args.signature_key_file is None:
        return fail("--require-signature requires --signature-key-file.", signature=signature_payload)
    signature_key = None
    if args.signature_key_file is not None:
        try:
            signature_key = _read_signature_key(Path(args.signature_key_file))
        except BundleError as exc:
            return fail(f"Signature key error: {exc}", signature=signature_payload)

    missing_members = []
    signature_status = "Signature: not present"
    signature_errors: list[str] = []

    try:
        with ZipFile(zip_path, "r") as archive:
            members = archive.namelist()
            manifest_member, manifest, manifest_errors = validate_bundle_manifest(archive)
            signature_member = find_bundle_signature_member(members)
            if signature_key is not None:
                signature_member, _signature, signature_errors = validate_bundle_signature(archive, signature_key)
                if signature_member is not None:
                    signature_payload["member"] = signature_member
                    signature_payload["status"] = "invalid"
                if not signature_errors and signature_member is not None:
                    signature_payload["status"] = "verified"
                    signature_payload["verified"] = True
                    signature_status = f"Signature: {signature_member} verified"
            elif signature_member is not None:
                signature_payload["member"] = signature_member
                signature_payload["status"] = "present_unverified"
                signature_status = f"Signature: {signature_member} present (not verified; pass --signature-key-file to verify)"
            report_member = _find_bundle_member(members, "agentledger-report.json")
            if report_member is None:
                return fail(
                    f"Missing agentledger-report.json in {zip_path}",
                    manifest=_bundle_manifest_summary(manifest_member, manifest),
                    signature=signature_payload,
                )
            markdown_member = _find_bundle_member(members, "agentledger-report.md")
            html_member = _find_bundle_member(members, "agentledger-report.html")
            if markdown_member is None:
                missing_members.append("Missing markdown report in bundle.")
            if html_member is None:
                missing_members.append("Missing HTML report in bundle.")
            try:
                payload = json.loads(archive.read(report_member).decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                return fail(
                    f"Invalid JSON in {report_member}",
                    manifest=_bundle_manifest_summary(manifest_member, manifest),
                    signature=signature_payload,
                    reports={"json": report_member, "markdown": markdown_member, "html": html_member},
                )
            if not isinstance(payload, dict):
                return fail(
                    "Bundle report payload is not a JSON object",
                    manifest=_bundle_manifest_summary(manifest_member, manifest),
                    signature=signature_payload,
                    reports={"json": report_member, "markdown": markdown_member, "html": html_member},
                )
            if payload.get("schema_version") != "agentledger.report.v1":
                return fail(
                    f"Unexpected report schema: {payload.get('schema_version')}",
                    manifest=_bundle_manifest_summary(manifest_member, manifest),
                    signature=signature_payload,
                    reports={"json": report_member, "markdown": markdown_member, "html": html_member},
                )
    except (OSError, BadZipFile):
        return fail(f"Unable to open zip file: {zip_path}", signature=signature_payload)

    problems = missing_members + manifest_errors + signature_errors
    if problems:
        return fail(
            problems,
            manifest=_bundle_manifest_summary(manifest_member, manifest),
            signature=signature_payload,
            reports={"json": report_member, "markdown": markdown_member, "html": html_member},
        )

    changed = changed_file_count(payload)
    passed, warned = artifact_status_counts([artifact for artifact in payload.get("artifacts", []) if isinstance(artifact, dict)])
    if output_format == "json":
        print(
            json.dumps(
                {
                    "schema_version": "agentledger.verify_bundle.v1",
                    "ok": True,
                    "bundle": str(zip_path),
                    "run_id": payload.get("run_id"),
                    "manifest": _bundle_manifest_summary(manifest_member, manifest),
                    "signature": signature_payload,
                    "reports": {"json": report_member, "markdown": markdown_member, "html": html_member},
                    "command": report_command_text(payload),
                    "changed_files": changed,
                    "artifacts": {"ok": passed, "warn": warned},
                    "errors": [],
                },
                indent=2,
            )
        )
        return 0
    print(f"Bundle OK: {zip_path}")
    print(f"Run ID: {payload.get('run_id', '(missing run_id)')}")
    print(f"Manifest: {manifest_member}")
    print(f"Files checked: {manifest.get('file_count', 'n/a')}")
    print(signature_status)
    print(f"Report: {report_member}")
    print(f"Markdown: {markdown_member}")
    print(f"HTML: {html_member}")
    print(f"Command: {report_command_text(payload)}")
    print(f"Changed files: {changed}")
    print(f"Artifacts: {passed} ok, {warned} warn")
    return 0


def _handle_sign_bundle(args: argparse.Namespace) -> int:
    bundle_path = Path(args.bundle).resolve()
    output_format = getattr(args, "format", "text")

    def fail(message: str) -> int:
        if output_format == "json":
            print(
                json.dumps(
                    {
                        "schema_version": SIGN_BUNDLE_SCHEMA,
                        "ok": False,
                        "bundle": str(bundle_path),
                        "signed_bundle": str(Path(args.output).resolve()) if args.output else str(bundle_path),
                        "signature": None,
                        "errors": [message],
                    },
                    indent=2,
                )
            )
        else:
            print(f"Unable to sign bundle: {message}")
        return 2

    try:
        key = _read_signature_key(Path(args.key_file))
        output = Path(args.output).resolve() if args.output else None
        signed_path, signature_member, signature = sign_zip_bundle(bundle_path, key, output)
    except BundleError as exc:
        return fail(str(exc))
    except OSError as exc:
        return fail(str(exc))
    if output_format == "json":
        print(
            json.dumps(
                {
                    "schema_version": SIGN_BUNDLE_SCHEMA,
                    "ok": True,
                    "bundle": str(bundle_path),
                    "signed_bundle": str(signed_path),
                    "signature": {
                        "member": signature_member,
                        "schema_version": signature.get("schema_version"),
                        "algorithm": signature.get("algorithm"),
                        "signed_member": signature.get("signed_member"),
                        "signed_sha256": signature.get("signed_sha256"),
                    },
                    "errors": [],
                },
                indent=2,
            )
        )
        return 0
    print(f"Signed bundle: {signed_path}")
    print(f"Signature: {signature_member}")
    print(f"Signed manifest: {signature['signed_member']}")
    print(f"Algorithm: {signature['algorithm']}")
    return 0


def _read_signature_key(path: Path) -> bytes:
    if not path.exists():
        raise BundleError(f"Key file not found: {path}")
    if not path.is_file():
        raise BundleError(f"Key path is not a file: {path}")
    key = path.read_bytes().strip()
    if not key:
        raise BundleError(f"Key file is empty: {path}")
    return key


def _git_root(repo: Path) -> tuple[Path | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--show-toplevel"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return None, "git was not found on PATH."
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        return None, detail or f"Not a git repository: {repo}"
    root = result.stdout.strip()
    if not root:
        return None, f"Git did not report a repository root for: {repo}"
    return Path(root).resolve(), None


def _relative_to(path: Path, root: Path) -> Path | None:
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def _git_boolean_check(repo_root: Path, args: list[str], expected_false: int = 1) -> tuple[bool | None, str | None]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except FileNotFoundError:
        return None, "git was not found on PATH."
    if result.returncode == 0:
        return True, None
    if result.returncode == expected_false:
        return False, None
    detail = (result.stderr or result.stdout).strip()
    return None, detail or f"git {' '.join(args)} failed with exit code {result.returncode}."


def _signing_key_next_actions(ok: bool, inside_repo: bool, ignored_by_git: bool | None, tracked_by_git: bool | None) -> list[str]:
    if not ok:
        actions = ["Fix the reported signing-key issue, then run agentledger signing-key again."]
        if inside_repo and ignored_by_git is not True:
            actions.append("Add a local ignore rule such as .agentledger-signing-key* before signing bundles.")
        if tracked_by_git:
            actions.append("Remove the key from git history and rotate it before using it again.")
        return actions
    actions = [
        "Use this key with agentledger sign-bundle --key-file when signing evidence bundles.",
        "Keep the signing key private and rotate it if it was shared too widely.",
    ]
    if inside_repo:
        actions.append("Keep the key covered by .gitignore and never commit it.")
    return actions


def _handle_signing_key(args: argparse.Namespace) -> int:
    key_path = Path(args.key_file).resolve()
    repo = Path(args.repo).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    key_size: int | None = None
    empty: bool | None = None
    exists = key_path.exists()
    is_file = key_path.is_file() if exists else False

    if not exists:
        errors.append(f"Key file not found: {key_path}")
    elif not is_file:
        errors.append(f"Key path is not a file: {key_path}")
    else:
        try:
            key = key_path.read_bytes().strip()
        except OSError as exc:
            errors.append(f"Unable to read key file: {exc}")
        else:
            key_size = len(key)
            empty = key_size == 0
            if empty:
                errors.append(f"Key file is empty: {key_path}")
            elif key_size < 32:
                warnings.append("Signing key is shorter than 32 bytes; use a longer random key for production signing.")

    git_root, git_error = _git_root(repo)
    if git_error:
        warnings.append(f"Unable to check git ignore/tracking status: {git_error}")

    inside_repo = False
    ignored_by_git: bool | None = None
    tracked_by_git: bool | None = None
    if git_root is not None:
        relative_key = _relative_to(key_path, git_root)
        inside_repo = relative_key is not None
        if inside_repo and relative_key is not None:
            git_key = relative_key.as_posix()
            ignored_by_git, ignore_error = _git_boolean_check(git_root, ["check-ignore", "-q", "--", git_key])
            tracked_by_git, tracked_error = _git_boolean_check(
                git_root,
                ["ls-files", "--error-unmatch", "--", git_key],
            )
            if ignore_error:
                errors.append(f"Unable to check whether key is ignored by git: {ignore_error}")
            if tracked_error:
                errors.append(f"Unable to check whether key is tracked by git: {tracked_error}")
            if tracked_by_git:
                errors.append(f"Signing key is tracked by git: {key_path}")
            if ignored_by_git is not True:
                errors.append(f"Signing key is inside the repo but is not ignored by git: {key_path}")

    ok = not errors
    payload = {
        "schema_version": SIGNING_KEY_SCHEMA,
        "ok": ok,
        "key_file": str(key_path),
        "repo": str(repo),
        "git_root": str(git_root) if git_root is not None else None,
        "exists": exists,
        "file": is_file,
        "size_bytes": key_size,
        "empty": empty,
        "inside_repo": inside_repo,
        "ignored_by_git": ignored_by_git,
        "tracked_by_git": tracked_by_git,
        "warnings": warnings,
        "errors": errors,
        "next_actions": _signing_key_next_actions(ok, inside_repo, ignored_by_git, tracked_by_git),
    }
    if args.format == "json":
        print(json.dumps(payload, indent=2))
        return 0 if ok else 2

    print(f"AgentLedger signing key: {'ready' if ok else 'blocked'}")
    print(f"Key file: {key_path}")
    print(f"Repo: {repo}")
    print(f"Git root: {git_root if git_root is not None else 'not checked'}")
    print(f"Exists: {'yes' if exists else 'no'}")
    print(f"File: {'yes' if is_file else 'no'}")
    print(f"Size: {key_size if key_size is not None else 'n/a'} bytes")
    print(f"Inside repo: {'yes' if inside_repo else 'no'}")
    print(f"Git ignored: {_format_optional_bool(ignored_by_git)}")
    print(f"Git tracked: {_format_optional_bool(tracked_by_git)}")
    if warnings:
        print("Warnings:")
        for warning in warnings:
            print(f"- {warning}")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error}")
    print("Next:")
    for action in payload["next_actions"]:
        print(f"- {action}")
    return 0 if ok else 2


def _format_optional_bool(value: bool | None) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "not checked"


def _check_policy_from_config(config: AgentLedgerConfig) -> CheckPolicy:
    return CheckPolicy(
        require_tests=config.check_require_tests is True,
        dirty=config.check_dirty or "warn",
        max_changed_files=config.check_max_changed_files,
    )


def _allow_warnings_from_config(args: argparse.Namespace, config: AgentLedgerConfig) -> bool:
    return getattr(args, "allow_warnings", False) or config.check_allow_warnings is True


def _handle_check(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    try:
        config = _load_check_config(args, run_dir)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    policy = _check_policy_from_config(config)
    allow_warnings = _allow_warnings_from_config(args, config)
    result = build_check(run_dir, policy)
    if getattr(args, "format", "text") == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_check(result))
    return check_exit_code(result["status"], allow_warnings)


def _resolve_config_path(repo: Path, config_path: str | None) -> Path:
    if config_path is None:
        return (repo / ".agentledger.toml").resolve()
    path = Path(config_path).expanduser()
    if not path.is_absolute():
        path = repo / path
    return path.resolve()


def _handle_init_config(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    if not repo.exists():
        print(f"Target directory not found: {repo}")
        return 2
    if not repo.is_dir():
        print(f"Target path is not a directory: {repo}")
        return 2

    config_path = _resolve_config_path(repo, args.config)
    if config_path.exists() and not args.force:
        print(f"Config already exists: {config_path}")
        print("Use --force to overwrite it.")
        return 2
    if not config_path.parent.exists():
        print(f"Config parent directory not found: {config_path.parent}")
        return 2

    config_path.write_text(STARTER_CONFIG_TEXT, encoding="utf-8")
    print(f"Wrote AgentLedger config: {config_path}")
    print(f"Evidence output: {repo / DEFAULT_OUT}")
    print(f"Next: python -m agentledger run --repo {repo} -- python -m pytest")
    return 0


def _load_cli_config(args: argparse.Namespace, repo: Path) -> AgentLedgerConfig:
    return load_config(repo, getattr(args, "config", None))


def _load_check_config(args: argparse.Namespace, run_dir: Path) -> AgentLedgerConfig:
    if args.repo is not None:
        repo = Path(args.repo).resolve()
    else:
        repo = _check_config_repo(run_dir)
    return load_config(repo, getattr(args, "config", None))


def _check_config_repo(run_dir: Path) -> Path:
    try:
        report = load_report(run_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
        return run_dir
    target_repo = report.get("target_repo")
    if isinstance(target_repo, str) and target_repo.strip():
        return Path(target_repo).resolve()
    return run_dir


def _load_output_config(args: argparse.Namespace, repo: Path) -> AgentLedgerConfig:
    return _load_cli_config(args, repo)


def _resolve_out_root(args: argparse.Namespace, repo: Path, config: AgentLedgerConfig) -> Path:
    if args.out is not None:
        return Path(args.out).resolve()
    if config.out is None:
        return Path(DEFAULT_OUT).resolve()

    configured = Path(config.out)
    if configured.is_absolute():
        return configured.resolve()
    return (repo / configured).resolve()


def _capture_hint(out_root: Path) -> str:
    return f"Run a capture first: python -m agentledger run --out {out_root} -- <command>"


def _resolve_latest_run_dir(out_root: Path) -> tuple[Path | None, list[str]]:
    latest_path = out_root / "latest.txt"
    if not out_root.exists():
        return None, [
            f"No AgentLedger output directory found: {out_root}",
            _capture_hint(out_root),
        ]
    if not latest_path.exists():
        return None, [
            f"No latest run pointer found: {latest_path}",
            _capture_hint(out_root),
        ]
    latest_value = latest_path.read_text(encoding="utf-8").strip()
    if not latest_value:
        return None, [
            f"Latest run pointer is empty: {latest_path}",
            "Run another capture to refresh latest.txt.",
        ]
    latest_dir = Path(latest_value)
    if not latest_dir.is_absolute():
        candidate = out_root / latest_dir
        latest_dir = candidate if candidate.exists() else latest_dir
    latest_dir = latest_dir.resolve()
    if not latest_dir.exists():
        return None, [
            f"Latest report directory not found: {latest_dir}",
            f"latest.txt points to: {latest_value}",
            "Run another capture to refresh latest.txt.",
        ]
    return latest_dir, []


def _handle_open_latest(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").resolve()
    output_format = getattr(args, "format", "text")
    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        if output_format == "json":
            print(
                json.dumps(
                    {
                        "schema_version": "agentledger.open_latest.v1",
                        "ok": False,
                        "repo": str(repo),
                        "out": None,
                        "latest_run": None,
                        "paths": {},
                        "missing_reports": [],
                        "errors": [f"Config error: {exc}"],
                    },
                    indent=2,
                )
            )
        else:
            print(f"Config error: {exc}")
        return 2
    out_root = _resolve_out_root(args, repo, config)
    latest_dir, errors = _resolve_latest_run_dir(out_root)
    if latest_dir is None:
        if output_format == "json":
            print(
                json.dumps(
                    {
                        "schema_version": "agentledger.open_latest.v1",
                        "ok": False,
                        "repo": str(repo),
                        "out": str(out_root),
                        "latest_run": None,
                        "paths": {},
                        "missing_reports": [],
                        "errors": errors,
                    },
                    indent=2,
                )
            )
        else:
            for message in errors:
                print(message)
        return 2

    markdown_path = latest_dir / "agentledger-report.md"
    json_path = latest_dir / "agentledger-report.json"
    html_path = latest_dir / "agentledger-report.html"
    zip_path = latest_dir.with_suffix(".zip")
    missing_reports = [
        str(path)
        for path in (markdown_path, json_path, html_path)
        if not path.exists()
    ]
    if output_format == "json":
        print(
            json.dumps(
                {
                    "schema_version": "agentledger.open_latest.v1",
                    "ok": not missing_reports,
                    "repo": str(repo),
                    "out": str(out_root),
                    "latest_run": str(latest_dir),
                    "paths": {
                        "markdown": str(markdown_path),
                        "json": str(json_path),
                        "html": str(html_path),
                        "zip": str(zip_path) if zip_path.exists() else None,
                    },
                    "missing_reports": missing_reports,
                    "errors": [f"Missing expected report file: {path}" for path in missing_reports],
                },
                indent=2,
            )
        )
        return 2 if missing_reports else 0

    print(f"Latest run: {latest_dir}")
    print(f"Markdown report: {markdown_path}")
    print(f"JSON report: {json_path}")
    print(f"HTML report: {html_path}")
    if zip_path.exists():
        print(f"Zip bundle: {zip_path}")
    if missing_reports:
        print("Missing expected report files:")
        for path in missing_reports:
            print(f"- {path}")
        return 2
    return 0


def _report_summary(run_dir: Path) -> dict:
    report = load_report(run_dir)
    passed, warned = artifact_status_counts([artifact for artifact in report.get("artifacts", []) if isinstance(artifact, dict)])
    return {
        "run_id": str(report.get("run_id") or run_dir.name),
        "run_dir": str(run_dir),
        "started_at": report.get("started_at"),
        "ended_at": report.get("ended_at"),
        "command": report_command_text(report),
        "exit_code": command_exit_code(report),
        "changed_files": changed_file_count(report),
        "test_framework": command_test_framework(report),
        "privacy_mode": str(report.get("privacy_mode") or "standard"),
        "artifacts": {"ok": passed, "warn": warned},
        "markdown": str(run_dir / "agentledger-report.md"),
        "json": str(run_dir / "agentledger-report.json"),
        "html": str(run_dir / "agentledger-report.html"),
        "zip": str(run_dir.with_suffix(".zip")) if run_dir.with_suffix(".zip").exists() else None,
    }


def _handle_history(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    out_root = _resolve_out_root(args, repo, config)
    if args.limit <= 0:
        print("--limit must be greater than zero.")
        return 2
    if not out_root.exists():
        print(f"No AgentLedger output directory found: {out_root}")
        print(f"Run a capture first: python -m agentledger run --out {out_root} -- <command>")
        return 2

    run_dirs = _report_run_dirs(out_root)[: args.limit]

    summaries = [_report_summary(run_dir) for run_dir in run_dirs]

    if getattr(args, "format", "text") == "json":
        print(
            json.dumps(
                {
                    "schema_version": "agentledger.history.v1",
                    "out": str(out_root),
                    "runs": summaries,
                },
                indent=2,
            )
        )
        return 0

    if not summaries:
        print(f"No AgentLedger runs found in {out_root}")
        return 0

    print(f"AgentLedger runs in {out_root}:")
    for item in summaries:
        exit_code = item["exit_code"] if item["exit_code"] is not None else "n/a"
        print(
            f"{item['run_id']} | exit={exit_code} | changed={item['changed_files']} | "
            f"test={item['test_framework']} | privacy={item['privacy_mode']} | command={item['command']}"
        )
        print(f"  report={item['markdown']}")
    return 0


def _latest_paths(run_dir: Path) -> dict[str, str | None]:
    zip_path = run_dir.with_suffix(".zip")
    return {
        "markdown": str(run_dir / "agentledger-report.md"),
        "json": str(run_dir / "agentledger-report.json"),
        "html": str(run_dir / "agentledger-report.html"),
        "zip": str(zip_path) if zip_path.exists() else None,
    }


def _missing_report_paths(run_dir: Path) -> list[str]:
    return [
        str(run_dir / filename)
        for filename in ("agentledger-report.md", "agentledger-report.json", "agentledger-report.html")
        if not (run_dir / filename).exists()
    ]


def _empty_status_feedback(errors: list[str] | None = None) -> dict:
    return {
        "total_entries": 0,
        "returned_entries": 0,
        "runs_with_feedback": 0,
        "latest_run_entries": 0,
        "categories": {},
        "severities": {},
        "errors": errors or [],
    }


def _status_feedback(summary: dict, latest_dir: Path) -> dict:
    latest_entry_count = 0
    latest_text = str(latest_dir)
    for item in summary.get("runs") or []:
        if str(item.get("run_dir") or "") == latest_text:
            latest_entry_count = int(item.get("entry_count") or 0)
            break
    return {
        "total_entries": int(summary.get("total_entries") or 0),
        "returned_entries": int(summary.get("returned_entries") or 0),
        "runs_with_feedback": int(summary.get("runs_with_feedback") or 0),
        "latest_run_entries": latest_entry_count,
        "categories": summary.get("categories") or {},
        "severities": summary.get("severities") or {},
        "errors": list(summary.get("errors") or []),
    }


def _status_next_actions(status: str, feedback: dict, errors: list[str]) -> list[str]:
    if errors:
        return ["Fix the reported status errors, then run agentledger status again."]
    if status == "block":
        return ["Fix blockers, rerun the capture, then run agentledger status again."]
    if status == "warn":
        action = "Read the Markdown report and warning rules before accepting the work."
    else:
        action = "Read the Markdown report, then keep or share only evidence you have reviewed."
    actions = [action]
    if int(feedback.get("total_entries") or 0) > 0:
        actions.append("Use feedback-summary or feedback-export before sharing alpha notes.")
    actions.append("Do not commit .agentledger folders or zip bundles.")
    return actions


def _status_payload(
    *,
    ok: bool,
    status: str,
    repo: Path,
    out_root: Path | None,
    latest_dir: Path | None,
    paths: dict[str, str | None],
    missing_reports: list[str],
    check: dict | None,
    feedback: dict,
    next_actions: list[str],
    errors: list[str],
    status_exit_code: int,
) -> dict:
    return {
        "schema_version": STATUS_SCHEMA,
        "ok": ok,
        "status": status,
        "repo": str(repo),
        "out": str(out_root) if out_root is not None else None,
        "latest_run": str(latest_dir) if latest_dir is not None else None,
        "paths": paths,
        "missing_reports": missing_reports,
        "check": check,
        "feedback": feedback,
        "next_actions": next_actions,
        "errors": errors,
        "status_exit_code": status_exit_code,
    }


def _status_error(
    args: argparse.Namespace,
    repo: Path,
    errors: list[str],
    out_root: Path | None = None,
) -> int:
    payload = _status_payload(
        ok=False,
        status="unknown",
        repo=repo,
        out_root=out_root,
        latest_dir=None,
        paths={},
        missing_reports=[],
        check=None,
        feedback=_empty_status_feedback(),
        next_actions=_status_next_actions("unknown", _empty_status_feedback(), errors),
        errors=errors,
        status_exit_code=2,
    )
    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
    else:
        for message in errors:
            print(message)
    return 2


def _alpha_guide_out_arg(args: argparse.Namespace, config: AgentLedgerConfig) -> str:
    if args.out is not None:
        return str(args.out)
    if config.out is not None:
        return str(config.out)
    return DEFAULT_OUT


def _alpha_guide_doctor(doctor_report: dict) -> dict:
    checks = doctor_report.get("checks") if isinstance(doctor_report.get("checks"), list) else []
    required_blockers = []
    for check in checks:
        if not isinstance(check, dict) or check.get("ok") is True or check.get("required") is not True:
            continue
        required_blockers.append(
            {
                "name": check.get("name") or "unknown",
                "detail": check.get("detail") or "required check failed",
                "hint": check.get("hint") or "",
            }
        )

    optional = doctor_report.get("optional") if isinstance(doctor_report.get("optional"), dict) else {}
    return {
        "schema_version": doctor_report.get("schema_version") or "agentledger.doctor.v1",
        "status": doctor_report.get("status") or "unknown",
        "summary": _first_line(format_doctor(doctor_report)),
        "required_ok": doctor_report.get("required_ok") is True,
        "optional": optional,
        "required_blockers": required_blockers,
        "checks": checks,
    }


def _alpha_guide_payload(args: argparse.Namespace) -> tuple[dict, int]:
    repo = Path(args.repo or ".").resolve()
    doctor_report = run_doctor(repo)
    doctor = _alpha_guide_doctor(doctor_report)
    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        errors = [f"Config error: {exc}"]
        fix_first = _alpha_fix_first("block", errors, [])
        return (
            {
                "schema_version": ALPHA_GUIDE_SCHEMA,
                "ok": False,
                "repo": str(repo),
                "out": None,
                "doctor": doctor,
                "fix_first": fix_first,
                "commands": {},
                "evidence": {},
                "send_back": [],
                "keep_private": [
                    "Do not commit or upload .agentledger folders, zip bundles, signing keys, or full reports unless reviewed and requested."
                ],
                "known_limitations": [],
                "errors": errors,
            },
            2,
        )

    out_root = _resolve_out_root(args, repo, config)
    repo_arg = str(args.repo or ".")
    out_arg = _alpha_guide_out_arg(args, config)
    commands = {
        "setup": [
            'python -m pip install -e ".[dev]"',
            "agentledger --version",
            f"python -m agentledger doctor --repo {repo_arg}",
        ],
        "run": [
            f"python -m agentledger alpha --repo {repo_arg} --out {out_arg}",
            f"python -m agentledger alpha-summary --out {out_arg}",
        ],
        "inspect": [
            f"python -m agentledger status --out {out_arg} --allow-warnings",
            f"python -m agentledger history --out {out_arg}",
            f"python -m agentledger open-latest --out {out_arg}",
        ],
        "feedback": [
            f'python -m agentledger feedback --out {out_arg} --note "First confusing thing: ..."',
            f"python -m agentledger feedback-summary --out {out_arg}",
            f"python -m agentledger feedback-export --out {out_arg} --output $env:TEMP\\agentledger-feedback.md",
            f"python -m agentledger pack-alpha --out {out_arg} --output-dir $env:TEMP\\agentledger-alpha-packet",
        ],
    }
    payload = {
        "schema_version": ALPHA_GUIDE_SCHEMA,
        "ok": True,
        "repo": str(repo),
        "out": str(out_root),
        "commands": commands,
        "evidence": {
            "output_root": str(out_root),
            "latest_pointer": str(out_root / "latest.txt"),
            "run_folder_contains": [
                "agentledger-report.md",
                "agentledger-report.json",
                "agentledger-report.html",
                "artifacts/",
                "alpha-feedback.jsonl when local feedback has been recorded",
            ],
            "bundle": "A sibling .zip bundle is written beside each run folder unless zip export is disabled.",
        },
        "send_back": [
            "Final alpha summary text from agentledger alpha or alpha-summary.",
            "The first command or message that felt confusing.",
            "Whether the Markdown report was understandable enough to trust.",
            "Reviewed feedback export or pack-alpha packet only when requested.",
        ],
        "keep_private": [
            "Do not commit .agentledger folders.",
            "Do not send zip bundles, signing keys, secrets, non-public source, or full reports unless reviewed and requested.",
            "Review feedback exports and pack-alpha packets before sharing.",
        ],
        "known_limitations": [
            "Optional RepoMori, Jester, and Tokometer integrations may warn when not installed.",
            "Bash smoke checks require WSL or another Linux shell with bash.",
        ],
        "errors": [],
    }
    doctor_errors = _alpha_required_setup_errors(doctor_report)
    doctor_next_actions = _alpha_required_setup_next_actions(doctor_report) if doctor_errors else []
    payload["doctor"] = doctor
    payload["fix_first"] = _alpha_fix_first("block" if doctor_errors else "ready", doctor_errors, doctor_next_actions)
    return payload, 0


def _format_alpha_guide(payload: dict) -> str:
    lines = [
        "AgentLedger alpha guide",
        f"Repo: {payload.get('repo') or 'n/a'}",
        f"Output: {payload.get('out') or 'n/a'}",
    ]
    doctor = payload.get("doctor") if isinstance(payload.get("doctor"), dict) else {}
    if doctor:
        lines.append(f"Doctor: {doctor.get('summary') or doctor.get('status') or 'n/a'}")
        optional = doctor.get("optional") if isinstance(doctor.get("optional"), dict) else {}
        if optional:
            lines.append(
                "Optional integrations: "
                f"{optional.get('configured', 0)}/{optional.get('total', 0)} configured"
            )
    fix_first = payload.get("fix_first") if isinstance(payload.get("fix_first"), list) else []
    if fix_first:
        lines.append("Fix first:")
        for action in fix_first:
            lines.append(f"- {action}")
    if payload.get("errors"):
        lines.append("Errors:")
        for error in payload["errors"]:
            lines.append(f"- {error}")
        return "\n".join(lines)

    commands = payload.get("commands") if isinstance(payload.get("commands"), dict) else {}
    for title, key in [
        ("Setup", "setup"),
        ("Run", "run"),
        ("Inspect", "inspect"),
        ("Feedback", "feedback"),
    ]:
        values = commands.get(key) if isinstance(commands.get(key), list) else []
        if not values:
            continue
        lines.append(f"{title}:")
        for command in values:
            lines.append(f"- {command}")

    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    lines.extend(
        [
            "Evidence appears:",
            f"- Output root: {evidence.get('output_root') or 'n/a'}",
            f"- Latest pointer: {evidence.get('latest_pointer') or 'n/a'}",
        ]
    )
    run_folder_contains = evidence.get("run_folder_contains")
    if isinstance(run_folder_contains, list):
        lines.append("- Run folder contains:")
        for item in run_folder_contains:
            lines.append(f"  - {item}")
    if evidence.get("bundle"):
        lines.append(f"- {evidence['bundle']}")

    for title, key in [
        ("Send back", "send_back"),
        ("Keep private", "keep_private"),
        ("Known limitations", "known_limitations"),
    ]:
        values = payload.get(key) if isinstance(payload.get(key), list) else []
        if not values:
            continue
        lines.append(f"{title}:")
        for item in values:
            lines.append(f"- {item}")
    return "\n".join(lines)


def _handle_alpha_guide(args: argparse.Namespace) -> int:
    payload, exit_code = _alpha_guide_payload(args)
    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_format_alpha_guide(payload))
    return exit_code


def _build_status_payload_for_latest(
    *,
    repo: Path,
    out_root: Path,
    latest_dir: Path,
    config: AgentLedgerConfig,
    feedback_limit: int,
    allow_warnings: bool,
) -> dict:
    paths = _latest_paths(latest_dir)
    missing_reports = _missing_report_paths(latest_dir)
    check = build_check(latest_dir, _check_policy_from_config(config))
    feedback_errors: list[str] = []
    try:
        feedback_summary = summarize_feedback(out_root=out_root, limit=feedback_limit)
        feedback = _status_feedback(feedback_summary, latest_dir)
        feedback_errors = feedback["errors"]
    except FeedbackError as exc:
        feedback_errors = [str(exc)]
        feedback = _empty_status_feedback(feedback_errors)

    status = str(check.get("status") or "unknown")
    errors = missing_reports + feedback_errors
    status_exit_code = 2 if errors else check_exit_code(status, allow_warnings)
    next_actions = _status_next_actions(status, feedback, errors)
    return _status_payload(
        ok=check.get("ok") is True and not errors,
        status=status,
        repo=repo,
        out_root=out_root,
        latest_dir=latest_dir,
        paths=paths,
        missing_reports=missing_reports,
        check=check,
        feedback=feedback,
        next_actions=next_actions,
        errors=errors,
        status_exit_code=status_exit_code,
    )


def _handle_status(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").resolve()
    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        return _status_error(args, repo, [f"Config error: {exc}"])
    out_root = _resolve_out_root(args, repo, config)
    if args.feedback_limit <= 0:
        return _status_error(args, repo, ["--feedback-limit must be greater than zero."], out_root)

    latest_dir, errors = _resolve_latest_run_dir(out_root)
    if latest_dir is None:
        return _status_error(args, repo, errors, out_root)

    payload = _build_status_payload_for_latest(
        repo=repo,
        out_root=out_root,
        latest_dir=latest_dir,
        config=config,
        feedback_limit=args.feedback_limit,
        allow_warnings=_allow_warnings_from_config(args, config),
    )
    paths = payload["paths"]
    check = payload["check"]
    feedback = payload["feedback"]
    status = payload["status"]
    errors = payload["errors"]
    next_actions = payload["next_actions"]
    status_exit_code = int(payload["status_exit_code"])

    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
        return status_exit_code

    print(f"AgentLedger status: {status}")
    print(f"Summary: {check['summary']}")
    print(f"Latest run: {latest_dir}")
    if "command" in check:
        print(f"Command: {check['command']}")
        print(f"Exit code: {check['exit_code'] if check['exit_code'] is not None else 'n/a'}")
        print(f"Changed files: {check['changed_files']}")
        print(f"Test framework: {check['test_framework']}")
        print(f"Privacy mode: {check['privacy_mode']}")
    print(
        f"Feedback: {feedback['total_entries']} total entries across "
        f"{feedback['runs_with_feedback']} runs; latest run has {feedback['latest_run_entries']}"
    )
    print(f"Markdown report: {paths['markdown']}")
    print(f"JSON report: {paths['json']}")
    print(f"HTML report: {paths['html']}")
    if paths["zip"]:
        print(f"Zip bundle: {paths['zip']}")
    if check["blocking_rules"]:
        print("Blockers:")
        for rule in check["blocking_rules"]:
            print(f"- {rule['id']}: {rule['message']}")
    if check["warning_rules"]:
        print("Warnings:")
        for rule in check["warning_rules"]:
            print(f"- {rule['id']}: {rule['message']}")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"- {error}")
    print("Next:")
    for action in next_actions:
        print(f"- {action}")
    return status_exit_code


def _first_line(text: str) -> str:
    lines = text.splitlines()
    return lines[0] if lines else ""


def _run_alpha_step(label: str, handler, args: argparse.Namespace, *, quiet: bool) -> tuple[int, str]:
    if not quiet:
        print("")
        print(f"== {label} ==")
        exit_code = handler(args)
        return exit_code, ""

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = handler(args)
    return exit_code, buffer.getvalue()


def _git_version() -> str:
    try:
        result = subprocess.run(
            ["git", "--version"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        return f"git unavailable: {exc}"
    text = (result.stdout or result.stderr).strip()
    return _first_line(text) or f"git exited {result.returncode}"


def _alpha_summary_path(args: argparse.Namespace, out_root: Path) -> Path:
    if args.json_output:
        return Path(args.json_output).expanduser().resolve()
    return (out_root / ALPHA_SUMMARY_FILENAME).resolve()


def _alpha_default_task(task: list[str] | None) -> list[str]:
    command = _clean_task(task or [])
    return command or [sys.executable, "-m", "pytest"]


def _write_alpha_summary(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _try_write_alpha_summary(path: Path | None, payload: dict) -> list[str]:
    if path is None:
        return []
    try:
        _write_alpha_summary(path, payload)
    except OSError as exc:
        return [f"Unable to write alpha summary {path}: {exc}"]
    return []


def _apply_alpha_summary_write_errors(
    payload: dict,
    errors: list[str],
    next_actions: list[str],
    write_errors: list[str],
) -> bool:
    if not write_errors:
        return False
    for error in write_errors:
        if error not in errors:
            errors.append(error)
    if ALPHA_SUMMARY_WRITE_NEXT_ACTION not in next_actions:
        next_actions.append(ALPHA_SUMMARY_WRITE_NEXT_ACTION)
    payload["ok"] = False
    payload["status_exit_code"] = 2
    payload["errors"] = errors
    payload["next_actions"] = next_actions
    payload["fix_first"] = _alpha_fix_first(str(payload.get("status") or "unknown"), errors, next_actions)
    return True


def _alpha_error_paths(args: argparse.Namespace) -> tuple[Path | None, Path | None]:
    if getattr(args, "out", None) is not None:
        out_root = Path(args.out).expanduser().resolve()
        if getattr(args, "json_output", None):
            return Path(args.json_output).expanduser().resolve(), out_root
        return (out_root / ALPHA_SUMMARY_FILENAME).resolve(), out_root
    if getattr(args, "json_output", None):
        return Path(args.json_output).expanduser().resolve(), Path(DEFAULT_OUT).resolve()
    return None, None


def _alpha_required_setup_errors(doctor_report: dict) -> list[str]:
    errors = []
    for check in doctor_report.get("checks") or []:
        if not isinstance(check, dict) or check.get("ok") is True or check.get("required") is not True:
            continue
        name = check.get("name") or "unknown"
        detail = check.get("detail") or "required check failed"
        errors.append(f"Required doctor check failed: {name} - {detail}")
    return errors


def _alpha_required_setup_next_actions(doctor_report: dict) -> list[str]:
    actions = []
    for check in doctor_report.get("checks") or []:
        if not isinstance(check, dict) or check.get("ok") is True or check.get("required") is not True:
            continue
        name = check.get("name") or "unknown"
        hint = str(check.get("hint") or "").strip()
        if hint and hint != "No action needed.":
            actions.append(f"Fix {name}: {hint}")
    actions.append("After fixing required setup, run agentledger alpha again.")
    return actions


def _append_unique(items: list[str], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _alpha_fix_first(status: str, errors: list[str], next_actions: list[str]) -> list[str]:
    if status != "block" and not errors:
        return []

    actions: list[str] = []
    for error in errors:
        if error.startswith("Config error:"):
            _append_unique(actions, "Fix the config error shown below, then run agentledger alpha again.")
        elif error.startswith("Required doctor check failed:"):
            _append_unique(actions, "Fix required setup checks shown below, then run agentledger alpha again.")
        elif error.startswith("Captured command exited"):
            _append_unique(actions, "Fix the captured command failure, then run agentledger alpha again.")
        elif error.startswith("Report check exited"):
            _append_unique(actions, "Fix the report check blocker, then run agentledger alpha again.")
        elif error.startswith("Bundle verification exited"):
            _append_unique(actions, "Fix bundle verification, then run agentledger alpha again.")
        elif "Unable to write alpha summary" in error:
            _append_unique(actions, ALPHA_SUMMARY_WRITE_NEXT_ACTION)

    for action in next_actions:
        action_text = str(action)
        if status == "block" or action_text.startswith(("Fix ", "After fixing", "Choose a writable")):
            _append_unique(actions, action_text)

    if (status == "block" or errors) and not actions:
        actions.append("Review the errors below, fix the first blocker, then run agentledger alpha again.")
    return actions


def _alpha_payload(
    *,
    ok: bool,
    summary_path: Path | None,
    started_at: str,
    repo: Path,
    out_root: Path | None,
    doctor_summary: str,
    status: str,
    status_summary: str,
    status_exit_code: int,
    errors: list[str],
    latest_dir: Path | None = None,
    report_paths: dict | None = None,
    feedback: dict | None = None,
    next_actions: list[str] | None = None,
) -> dict:
    next_actions = next_actions or []
    return {
        "schema_version": ALPHA_SUMMARY_SCHEMA,
        "ok": ok,
        "summary_file": str(summary_path) if summary_path is not None else None,
        "started_at": started_at,
        "ended_at": utc_now_iso(),
        "repo": str(repo),
        "out": str(out_root) if out_root is not None else None,
        "latest_run": str(latest_dir) if latest_dir is not None else None,
        "bundle": str(latest_dir.with_suffix(".zip")) if latest_dir is not None else None,
        "agentledger_version": f"agentledger {__version__}",
        "python_version": f"Python {platform.python_version()}",
        "git_version": _git_version(),
        "doctor": doctor_summary,
        "status": status,
        "status_summary": status_summary,
        "status_exit_code": status_exit_code,
        "report_paths": report_paths or {},
        "feedback": feedback or _empty_status_feedback(),
        "fix_first": _alpha_fix_first(status, errors, next_actions),
        "next_actions": next_actions,
        "errors": errors,
    }


def _alpha_config_error(args: argparse.Namespace, repo: Path, started_at: str, message: str, quiet: bool) -> int:
    summary_path, out_root = _alpha_error_paths(args)
    errors = [message]
    payload = _alpha_payload(
        ok=False,
        summary_path=summary_path,
        started_at=started_at,
        repo=repo,
        out_root=out_root,
        doctor_summary="AgentLedger doctor: not run (config error)",
        status="block",
        status_summary="Config error blocked alpha before setup checks.",
        status_exit_code=2,
        errors=errors,
        next_actions=["Fix the config error, then run agentledger alpha again."],
    )
    if summary_path is not None:
        _apply_alpha_summary_write_errors(
            payload,
            errors,
            payload["next_actions"],
            _try_write_alpha_summary(summary_path, payload),
        )
    if quiet:
        print(json.dumps(payload, indent=2))
    else:
        if summary_path is None:
            print(message)
        else:
            print("== Alpha blocked ==")
            print(_format_alpha_summary(summary_path, payload))
    return 2


def _handle_alpha(args: argparse.Namespace) -> int:
    output_format = getattr(args, "format", "text")
    quiet = output_format == "json"
    repo = Path(args.repo or ".").resolve()
    started_at = utc_now_iso()
    errors: list[str] = []

    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        return _alpha_config_error(args, repo, started_at, f"Config error: {exc}", quiet)

    out_root = _resolve_out_root(args, repo, config)
    summary_path = _alpha_summary_path(args, out_root)

    if not quiet:
        print("== Check AgentLedger version ==")
        print(f"agentledger {__version__}")
        print("")
        print("== Check local readiness ==")
    doctor_report = run_doctor(repo)
    doctor_summary = _first_line(format_doctor(doctor_report))
    if not quiet:
        print(format_doctor(doctor_report))
    if doctor_report.get("status") != "ready":
        errors.extend(_alpha_required_setup_errors(doctor_report) or ["Doctor check did not report ready."])
        payload = _alpha_payload(
            ok=False,
            summary_path=summary_path,
            started_at=started_at,
            repo=repo,
            out_root=out_root,
            doctor_summary=doctor_summary,
            status="block",
            status_summary="Required setup is blocked; fix doctor errors before running alpha again.",
            status_exit_code=2,
            errors=errors,
            next_actions=_alpha_required_setup_next_actions(doctor_report),
        )
        _apply_alpha_summary_write_errors(
            payload,
            errors,
            payload["next_actions"],
            _try_write_alpha_summary(summary_path, payload),
        )
        if quiet:
            print(json.dumps(payload, indent=2))
        else:
            print("")
            print("== Alpha blocked ==")
            print(_format_alpha_summary(summary_path, payload))
        return 2

    capture_args = argparse.Namespace(
        repo=str(repo),
        config=args.config,
        out=str(out_root),
        no_repomori=True,
        no_jester=True,
        no_tokometer=True,
        no_zip=False,
        privacy_mode=args.privacy_mode,
    )
    capture_exit, _ = _run_alpha_step(
        "Capture verification run",
        lambda capture_args: _capture(capture_args, _alpha_default_task(args.task)),
        capture_args,
        quiet=quiet,
    )
    if capture_exit != 0:
        errors.append(f"Captured command exited {capture_exit}.")

    latest_dir, latest_errors = _resolve_latest_run_dir(out_root)
    if latest_errors:
        errors.extend(latest_errors)

    status_payload = _status_payload(
        ok=False,
        status="unknown",
        repo=repo,
        out_root=out_root,
        latest_dir=latest_dir,
        paths={},
        missing_reports=[],
        check=None,
        feedback=_empty_status_feedback(),
        next_actions=_status_next_actions("unknown", _empty_status_feedback(), errors),
        errors=errors,
        status_exit_code=2,
    )
    status_exit = 2
    if latest_dir is not None:
        common_output_args = {
            "repo": str(repo),
            "config": args.config,
            "out": str(out_root),
        }
        _run_alpha_step(
            "Show latest run paths",
            _handle_open_latest,
            argparse.Namespace(**common_output_args, format="text"),
            quiet=quiet,
        )
        _run_alpha_step(
            "Show run history",
            _handle_history,
            argparse.Namespace(**common_output_args, limit=10, format="text"),
            quiet=quiet,
        )
        _run_alpha_step(
            "Show latest status",
            _handle_status,
            argparse.Namespace(
                **common_output_args,
                feedback_limit=3,
                allow_warnings=not args.strict,
                format="text",
            ),
            quiet=quiet,
        )
        status_exit, status_json = _run_alpha_step(
            "Check latest status JSON",
            _handle_status,
            argparse.Namespace(
                **common_output_args,
                feedback_limit=3,
                allow_warnings=not args.strict,
                format="json",
            ),
            quiet=True,
        )
        try:
            status_payload = json.loads(status_json)
        except json.JSONDecodeError as exc:
            errors.append(f"Unable to parse status JSON: {exc}")

        _run_alpha_step(
            "Inspect latest report",
            _handle_inspect_report,
            argparse.Namespace(run_dir=str(latest_dir), format="text"),
            quiet=quiet,
        )
        check_exit, _ = _run_alpha_step(
            "Check latest report",
            _handle_check,
            argparse.Namespace(
                run_dir=str(latest_dir),
                repo=str(repo),
                config=args.config,
                format="text",
                allow_warnings=not args.strict,
            ),
            quiet=quiet,
        )
        if check_exit not in {0, 1} or (args.strict and check_exit != 0):
            errors.append(f"Report check exited {check_exit}.")
        bundle_path = latest_dir.with_suffix(".zip")
        verify_exit, _ = _run_alpha_step(
            "Verify latest bundle",
            _handle_verify_bundle,
            argparse.Namespace(
                bundle=str(bundle_path),
                signature_key_file=None,
                require_signature=False,
                format="text",
            ),
            quiet=quiet,
        )
        if verify_exit != 0:
            errors.append(f"Bundle verification exited {verify_exit}.")

    status = str(status_payload.get("status") or "unknown")
    status_summary = ""
    check_payload = status_payload.get("check")
    if isinstance(check_payload, dict):
        status_summary = str(check_payload.get("summary") or "")
    if not status_summary:
        status_summary = "Alpha pass did not produce a status summary."
    status_errors = status_payload.get("errors") if isinstance(status_payload.get("errors"), list) else []
    for error in status_errors:
        if error not in errors:
            errors.append(str(error))
    report_paths = status_payload.get("paths") if isinstance(status_payload.get("paths"), dict) else {}
    feedback = status_payload.get("feedback") if isinstance(status_payload.get("feedback"), dict) else _empty_status_feedback()
    next_actions = status_payload.get("next_actions") if isinstance(status_payload.get("next_actions"), list) else []
    status_exit_code = int(status_payload.get("status_exit_code") or status_exit)
    ok = not errors and status_exit_code == 0
    payload = _alpha_payload(
        ok=ok,
        summary_path=summary_path,
        started_at=started_at,
        repo=repo,
        out_root=out_root,
        latest_dir=latest_dir,
        doctor_summary=doctor_summary,
        status=status,
        status_summary=status_summary,
        status_exit_code=status_exit_code,
        report_paths=report_paths,
        feedback=feedback,
        next_actions=next_actions,
        errors=errors,
    )
    if _apply_alpha_summary_write_errors(
        payload,
        errors,
        next_actions,
        _try_write_alpha_summary(summary_path, payload),
    ):
        ok = False

    if quiet:
        print(json.dumps(payload, indent=2))
    else:
        print("")
        print("== Alpha complete ==")
        print(_format_alpha_summary(summary_path, payload))
        print("")
        print("Do not send or commit .agentledger folders, zip bundles, secrets, or sensitive evidence unless requested.")
    return 0 if ok else 2


def _alpha_summary_error(
    args: argparse.Namespace,
    errors: list[str],
    summary_file: Path | None = None,
) -> int:
    if getattr(args, "format", "text") == "json":
        payload = {
            "schema_version": ALPHA_SUMMARY_SCHEMA,
            "ok": False,
            "summary_file": str(summary_file) if summary_file is not None else None,
            "errors": errors,
        }
        print(json.dumps(payload, indent=2))
    else:
        for message in errors:
            print(message)
    return 2


def _resolve_alpha_summary_file(args: argparse.Namespace) -> tuple[Path | None, list[str]]:
    if args.summary_file:
        return Path(args.summary_file).expanduser().resolve(), []

    repo = Path(args.repo or ".").resolve()
    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        return None, [f"Config error: {exc}"]
    out_root = _resolve_out_root(args, repo, config)
    return (out_root / ALPHA_SUMMARY_FILENAME).resolve(), []


def _load_alpha_summary(path: Path) -> tuple[dict | None, list[str]]:
    if not path.exists():
        return None, [
            f"Alpha summary file not found: {path}",
            "Run agentledger alpha or scripts/alpha.ps1 first, or pass a summary path.",
        ]
    if not path.is_file():
        return None, [f"Alpha summary path is not a file: {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, [f"Unable to read alpha summary {path}: {exc}"]
    if not isinstance(payload, dict):
        return None, [f"Alpha summary JSON must be an object: {path}"]
    return payload, []


def _validate_alpha_summary(payload: dict) -> list[str]:
    errors: list[str] = []
    schema = payload.get("schema_version")
    if schema != ALPHA_SUMMARY_SCHEMA:
        errors.append(f"Expected schema_version {ALPHA_SUMMARY_SCHEMA}, found {schema!r}.")
    missing = sorted(ALPHA_SUMMARY_REQUIRED_FIELDS - payload.keys())
    if missing:
        errors.append("Missing alpha summary fields: " + ", ".join(missing))
    if "ok" in payload and not isinstance(payload.get("ok"), bool):
        errors.append("Alpha summary field ok must be a boolean.")
    if "errors" in payload and not isinstance(payload.get("errors"), list):
        errors.append("Alpha summary field errors must be a list.")
    if "next_actions" in payload and not isinstance(payload.get("next_actions"), list):
        errors.append("Alpha summary field next_actions must be a list.")
    if "fix_first" in payload and not isinstance(payload.get("fix_first"), list):
        errors.append("Alpha summary field fix_first must be a list.")
    if "report_paths" in payload and not isinstance(payload.get("report_paths"), dict):
        errors.append("Alpha summary field report_paths must be an object.")
    if "feedback" in payload and not isinstance(payload.get("feedback"), dict):
        errors.append("Alpha summary field feedback must be an object.")
    return errors


def _normalized_alpha_summary_payload(payload: dict) -> dict:
    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    fix_first = payload.get("fix_first")
    if isinstance(fix_first, list):
        return payload
    normalized = dict(payload)
    normalized["fix_first"] = _alpha_fix_first(str(payload.get("status") or "unknown"), errors, next_actions)
    return normalized


def _format_alpha_summary(path: Path, payload: dict) -> str:
    status = payload.get("status") or "unknown"
    status_summary = payload.get("status_summary") or "No status summary."
    feedback = payload.get("feedback") if isinstance(payload.get("feedback"), dict) else {}
    paths = payload.get("report_paths") if isinstance(payload.get("report_paths"), dict) else {}
    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    fix_first = payload.get("fix_first") if isinstance(payload.get("fix_first"), list) else _alpha_fix_first(str(status), errors, next_actions)

    lines = [
        f"AgentLedger alpha summary: {status}",
        f"Summary: {status_summary}",
        f"Summary file: {path}",
        f"Repo: {payload.get('repo') or 'n/a'}",
        f"Output: {payload.get('out') or 'n/a'}",
        f"Latest run: {payload.get('latest_run') or 'n/a'}",
        f"Bundle: {payload.get('bundle') or 'n/a'}",
        f"AgentLedger: {payload.get('agentledger_version') or 'n/a'}",
        f"Python: {payload.get('python_version') or 'n/a'}",
        f"Git: {payload.get('git_version') or 'n/a'}",
        f"Doctor: {payload.get('doctor') or 'n/a'}",
        (
            f"Feedback: {feedback.get('total_entries', 0)} total entries across "
            f"{feedback.get('runs_with_feedback', 0)} runs; latest run has {feedback.get('latest_run_entries', 0)}"
        ),
    ]
    if fix_first:
        lines.append("Fix first:")
        for action in fix_first:
            lines.append(f"- {action}")
    if paths:
        lines.extend(
            [
                f"Markdown report: {paths.get('markdown') or 'n/a'}",
                f"JSON report: {paths.get('json') or 'n/a'}",
                f"HTML report: {paths.get('html') or 'n/a'}",
            ]
        )
        if paths.get("zip"):
            lines.append(f"Zip bundle: {paths['zip']}")
    if next_actions:
        lines.append("Next:")
        for action in next_actions:
            lines.append(f"- {action}")
    lines.extend(
        [
            "Send back:",
            "- This summary text, plus the first command or message that felt confusing.",
            "- Whether the Markdown report was understandable enough to trust.",
            "- A reviewed feedback export or pack-alpha packet only if requested.",
            "Keep private:",
            "- Do not send .agentledger folders, zip bundles, signing keys, or full reports unless requested.",
        ]
    )
    if errors:
        lines.append("Errors:")
        for error in errors:
            lines.append(f"- {error}")
    return "\n".join(lines)


def _handle_alpha_summary(args: argparse.Namespace) -> int:
    summary_file, resolve_errors = _resolve_alpha_summary_file(args)
    if resolve_errors:
        return _alpha_summary_error(args, resolve_errors, summary_file)
    assert summary_file is not None
    payload, load_errors = _load_alpha_summary(summary_file)
    if load_errors:
        return _alpha_summary_error(args, load_errors, summary_file)
    assert payload is not None
    validation_errors = _validate_alpha_summary(payload)
    if validation_errors:
        return _alpha_summary_error(args, validation_errors, summary_file)
    payload = _normalized_alpha_summary_payload(payload)

    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(_format_alpha_summary(summary_file, payload))
    summary_errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    return 0 if payload.get("ok") is True and not summary_errors else 2


def _resolve_feedback_run_dir(args: argparse.Namespace) -> tuple[Path | None, list[str]]:
    if args.run_dir:
        return Path(args.run_dir).resolve(), []

    repo = Path(args.repo or ".").resolve()
    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        return None, [f"Config error: {exc}"]
    out_root = _resolve_out_root(args, repo, config)
    return _resolve_latest_run_dir(out_root)


def _feedback_error(args: argparse.Namespace, action: str, errors: list[str]) -> int:
    if getattr(args, "format", "text") == "json":
        print(
            json.dumps(
                {
                    "schema_version": FEEDBACK_SCHEMA,
                    "ok": False,
                    "action": action,
                    "run_dir": None,
                    "feedback_file": None,
                    "entry": None,
                    "entries": [],
                    "errors": errors,
                },
                indent=2,
            )
        )
    else:
        for message in errors:
            print(message)
    return 2


def _format_feedback_entry(entry: dict) -> str:
    created_at = str(entry.get("created_at") or "unknown time")
    category = str(entry.get("category") or "other")
    severity = str(entry.get("severity") or "medium")
    source = str(entry.get("source") or "tester")
    note = str(entry.get("note") or "").replace("\r", " ").replace("\n", " ")
    return f"- {created_at} | {severity} | {category} | {source}: {note}"


def _format_feedback_summary_entry(entry: dict) -> str:
    created_at = str(entry.get("created_at") or "unknown time")
    category = str(entry.get("category") or "other")
    severity = str(entry.get("severity") or "medium")
    source = str(entry.get("source") or "tester")
    run_id = str(entry.get("run_id") or "unknown run")
    note = str(entry.get("note") or "").replace("\r", " ").replace("\n", " ")
    return f"- {created_at} | {severity} | {category} | {run_id} | {source}: {note}"


def _handle_feedback(args: argparse.Namespace) -> int:
    action = "list" if args.list_entries else "record"
    if args.list_entries and args.note is not None:
        return _feedback_error(args, action, ["Use either --list or --note, not both."])
    if not args.list_entries and args.note is None:
        return _feedback_error(args, action, ["Feedback note is required unless --list is used."])

    run_dir, errors = _resolve_feedback_run_dir(args)
    if run_dir is None:
        return _feedback_error(args, action, errors)

    try:
        if args.list_entries:
            path, entries = read_feedback(run_dir)
            entry = None
        else:
            path, entry = append_feedback(
                run_dir=run_dir,
                note=args.note,
                category=args.category,
                severity=args.severity,
                source=args.source,
            )
            entries = [entry]
    except FeedbackError as exc:
        return _feedback_error(args, action, [str(exc)])

    if getattr(args, "format", "text") == "json":
        print(
            json.dumps(
                {
                    "schema_version": FEEDBACK_SCHEMA,
                    "ok": True,
                    "action": action,
                    "run_dir": str(run_dir),
                    "feedback_file": str(path),
                    "entry": entry,
                    "entries": entries,
                    "errors": [],
                },
                indent=2,
            )
        )
        return 0

    if args.list_entries:
        if not entries:
            print(f"No feedback entries found: {path}")
            return 0
        print(f"AgentLedger feedback for {run_dir}:")
        for item in entries:
            print(_format_feedback_entry(item))
        return 0

    print(f"Feedback recorded: {path}")
    print(f"Run: {run_dir}")
    print(f"Category: {entry['category']}")
    print(f"Severity: {entry['severity']}")
    if entry["redacted"]:
        print("Note: feedback was redacted before saving.")
    print("Next: keep alpha-feedback.jsonl local unless reviewed; do not commit .agentledger folders.")
    return 0


def _feedback_summary_error(args: argparse.Namespace, errors: list[str], out_root: Path | None = None) -> int:
    if getattr(args, "format", "text") == "json":
        print(
            json.dumps(
                {
                    "schema_version": FEEDBACK_SUMMARY_SCHEMA,
                    "ok": False,
                    "out": str(out_root) if out_root is not None else None,
                    "filters": {
                        "category": getattr(args, "category", None),
                        "severity": getattr(args, "severity", None),
                        "limit": getattr(args, "limit", None),
                    },
                    "total_entries": 0,
                    "returned_entries": 0,
                    "run_count": 0,
                    "runs_with_feedback": 0,
                    "categories": {},
                    "severities": {},
                    "runs": [],
                    "entries": [],
                    "errors": errors,
                },
                indent=2,
            )
        )
    else:
        for message in errors:
            print(message)
    return 2


def _handle_feedback_summary(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").resolve()
    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        return _feedback_summary_error(args, [f"Config error: {exc}"])
    out_root = _resolve_out_root(args, repo, config)

    try:
        summary = summarize_feedback(
            out_root=out_root,
            limit=args.limit,
            category=args.category,
            severity=args.severity,
        )
    except FeedbackError as exc:
        return _feedback_summary_error(args, [str(exc)], out_root)

    if getattr(args, "format", "text") == "json":
        print(json.dumps(summary, indent=2))
        return 0 if summary["ok"] else 2

    print(f"AgentLedger feedback summary in {out_root}:")
    print(
        f"Entries: {summary['returned_entries']} shown / {summary['total_entries']} total "
        f"across {summary['runs_with_feedback']} runs"
    )
    filters = summary["filters"]
    active_filters = [
        f"{name}={value}"
        for name, value in filters.items()
        if name != "limit" and value is not None
    ]
    if active_filters:
        print(f"Filters: {', '.join(active_filters)}")
    if summary["categories"]:
        print(
            "Categories: "
            + ", ".join(f"{name}={count}" for name, count in summary["categories"].items())
        )
    if summary["severities"]:
        print(
            "Severities: "
            + ", ".join(f"{name}={count}" for name, count in summary["severities"].items())
        )
    if summary["entries"]:
        print("Recent feedback:")
        for entry in summary["entries"]:
            print(_format_feedback_summary_entry(entry))
    else:
        print("No feedback entries found.")
    if summary["errors"]:
        print("Errors:")
        for error in summary["errors"]:
            print(f"- {error}")
        return 2
    return 0


def _feedback_export_payload(
    *,
    ok: bool,
    out_root: Path | None,
    output_path: Path | None,
    output_format: str,
    filters: dict,
    total_entries: int,
    returned_entries: int,
    run_count: int,
    runs_with_feedback: int,
    errors: list[str],
) -> dict:
    return {
        "schema_version": FEEDBACK_EXPORT_RESULT_SCHEMA,
        "ok": ok,
        "out": str(out_root) if out_root is not None else None,
        "output": str(output_path) if output_path is not None else None,
        "output_format": output_format,
        "export_schema_version": FEEDBACK_EXPORT_SCHEMA,
        "filters": filters,
        "total_entries": total_entries,
        "returned_entries": returned_entries,
        "run_count": run_count,
        "runs_with_feedback": runs_with_feedback,
        "errors": errors,
    }


def _feedback_export_error(
    args: argparse.Namespace,
    errors: list[str],
    out_root: Path | None = None,
    output_path: Path | None = None,
) -> int:
    if getattr(args, "format", "text") == "json":
        payload = _feedback_export_payload(
            ok=False,
            out_root=out_root,
            output_path=output_path,
            output_format=getattr(args, "output_format", "markdown"),
            filters={
                "category": getattr(args, "category", None),
                "severity": getattr(args, "severity", None),
                "limit": getattr(args, "limit", None),
            },
            total_entries=0,
            returned_entries=0,
            run_count=0,
            runs_with_feedback=0,
            errors=errors,
        )
        print(json.dumps(payload, indent=2))
    else:
        for message in errors:
            print(message)
    return 2


def _handle_feedback_export(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").resolve()
    output_path = Path(args.output).resolve()
    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        return _feedback_export_error(args, [f"Config error: {exc}"], output_path=output_path)
    out_root = _resolve_out_root(args, repo, config)

    try:
        summary = summarize_feedback(
            out_root=out_root,
            limit=args.limit,
            category=args.category,
            severity=args.severity,
        )
    except FeedbackError as exc:
        return _feedback_export_error(args, [str(exc)], out_root, output_path)

    if not summary["ok"]:
        return _feedback_export_error(args, summary["errors"], out_root, output_path)

    try:
        written_path, export = write_feedback_export(
            summary=summary,
            output_path=output_path,
            output_format=args.output_format,
        )
    except FeedbackError as exc:
        return _feedback_export_error(args, [str(exc)], out_root, output_path)

    payload = _feedback_export_payload(
        ok=True,
        out_root=out_root,
        output_path=written_path,
        output_format=args.output_format,
        filters=summary["filters"],
        total_entries=summary["total_entries"],
        returned_entries=summary["returned_entries"],
        run_count=summary["run_count"],
        runs_with_feedback=summary["runs_with_feedback"],
        errors=[],
    )

    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Feedback export written: {written_path}")
    print(f"Format: {args.output_format}")
    print(
        f"Entries: {export['returned_entries']} shown / {export['total_entries']} total "
        f"across {export['runs_with_feedback']} runs"
    )
    print("Review before sharing. The export omits local run directories and feedback file paths.")
    return 0


def _review_paths(run_dir: Path) -> dict[str, str | None]:
    zip_path = run_dir.with_suffix(".zip")
    return {
        "markdown": str(run_dir / "agentledger-report.md"),
        "json": str(run_dir / "agentledger-report.json"),
        "html": str(run_dir / "agentledger-report.html"),
        "zip": str(zip_path) if zip_path.exists() else None,
    }


def _report_run_dirs(out_root: Path) -> list[Path]:
    def sort_key(path: Path) -> tuple[str, int, str]:
        report_path = path / "agentledger-report.json"
        started_at = ""
        try:
            report = load_report(path)
            started_at = str(report.get("started_at") or "")
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError):
            pass
        try:
            mtime_ns = report_path.stat().st_mtime_ns
        except OSError:
            mtime_ns = 0
        return started_at, mtime_ns, path.name

    return sorted(
        [
            child
            for child in out_root.iterdir()
            if child.is_dir() and (child / "agentledger-report.json").exists()
        ],
        key=sort_key,
        reverse=True,
    )


def _review_history(run_dir: Path, limit: int) -> dict:
    out_root = run_dir.parent
    payload = {
        "out": str(out_root),
        "limit": limit,
        "runs": [],
        "errors": [],
    }
    if limit <= 0:
        return payload
    if not out_root.exists():
        payload["errors"].append(f"Review history output directory not found: {out_root}")
        return payload

    run_dirs = _report_run_dirs(out_root)[:limit]
    current = run_dir.resolve()
    for history_dir in run_dirs:
        try:
            summary = _report_summary(history_dir)
        except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
            payload["errors"].append(f"Unable to read history report in {history_dir}: {exc}")
            continue
        summary["current"] = history_dir.resolve() == current
        payload["runs"].append(summary)
    return payload


def _review_previous_comparison(run_dir: Path) -> dict:
    current = run_dir.resolve()
    payload = {
        "available": False,
        "current_run": str(current),
        "previous_run": None,
        "compare": None,
        "errors": [],
    }
    out_root = run_dir.parent
    if not out_root.exists():
        payload["errors"].append(f"Review comparison output directory not found: {out_root}")
        return payload

    run_dirs = _report_run_dirs(out_root)
    current_index = None
    for index, candidate in enumerate(run_dirs):
        if candidate.resolve() == current:
            current_index = index
            break
    if current_index is None:
        payload["errors"].append(f"Reviewed run was not found in history output: {current}")
        return payload
    older_runs = run_dirs[current_index + 1 :]
    if not older_runs:
        return payload

    previous_run = older_runs[0].resolve()
    payload["previous_run"] = str(previous_run)
    try:
        old_report = load_report(previous_run)
        new_report = load_report(current)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        payload["errors"].append(f"Unable to compare previous run {previous_run}: {exc}")
        return payload

    payload["available"] = True
    payload["compare"] = _compare_reports_payload(old_report, new_report)
    return payload


def _load_review_run_dir(args: argparse.Namespace) -> Path | None:
    if args.run_dir:
        return Path(args.run_dir).resolve()

    repo = Path(args.repo or ".").resolve()
    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return None
    out_root = _resolve_out_root(args, repo, config)
    latest_dir, errors = _resolve_latest_run_dir(out_root)
    if latest_dir is None:
        for message in errors:
            print(message)
        return None
    return latest_dir


def _review_next_line(status: str) -> str:
    if status == "block":
        return "Fix blockers, rerun the command, then review again."
    if status == "warn":
        return "Read the Markdown report and warning rules before accepting the work."
    return "Read the Markdown report, then keep or share only evidence you have reviewed."


def _format_review(result: dict, paths: dict[str, str | None], history: dict, comparison: dict) -> str:
    lines = [
        f"AgentLedger review: {result['status']}",
        f"Summary: {result['summary']}",
        f"Run: {result['run_dir']}",
    ]
    if "command" in result:
        lines.extend(
            [
                f"Command: {result['command']}",
                f"Exit code: {result['exit_code'] if result['exit_code'] is not None else 'n/a'}",
                f"Changed files: {result['changed_files']}",
                f"Test framework: {result['test_framework']}",
                f"Privacy mode: {result['privacy_mode']}",
            ]
        )

    lines.extend(
        [
            f"Markdown report: {paths['markdown']}",
            f"JSON report: {paths['json']}",
            f"HTML report: {paths['html']}",
        ]
    )
    if paths["zip"]:
        lines.append(f"Zip bundle: {paths['zip']}")

    history_runs = history.get("runs") if isinstance(history.get("runs"), list) else []
    if history_runs:
        lines.append("Recent runs:")
        for item in history_runs:
            marker = "*" if item.get("current") is True else "-"
            exit_code = item["exit_code"] if item.get("exit_code") is not None else "n/a"
            lines.append(
                f"{marker} {item['run_id']} | exit={exit_code} | changed={item['changed_files']} | "
                f"test={item['test_framework']} | command={item['command']}"
            )
    history_errors = history.get("errors") if isinstance(history.get("errors"), list) else []
    if history_errors:
        lines.append("History warnings:")
        for error in history_errors:
            lines.append(f"- {error}")

    compare_payload = comparison.get("compare") if isinstance(comparison.get("compare"), dict) else None
    if comparison.get("available") is True and compare_payload:
        changed = compare_payload["changed_files"]
        exit_code = compare_payload["exit_code"]
        artifacts = compare_payload["artifacts"]
        lines.append("Previous comparison:")
        lines.append(f"Previous run: {comparison['previous_run']}")
        lines.append(
            f"Changed files: {changed['old']} -> {changed['new']} ({changed['delta_text']})"
        )
        lines.append(
            "Exit code: "
            f"{exit_code['old'] if exit_code['old'] is not None else 'n/a'} -> "
            f"{exit_code['new'] if exit_code['new'] is not None else 'n/a'} "
            f"({exit_code['trend']})"
        )
        lines.append(
            f"Artifacts: {artifacts['old']['ok']} ok/{artifacts['old']['warn']} warn -> "
            f"{artifacts['new']['ok']} ok/{artifacts['new']['warn']} warn"
        )
        lines.append(
            f"Test framework: {compare_payload['test_framework']['old']} -> "
            f"{compare_payload['test_framework']['new']}"
        )
    comparison_errors = comparison.get("errors") if isinstance(comparison.get("errors"), list) else []
    if comparison_errors:
        lines.append("Comparison warnings:")
        for error in comparison_errors:
            lines.append(f"- {error}")

    if result["blocking_rules"]:
        lines.append("Blockers:")
        for rule in result["blocking_rules"]:
            lines.append(f"- {rule['id']}: {rule['message']}")
    if result["warning_rules"]:
        lines.append("Warnings:")
        for rule in result["warning_rules"]:
            lines.append(f"- {rule['id']}: {rule['message']}")

    next_line = _review_next_line(result["status"])
    lines.extend(
        [
            "Next:",
            f"- {next_line}",
            "- Do not commit .agentledger folders or zip bundles.",
        ]
    )
    return "\n".join(lines)


def _markdown_inline(value: object) -> str:
    text = str(value)
    longest_tick_run = 0
    current_tick_run = 0
    for character in text:
        if character == "`":
            current_tick_run += 1
            longest_tick_run = max(longest_tick_run, current_tick_run)
        else:
            current_tick_run = 0
    delimiter = "`" * (longest_tick_run + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{delimiter}{padding}{text}{padding}{delimiter}"


def _format_review_markdown(result: dict, paths: dict[str, str | None], history: dict, comparison: dict) -> str:
    lines = [
        "# AgentLedger Review",
        "",
        f"- Status: {result['status']}",
        f"- Summary: {result['summary']}",
        f"- Run: {_markdown_inline(result['run_dir'])}",
    ]
    if "command" in result:
        lines.extend(
            [
                f"- Command: {_markdown_inline(result['command'])}",
                f"- Exit code: {result['exit_code'] if result['exit_code'] is not None else 'n/a'}",
                f"- Changed files: {result['changed_files']}",
                f"- Test framework: {result['test_framework']}",
                f"- Privacy mode: {result['privacy_mode']}",
            ]
        )

    lines.extend(
        [
            "",
            "## Evidence",
            "",
            f"- Markdown report: {_markdown_inline(paths['markdown'])}",
            f"- JSON report: {_markdown_inline(paths['json'])}",
            f"- HTML report: {_markdown_inline(paths['html'])}",
        ]
    )
    if paths["zip"]:
        lines.append(f"- Zip bundle: {_markdown_inline(paths['zip'])}")

    history_runs = history.get("runs") if isinstance(history.get("runs"), list) else []
    if history_runs:
        lines.extend(["", "## Recent Runs", ""])
        for item in history_runs:
            marker = "current" if item.get("current") is True else "previous"
            exit_code = item["exit_code"] if item.get("exit_code") is not None else "n/a"
            lines.append(
                f"- {marker}: {item['run_id']} | exit={exit_code} | changed={item['changed_files']} | "
                f"test={item['test_framework']} | command={_markdown_inline(item['command'])}"
            )
    history_errors = history.get("errors") if isinstance(history.get("errors"), list) else []
    if history_errors:
        lines.extend(["", "## History Warnings", ""])
        for error in history_errors:
            lines.append(f"- {error}")

    compare_payload = comparison.get("compare") if isinstance(comparison.get("compare"), dict) else None
    if comparison.get("available") is True and compare_payload:
        changed = compare_payload["changed_files"]
        exit_code = compare_payload["exit_code"]
        artifacts = compare_payload["artifacts"]
        lines.extend(
            [
                "",
                "## Previous Comparison",
                "",
                f"- Previous run: {_markdown_inline(comparison['previous_run'])}",
                f"- Changed files: {changed['old']} -> {changed['new']} ({changed['delta_text']})",
                (
                    "- Exit code: "
                    f"{exit_code['old'] if exit_code['old'] is not None else 'n/a'} -> "
                    f"{exit_code['new'] if exit_code['new'] is not None else 'n/a'} "
                    f"({exit_code['trend']})"
                ),
                (
                    f"- Artifacts: {artifacts['old']['ok']} ok/{artifacts['old']['warn']} warn -> "
                    f"{artifacts['new']['ok']} ok/{artifacts['new']['warn']} warn"
                ),
                (
                    f"- Test framework: {compare_payload['test_framework']['old']} -> "
                    f"{compare_payload['test_framework']['new']}"
                ),
            ]
        )
    comparison_errors = comparison.get("errors") if isinstance(comparison.get("errors"), list) else []
    if comparison_errors:
        lines.extend(["", "## Comparison Warnings", ""])
        for error in comparison_errors:
            lines.append(f"- {error}")

    if result["blocking_rules"]:
        lines.extend(["", "## Blockers", ""])
        for rule in result["blocking_rules"]:
            lines.append(f"- {rule['id']}: {rule['message']}")
    if result["warning_rules"]:
        lines.extend(["", "## Warnings", ""])
        for rule in result["warning_rules"]:
            lines.append(f"- {rule['id']}: {rule['message']}")

    lines.extend(
        [
            "",
            "## Next",
            "",
            f"- {_review_next_line(result['status'])}",
            "- Do not commit .agentledger folders or zip bundles.",
        ]
    )
    return "\n".join(lines)


def _write_rendered_output(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered.rstrip("\n") + "\n", encoding="utf-8")


def _build_review_payload(
    *,
    run_dir: Path,
    config: AgentLedgerConfig,
    history_limit: int,
    allow_warnings: bool,
    output_path: Path | None = None,
) -> dict:
    result = build_check(run_dir, _check_policy_from_config(config))
    paths = _review_paths(run_dir)
    history = _review_history(run_dir, history_limit)
    comparison = _review_previous_comparison(run_dir)
    exit_code = check_exit_code(result["status"], allow_warnings)
    return {
        "schema_version": "agentledger.review.v1",
        "status": result["status"],
        "ok": result["ok"],
        "summary": result["summary"],
        "run_dir": result["run_dir"],
        "command_exit_code": result.get("exit_code"),
        "paths": paths,
        "history": history,
        "comparison": comparison,
        "check": result,
        "output": str(output_path) if output_path is not None else None,
        "review_exit_code": exit_code,
    }


def _handle_review(args: argparse.Namespace) -> int:
    if args.history_limit < 0:
        print("--history-limit must be zero or greater.")
        return 2
    run_dir = _load_review_run_dir(args)
    if run_dir is None:
        return 2
    try:
        config = _load_check_config(args, run_dir)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    allow_warnings = _allow_warnings_from_config(args, config)
    output_path = Path(args.output).expanduser().resolve() if getattr(args, "output", None) else None
    payload = _build_review_payload(
        run_dir=run_dir,
        config=config,
        history_limit=args.history_limit,
        allow_warnings=allow_warnings,
        output_path=output_path,
    )
    result = payload["check"]
    paths = payload["paths"]
    history = payload["history"]
    comparison = payload["comparison"]
    exit_code = int(payload["review_exit_code"])
    output_format = getattr(args, "format", "text")
    if output_format == "json":
        rendered = json.dumps(payload, indent=2)
    elif output_format == "markdown":
        rendered = _format_review_markdown(result, paths, history, comparison)
    else:
        rendered = _format_review(result, paths, history, comparison)
    if output_path is not None:
        try:
            _write_rendered_output(output_path, rendered)
        except OSError as exc:
            print(f"Unable to write review output {output_path}: {exc}")
            return 2
    print(rendered)
    return exit_code


_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/][^\s`\"'<>|{}()[\]]+")
_POSIX_LOCAL_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:tmp|var/tmp|private/tmp|home|Users|mnt|workspace|workspaces)/[^\s`\"'<>|{}()[\]]+")


def _share_safe_path_replacements(paths: dict[str, Path | None]) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    seen: set[str] = set()
    for marker, path in paths.items():
        if path is None:
            continue
        variants = {str(path), str(path).replace("\\", "/")}
        try:
            resolved = path.resolve()
            variants.add(str(resolved))
            variants.add(str(resolved).replace("\\", "/"))
        except OSError:
            pass
        for variant in variants:
            if not variant or variant in seen:
                continue
            seen.add(variant)
            replacements.append((variant, marker))
    return sorted(replacements, key=lambda item: len(item[0]), reverse=True)


def _redact_share_safe_text(text: str, replacements: list[tuple[str, str]]) -> str:
    redacted = text
    for raw_path, marker in replacements:
        redacted = redacted.replace(raw_path, marker)
    redacted = _WINDOWS_ABSOLUTE_PATH_RE.sub("[redacted-local-path]", redacted)
    return _POSIX_LOCAL_PATH_RE.sub("[redacted-local-path]", redacted)


def _redact_share_safe_value(value: object, replacements: list[tuple[str, str]]) -> object:
    if isinstance(value, dict):
        return {key: _redact_share_safe_value(item, replacements) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_share_safe_value(item, replacements) for item in value]
    if isinstance(value, str):
        return _redact_share_safe_text(value, replacements)
    return value


def _share_safe_alpha_handoff_payload(
    payload: dict,
    *,
    repo: Path,
    out_root: Path | None,
    latest_dir: Path | None,
    output_dir: Path,
) -> dict:
    replacements = _share_safe_path_replacements(
        {
            "[latest-run]": latest_dir,
            "[agentledger-output]": out_root,
            "[handoff-output]": output_dir,
            "[repo]": repo,
        }
    )
    redacted = _redact_share_safe_value(payload, replacements)
    return redacted if isinstance(redacted, dict) else {}


def _alpha_handoff_error(
    args: argparse.Namespace,
    *,
    repo: Path | None,
    output_dir: Path | None,
    errors: list[str],
    out_root: Path | None = None,
) -> int:
    share_safe = bool(getattr(args, "share_safe", False))
    if getattr(args, "format", "text") == "json":
        payload = {
            "schema_version": ALPHA_HANDOFF_SCHEMA,
            "ok": False,
            "status": "unknown",
            "summary": "Alpha handoff could not be written.",
            "generated_at": utc_now_iso(),
            "agentledger_version": f"agentledger {__version__}",
            "repo": str(repo) if repo is not None else None,
            "out": str(out_root) if out_root is not None else None,
            "latest_run": None,
            "output_dir": str(output_dir) if output_dir is not None else None,
            "files": {},
            "share_safe": share_safe,
            "redactions": _alpha_handoff_redactions(share_safe),
            "review": None,
            "status_payload": None,
            "feedback_summary": None,
            "alpha_summary": None,
            "handling": _alpha_handoff_handling(share_safe),
            "next_actions": ["Fix the reported handoff errors, then run agentledger alpha-handoff again."],
            "errors": errors,
        }
        if share_safe and repo is not None and output_dir is not None:
            payload = _share_safe_alpha_handoff_payload(
                payload,
                repo=repo,
                out_root=out_root,
                latest_dir=None,
                output_dir=output_dir,
            )
        print(json.dumps(payload, indent=2))
    else:
        messages = errors
        if share_safe and repo is not None and output_dir is not None:
            replacements = _share_safe_path_replacements(
                {
                    "[agentledger-output]": out_root,
                    "[handoff-output]": output_dir,
                    "[repo]": repo,
                }
            )
            messages = [_redact_share_safe_text(message, replacements) for message in errors]
        for message in messages:
            print(message)
    return 2


def _alpha_handoff_redactions(share_safe: bool) -> dict[str, object]:
    return {
        "local_paths": share_safe,
        "markers": ["[repo]", "[agentledger-output]", "[latest-run]", "[handoff-output]"] if share_safe else [],
        "note": (
            "Local absolute paths are replaced with stable markers for sharing."
            if share_safe
            else "Local absolute paths are preserved; review before sharing."
        ),
    }


def _alpha_handoff_handling(share_safe: bool = False) -> dict[str, object]:
    return {
        "raw_evidence_copied": False,
        "copied_files": [],
        "share_safe": share_safe,
        "local_paths_redacted": share_safe,
        "omits": [
            ".agentledger run folders",
            "zip evidence bundles",
            "command transcript files",
            "diff files",
            "signing keys",
        ],
        "do_not_commit": [
            ".agentledger/",
            "*.zip",
            "signing keys",
            "unreviewed handoff packets",
        ],
    }


def _alpha_summary_for_handoff(out_root: Path) -> dict:
    summary_path = (out_root / ALPHA_SUMMARY_FILENAME).resolve()
    if not summary_path.exists():
        return {
            "available": False,
            "summary_file": str(summary_path),
            "payload": None,
            "errors": [],
        }
    payload, load_errors = _load_alpha_summary(summary_path)
    validation_errors = _validate_alpha_summary(payload) if payload is not None else []
    errors = load_errors + validation_errors
    return {
        "available": not errors,
        "summary_file": str(summary_path),
        "payload": payload if not errors else None,
        "errors": errors,
    }


def _alpha_handoff_next_actions(status_payload: dict, feedback_summary: dict, strict: bool) -> list[str]:
    actions = [str(action) for action in status_payload.get("next_actions") or []]
    if int(feedback_summary.get("total_entries") or 0) > 0:
        actions.append("Review feedback entries before sharing the handoff packet.")
    if strict and status_payload.get("status") == "warn":
        actions.append("Resolve warnings or rerun alpha-handoff without --strict for a warning-tolerant handoff.")
    actions.append("Share only the handoff Markdown/JSON after review; do not attach raw .agentledger evidence unless requested.")
    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped


def _format_alpha_handoff_markdown(payload: dict) -> str:
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    status_payload = payload.get("status_payload") if isinstance(payload.get("status_payload"), dict) else {}
    feedback = payload.get("feedback_summary") if isinstance(payload.get("feedback_summary"), dict) else {}
    alpha_summary = payload.get("alpha_summary") if isinstance(payload.get("alpha_summary"), dict) else {}
    paths = review.get("paths") if isinstance(review.get("paths"), dict) else {}
    comparison = review.get("comparison") if isinstance(review.get("comparison"), dict) else {}
    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []

    lines = [
        "# AgentLedger Alpha Handoff",
        "",
        f"- Status: {payload.get('status') or 'unknown'}",
        f"- Summary: {payload.get('summary') or 'No summary.'}",
        f"- Generated: {payload.get('generated_at')}",
        f"- Repo: {_markdown_inline(payload.get('repo') or 'n/a')}",
        f"- Evidence output: {_markdown_inline(payload.get('out') or 'n/a')}",
        f"- Latest run: {_markdown_inline(payload.get('latest_run') or 'n/a')}",
        "",
        "## Packet Files",
        "",
    ]
    files = payload.get("files") if isinstance(payload.get("files"), dict) else {}
    for label in ("markdown", "json"):
        if files.get(label):
            lines.append(f"- {label}: {_markdown_inline(files[label])}")

    lines.extend(
        [
            "",
            "## Review",
            "",
            f"- Review status: {review.get('status') or 'unknown'}",
            f"- Review exit code: {review.get('review_exit_code') if review.get('review_exit_code') is not None else 'n/a'}",
        ]
    )
    if paths:
        lines.extend(
            [
                f"- Markdown report: {_markdown_inline(paths.get('markdown') or 'n/a')}",
                f"- JSON report: {_markdown_inline(paths.get('json') or 'n/a')}",
                f"- HTML report: {_markdown_inline(paths.get('html') or 'n/a')}",
            ]
        )
        if paths.get("zip"):
            lines.append(f"- Zip bundle: {_markdown_inline(paths['zip'])}")
    if comparison.get("available") is True and isinstance(comparison.get("compare"), dict):
        compare_payload = comparison["compare"]
        changed = compare_payload.get("changed_files") if isinstance(compare_payload.get("changed_files"), dict) else {}
        lines.extend(
            [
                "",
                "## Previous Comparison",
                "",
                f"- Previous run: {_markdown_inline(comparison.get('previous_run') or 'n/a')}",
                f"- Changed files: {changed.get('old', 'n/a')} -> {changed.get('new', 'n/a')} ({changed.get('delta_text', 'n/a')})",
            ]
        )

    lines.extend(
        [
            "",
            "## Status",
            "",
            f"- Status command exit code: {status_payload.get('status_exit_code') if status_payload.get('status_exit_code') is not None else 'n/a'}",
        ]
    )
    status_feedback = status_payload.get("feedback") if isinstance(status_payload.get("feedback"), dict) else {}
    lines.append(
        f"- Latest feedback count: {status_feedback.get('latest_run_entries', 0)} "
        f"of {status_feedback.get('total_entries', 0)} total entries"
    )

    lines.extend(
        [
            "",
            "## Feedback",
            "",
            (
                f"- Entries: {feedback.get('returned_entries', 0)} shown / "
                f"{feedback.get('total_entries', 0)} total across {feedback.get('runs_with_feedback', 0)} runs"
            ),
        ]
    )
    entries = feedback.get("entries") if isinstance(feedback.get("entries"), list) else []
    if entries:
        lines.append("- Recent feedback:")
        for entry in entries:
            lines.append(f"  - {_format_feedback_summary_entry(entry).removeprefix('- ')}")
    else:
        lines.append("- Recent feedback: none")

    lines.extend(
        [
            "",
            "## Alpha Summary",
            "",
            f"- Available: {'yes' if alpha_summary.get('available') else 'no'}",
            f"- Summary file: {_markdown_inline(alpha_summary.get('summary_file') or 'n/a')}",
        ]
    )
    if alpha_summary.get("errors"):
        lines.append("- Alpha summary errors:")
        for error in alpha_summary["errors"]:
            lines.append(f"  - {error}")

    lines.extend(["", "## Handling", ""])
    handling = payload.get("handling") if isinstance(payload.get("handling"), dict) else {}
    lines.append(f"- Raw evidence copied: {'yes' if handling.get('raw_evidence_copied') else 'no'}")
    for item in handling.get("omits") or []:
        lines.append(f"- Omits: {item}")

    if next_actions:
        lines.extend(["", "## Next", ""])
        for action in next_actions:
            lines.append(f"- {action}")
    if errors:
        lines.extend(["", "## Errors", ""])
        for error in errors:
            lines.append(f"- {error}")
    return "\n".join(lines)


def _handle_alpha_handoff(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    if args.feedback_limit <= 0:
        return _alpha_handoff_error(args, repo=repo, output_dir=output_dir, errors=["--feedback-limit must be greater than zero."])
    if args.history_limit < 0:
        return _alpha_handoff_error(args, repo=repo, output_dir=output_dir, errors=["--history-limit must be zero or greater."])
    if output_dir.exists() and not output_dir.is_dir():
        return _alpha_handoff_error(args, repo=repo, output_dir=output_dir, errors=[f"Output path is not a directory: {output_dir}"])

    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        return _alpha_handoff_error(args, repo=repo, output_dir=output_dir, errors=[f"Config error: {exc}"])
    out_root = _resolve_out_root(args, repo, config)
    latest_dir, latest_errors = _resolve_latest_run_dir(out_root)
    if latest_dir is None:
        return _alpha_handoff_error(args, repo=repo, output_dir=output_dir, out_root=out_root, errors=latest_errors)

    allow_warnings = not args.strict
    status_payload = _build_status_payload_for_latest(
        repo=repo,
        out_root=out_root,
        latest_dir=latest_dir,
        config=config,
        feedback_limit=args.feedback_limit,
        allow_warnings=allow_warnings,
    )
    review_payload = _build_review_payload(
        run_dir=latest_dir,
        config=config,
        history_limit=args.history_limit,
        allow_warnings=allow_warnings,
    )
    try:
        feedback_summary = summarize_feedback(out_root=out_root, limit=args.feedback_limit)
    except FeedbackError as exc:
        feedback_summary = {
            "schema_version": FEEDBACK_SUMMARY_SCHEMA,
            "ok": False,
            "out": str(out_root),
            "filters": {"category": None, "severity": None, "limit": args.feedback_limit},
            "total_entries": 0,
            "returned_entries": 0,
            "run_count": 0,
            "runs_with_feedback": 0,
            "categories": {},
            "severities": {},
            "runs": [],
            "entries": [],
            "errors": [str(exc)],
        }
    alpha_summary = _alpha_summary_for_handoff(out_root)
    errors = [str(error) for error in status_payload.get("errors") or []]
    if not feedback_summary.get("ok", False):
        errors.extend(str(error) for error in feedback_summary.get("errors") or [])
    errors.extend(str(error) for error in alpha_summary.get("errors") or [])
    status_exit_value = status_payload.get("status_exit_code")
    review_exit_value = review_payload.get("review_exit_code")
    status_exit_code = int(status_exit_value) if status_exit_value is not None else 2
    review_exit_code = int(review_exit_value) if review_exit_value is not None else 2
    if review_exit_code != status_exit_code and review_exit_code != 0:
        errors.append(f"Review exited {review_exit_code}; status exited {status_exit_code}.")

    markdown_path = output_dir / ALPHA_HANDOFF_MARKDOWN
    json_path = output_dir / ALPHA_HANDOFF_JSON
    next_actions = _alpha_handoff_next_actions(status_payload, feedback_summary, args.strict)
    ok = not errors and status_exit_code == 0 and review_exit_code == 0
    payload = {
        "schema_version": ALPHA_HANDOFF_SCHEMA,
        "ok": ok,
        "status": status_payload.get("status") or "unknown",
        "summary": (status_payload.get("check") or {}).get("summary") or "No status summary.",
        "generated_at": utc_now_iso(),
        "agentledger_version": f"agentledger {__version__}",
        "repo": str(repo),
        "out": str(out_root),
        "latest_run": str(latest_dir),
        "output_dir": str(output_dir),
        "files": {
            "markdown": str(markdown_path),
            "json": str(json_path),
        },
        "share_safe": bool(args.share_safe),
        "redactions": _alpha_handoff_redactions(bool(args.share_safe)),
        "review": review_payload,
        "status_payload": status_payload,
        "feedback_summary": feedback_summary,
        "alpha_summary": alpha_summary,
        "handling": _alpha_handoff_handling(bool(args.share_safe)),
        "next_actions": next_actions,
        "errors": errors,
    }
    if args.share_safe:
        payload = _share_safe_alpha_handoff_payload(
            payload,
            repo=repo,
            out_root=out_root,
            latest_dir=latest_dir,
            output_dir=output_dir,
        )
    markdown = _format_alpha_handoff_markdown(payload)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        _write_rendered_output(markdown_path, markdown)
        _write_rendered_output(json_path, json.dumps(payload, indent=2))
    except OSError as exc:
        return _alpha_handoff_error(
            args,
            repo=repo,
            output_dir=output_dir,
            out_root=out_root,
            errors=[f"Unable to write alpha handoff packet in {output_dir}: {exc}"],
        )

    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(f"Alpha handoff written: {output_dir}")
        print(f"Markdown: {markdown_path}")
        print(f"JSON: {json_path}")
        print(f"Share-safe: {'yes' if args.share_safe else 'no'}")
        print(f"Status: {payload['status']}")
        print(f"Summary: {payload['summary']}")
        print("Raw evidence copied: no")
        print("Next:")
        for action in next_actions:
            print(f"- {action}")
    return 0 if ok else 2


def _parse_json_object_from_output(output: str) -> dict | None:
    start = output.find("{")
    end = output.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        payload = json.loads(output[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _path_variants_for_validation(path: Path) -> set[str]:
    variants = {str(path), str(path).replace("\\", "/")}
    try:
        resolved = path.resolve()
        variants.add(str(resolved))
        variants.add(str(resolved).replace("\\", "/"))
    except OSError:
        pass
    return {variant for variant in variants if variant}


def _pack_alpha_validation(
    *,
    markdown_path: Path,
    json_path: Path,
    local_paths: dict[str, Path],
) -> dict:
    errors: list[str] = []
    contents: list[str] = []
    checked_files = {"markdown": str(markdown_path), "json": str(json_path)}
    for label, path in checked_files.items():
        file_path = Path(path)
        if not file_path.exists():
            errors.append(f"Missing generated {label} packet: {file_path}")
            continue
        try:
            contents.append(file_path.read_text(encoding="utf-8-sig"))
        except OSError as exc:
            errors.append(f"Unable to read generated {label} packet {file_path}: {exc}")

    combined = "\n".join(contents)
    for label, path in local_paths.items():
        for variant in sorted(_path_variants_for_validation(path), key=len, reverse=True):
            if variant in combined:
                errors.append(f"Packet leaks local {label} path: {variant}")
                break

    for match in sorted(set(_WINDOWS_ABSOLUTE_PATH_RE.findall(combined))):
        errors.append(f"Packet contains local absolute path: {match}")
    for match in sorted(set(_POSIX_LOCAL_PATH_RE.findall(combined))):
        errors.append(f"Packet contains local absolute path: {match}")

    return {
        "ok": not errors,
        "checked_files": checked_files,
        "checks": [
            "generated Markdown packet exists",
            "generated JSON packet exists",
            "known local roots are absent",
            "Windows absolute paths are absent",
            "common local POSIX paths are absent",
        ],
        "errors": errors,
    }


def _pack_alpha_next_actions(handoff_payload: dict | None, validation: dict, handoff_exit_code: int) -> list[str]:
    actions: list[str] = []
    if not validation.get("ok"):
        actions.append("Fix packet validation errors before sharing the alpha packet.")
    if handoff_exit_code != 0:
        actions.append("Review handoff errors or rerun without --strict when warnings are acceptable.")
    if isinstance(handoff_payload, dict) and handoff_payload.get("status") == "warn":
        actions.append("Review warning rules before sending the packet.")
    actions.append("Send only the listed Markdown and JSON packet files; do not attach raw .agentledger evidence.")
    deduped: list[str] = []
    for action in actions:
        if action not in deduped:
            deduped.append(action)
    return deduped


def _handle_pack_alpha(args: argparse.Namespace) -> int:
    repo = Path(args.repo or ".").resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    handoff_args = argparse.Namespace(
        command_name="alpha-handoff",
        repo=args.repo,
        config=args.config,
        out=args.out,
        output_dir=args.output_dir,
        feedback_limit=args.feedback_limit,
        history_limit=args.history_limit,
        strict=args.strict,
        share_safe=True,
        format="json",
    )
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        handoff_exit_code = _handle_alpha_handoff(handoff_args)
    handoff_output = buffer.getvalue()
    handoff_payload = _parse_json_object_from_output(handoff_output)

    markdown_path = output_dir / ALPHA_HANDOFF_MARKDOWN
    json_path = output_dir / ALPHA_HANDOFF_JSON
    local_paths = {
        "repo": repo,
        "handoff output": output_dir,
    }
    if args.out:
        local_paths["evidence output"] = Path(args.out).expanduser().resolve()
    validation = _pack_alpha_validation(
        markdown_path=markdown_path,
        json_path=json_path,
        local_paths=local_paths,
    )
    handoff_errors = []
    if isinstance(handoff_payload, dict):
        handoff_errors = [str(error) for error in handoff_payload.get("errors") or []]
    elif handoff_exit_code != 0:
        handoff_errors = ["Unable to parse alpha-handoff JSON output."]
    errors = handoff_errors + [str(error) for error in validation.get("errors") or []]
    ok = handoff_exit_code == 0 and validation.get("ok") is True
    files = {"markdown": str(markdown_path), "json": str(json_path)}
    payload = {
        "schema_version": PACK_ALPHA_SCHEMA,
        "ok": ok,
        "status": handoff_payload.get("status") if isinstance(handoff_payload, dict) else "unknown",
        "summary": handoff_payload.get("summary") if isinstance(handoff_payload, dict) else "Alpha packet could not be generated.",
        "generated_at": utc_now_iso(),
        "agentledger_version": f"agentledger {__version__}",
        "repo": str(repo),
        "output_dir": str(output_dir),
        "files": files,
        "raw_evidence_copied": False,
        "handoff_exit_code": handoff_exit_code,
        "handoff": handoff_payload,
        "validation": validation,
        "next_actions": _pack_alpha_next_actions(handoff_payload, validation, handoff_exit_code),
        "errors": errors,
    }

    if getattr(args, "format", "text") == "json":
        print(json.dumps(payload, indent=2))
    else:
        print(f"AgentLedger alpha packet: {payload['status']}")
        print(f"Summary: {payload['summary']}")
        print(f"Markdown to share: {markdown_path}")
        print(f"JSON to share: {json_path}")
        print("Raw evidence copied: no")
        print(f"Packet validation: {'pass' if validation.get('ok') else 'fail'}")
        if errors:
            print("Errors:")
            for error in errors:
                print(f"- {error}")
        print("Next:")
        for action in payload["next_actions"]:
            print(f"- {action}")
    return 0 if ok else 2


def _run_task(command: list[str], repo: Path, artifacts_dir: Path) -> CommandResult:
    started = utc_now_iso()
    try:
        result = run_capture(command, repo)
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired as exc:
        exit_code = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or "Command timed out."
    ended = utc_now_iso()
    redacted_stdout = redact_text(stdout)
    redacted_stderr = redact_text(stderr)
    transcripts = artifacts_dir / "command"
    transcripts.mkdir(parents=True, exist_ok=True)
    stdout_path = transcripts / "stdout.txt"
    stderr_path = transcripts / "stderr.txt"
    stdout_path.write_text(redacted_stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(redacted_stderr, encoding="utf-8", errors="replace")
    test_detected, test_framework = detect_test_command(command)
    return CommandResult(
        command=redact_command(command),
        cwd=str(repo),
        started_at=started,
        ended_at=ended,
        exit_code=exit_code,
        stdout_tail=tail_text(redacted_stdout),
        stderr_tail=tail_text(redacted_stderr),
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        test_detected=test_detected,
        test_framework=test_framework,
    )


def _run_task_with_privacy(command: list[str], repo: Path, artifacts_dir: Path, privacy_mode: str) -> CommandResult:
    result = _run_task(command, repo, artifacts_dir)
    if privacy_mode != "summary":
        return result

    stdout_path = Path(result.stdout_path) if result.stdout_path else None
    stderr_path = Path(result.stderr_path) if result.stderr_path else None
    if stdout_path:
        stdout_path.write_text(f"Command stdout {PRIVACY_OMISSION}.\n", encoding="utf-8")
    if stderr_path:
        stderr_path.write_text(f"Command stderr {PRIVACY_OMISSION}.\n", encoding="utf-8")
    result.stdout_tail = ""
    result.stderr_tail = ""
    return result


def _apply_privacy_mode(report: LedgerReport, privacy_mode: str) -> None:
    if privacy_mode != "summary":
        return
    report.before.diff = ""
    report.after.diff = ""
    report.warnings.append(
        "Privacy mode summary omitted command transcript content and full diffs from reports and bundles."
    )


def _capture(args: argparse.Namespace, task: list[str] | None) -> int:
    repo = Path(args.repo).resolve()
    try:
        config = _load_cli_config(args, repo)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    out_root = _resolve_out_root(args, repo, config)
    privacy_mode = args.privacy_mode or config.privacy_mode or DEFAULT_PRIVACY_MODE
    skip_repomori = getattr(args, "no_repomori", False) or config.repomori is False
    skip_jester = getattr(args, "no_jester", False) or config.jester is False
    skip_tokometer = getattr(args, "no_tokometer", False) or config.tokometer is False
    skip_zip = getattr(args, "no_zip", False) or config.zip is False
    has_jester = hasattr(args, "no_jester")
    run_id = f"{utc_now_iso().replace(':', '').replace('+', 'Z')}-{uuid.uuid4().hex[:8]}"
    run_dir = out_root / run_id
    artifacts_dir = run_dir / "artifacts"
    run_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    artifacts = []
    started = utc_now_iso()
    before = snapshot(repo)
    privacy_summary = privacy_mode == "summary"

    if not skip_repomori and not privacy_summary:
        artifacts.append(run_repomori_snapshot(repo, artifacts_dir, "before"))
    elif privacy_summary and not skip_repomori:
        warnings.append("Privacy mode summary skipped RepoMori snapshots.")

    command_result = None
    command = _clean_task(task or [])
    if command:
        command_result = _run_task_with_privacy(command, repo, artifacts_dir, privacy_mode)
    elif task is not None:
        warnings.append("No command supplied after --; captured repository state only.")

    after = snapshot(repo)

    if not skip_repomori and not privacy_summary:
        artifacts.append(run_repomori_snapshot(repo, artifacts_dir, "after"))
    if not skip_jester and has_jester and not privacy_summary:
        artifacts.append(run_jester_diff(repo, artifacts_dir))
    elif privacy_summary and not skip_jester and has_jester:
        warnings.append("Privacy mode summary skipped Jester diff gate.")
    if not skip_tokometer and not privacy_summary:
        artifacts.append(read_tokometer_usage(artifacts_dir))
    elif privacy_summary and not skip_tokometer:
        warnings.append("Privacy mode summary skipped Tokometer path evidence.")

    ended = utc_now_iso()
    report = LedgerReport(
        schema_version="agentledger.report.v1",
        run_id=run_id,
        started_at=started,
        ended_at=ended,
        target_repo=str(repo),
        command=command_result,
        before=before,
        after=after,
        privacy_mode=privacy_mode,
        artifacts=artifacts,
        warnings=warnings,
    )
    _apply_privacy_mode(report, privacy_mode)
    write_json(report, run_dir / "agentledger-report.json")
    write_markdown(report, run_dir / "agentledger-report.md")
    write_html(report, run_dir / "agentledger-report.html")
    if not skip_zip:
        bundle_path = write_zip_bundle(run_dir)
        print(f"AgentLedger bundle: {bundle_path}")
    latest = out_root / "latest.txt"
    latest.write_text(str(run_dir), encoding="utf-8")

    print(f"AgentLedger report: {run_dir / 'agentledger-report.md'}")
    if command_result and command_result.exit_code != 0:
        return command_result.exit_code
    blocking = [
        artifact
        for artifact in artifacts
        if artifact.name == "jester_diff" and not artifact.ok and artifact.exit_code is not None
    ]
    return 2 if blocking else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command_name == "contracts":
        if args.format == "json":
            print(json.dumps(build_contracts_payload(__version__), indent=2))
        else:
            print(format_contracts_text(__version__))
        return 0
    if args.command_name == "run":
        return _capture(args, args.task)
    if args.command_name == "snapshot":
        return _capture(args, None)
    if args.command_name == "doctor":
        report = run_doctor(Path(args.repo).resolve() if args.repo else None)
        print(doctor_json(report) if args.json else format_doctor(report))
        return 0 if report["status"] == "ready" else 2
    if args.command_name == "inspect-report":
        return _handle_inspect_report(args)
    if args.command_name == "open-latest":
        return _handle_open_latest(args)
    if args.command_name == "history":
        return _handle_history(args)
    if args.command_name == "status":
        return _handle_status(args)
    if args.command_name == "alpha-guide":
        return _handle_alpha_guide(args)
    if args.command_name == "alpha":
        return _handle_alpha(args)
    if args.command_name == "alpha-summary":
        return _handle_alpha_summary(args)
    if args.command_name == "alpha-handoff":
        return _handle_alpha_handoff(args)
    if args.command_name == "pack-alpha":
        return _handle_pack_alpha(args)
    if args.command_name == "feedback":
        return _handle_feedback(args)
    if args.command_name == "feedback-summary":
        return _handle_feedback_summary(args)
    if args.command_name == "feedback-export":
        return _handle_feedback_export(args)
    if args.command_name == "review":
        return _handle_review(args)
    if args.command_name == "compare":
        return _handle_compare(args)
    if args.command_name == "check":
        return _handle_check(args)
    if args.command_name == "init-config":
        return _handle_init_config(args)
    if args.command_name == "signing-key":
        return _handle_signing_key(args)
    if args.command_name == "inspect-bundle":
        return _handle_inspect_bundle(args)
    if args.command_name == "verify-bundle":
        return _handle_verify_bundle(args)
    if args.command_name == "sign-bundle":
        return _handle_sign_bundle(args)
    parser.error("unknown command")
    return 2
