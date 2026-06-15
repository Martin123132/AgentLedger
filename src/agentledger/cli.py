from __future__ import annotations

import argparse
import contextlib
import io
import json
import platform
import subprocess
import sys
import uuid
from zipfile import BadZipFile, ZipFile
from pathlib import Path

from . import __version__
from .bundle import (
    BundleError,
    find_bundle_signature_member,
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
ALPHA_SUMMARY_SCHEMA = "agentledger.alpha_summary.v1"
ALPHA_SUMMARY_FILENAME = "alpha-summary.json"
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
    review.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
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


def _handle_compare(args: argparse.Namespace) -> int:
    old_dir = Path(args.old_run_dir).resolve()
    new_dir = Path(args.new_run_dir).resolve()
    try:
        old_report = load_report(old_dir)
        new_report = load_report(new_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"Unable to read report: {exc}")
        return 2

    old_changed = changed_file_count(old_report)
    new_changed = changed_file_count(new_report)
    old_exit = command_exit_code(old_report)
    new_exit = command_exit_code(new_report)
    old_passed, old_warned = artifact_status_counts([artifact for artifact in old_report.get("artifacts", []) if isinstance(artifact, dict)])
    new_passed, new_warned = artifact_status_counts([artifact for artifact in new_report.get("artifacts", []) if isinstance(artifact, dict)])
    changed_delta = new_changed - old_changed
    changed_delta_text = f"+{changed_delta}" if changed_delta > 0 else str(changed_delta)
    trend = command_exit_trend(old_exit, new_exit)
    old_tokometer = tokometer_summary(old_report)
    new_tokometer = tokometer_summary(new_report)
    old_privacy = str(old_report.get("privacy_mode") or "standard")
    new_privacy = str(new_report.get("privacy_mode") or "standard")

    if getattr(args, "format", "text") == "json":
        print(
            json.dumps(
                {
                    "schema_version": "agentledger.compare.v1",
                    "changed_files": {
                        "old": old_changed,
                        "new": new_changed,
                        "delta": changed_delta,
                        "delta_text": changed_delta_text,
                    },
                    "exit_code": {
                        "old": old_exit,
                        "new": new_exit,
                        "trend": trend,
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
                        "old": old_privacy,
                        "new": new_privacy,
                    },
                },
                indent=2,
            )
        )
        return 0

    print(f"Comparing reports:")
    print(f"Old: {old_dir}")
    print(f"New: {new_dir}")
    print(f"Old command: {report_command_text(old_report)}")
    print(f"New command: {report_command_text(new_report)}")
    print(f"Changed files: {old_changed} -> {new_changed} ({changed_delta_text})")
    print(
        "Exit code: "
        f"{old_exit if old_exit is not None else 'n/a'} -> {new_exit if new_exit is not None else 'n/a'} "
        f"({trend})"
    )
    print(
        f"Artifacts: {old_passed} ok/{old_warned} warn -> "
        f"{new_passed} ok/{new_warned} warn"
    )
    if old_tokometer or new_tokometer:
        print(f"Tokometer: {old_tokometer or 'n/a'} -> {new_tokometer or 'n/a'}")
    print(f"Test framework: {command_test_framework(old_report)} -> {command_test_framework(new_report)}")
    print(f"Privacy mode: {old_privacy} -> {new_privacy}")
    return 0


def _bundle_manifest_summary(member: str | None, manifest: dict) -> dict[str, object]:
    return {
        "member": member,
        "schema_version": manifest.get("schema_version"),
        "digest_algorithm": manifest.get("digest_algorithm"),
        "file_count": manifest.get("file_count"),
        "run_id": manifest.get("run_id"),
    }


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
    try:
        key = _read_signature_key(Path(args.key_file))
        output = Path(args.output).resolve() if args.output else None
        signed_path, signature_member, signature = sign_zip_bundle(Path(args.bundle), key, output)
    except BundleError as exc:
        print(f"Unable to sign bundle: {exc}")
        return 2
    except OSError as exc:
        print(f"Unable to sign bundle: {exc}")
        return 2
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

    run_dirs = sorted(
        [
            child
            for child in out_root.iterdir()
            if child.is_dir() and (child / "agentledger-report.json").exists()
        ],
        key=lambda path: path.name,
        reverse=True,
    )[: args.limit]

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

    paths = _latest_paths(latest_dir)
    missing_reports = _missing_report_paths(latest_dir)
    check = build_check(latest_dir, _check_policy_from_config(config))
    feedback_errors: list[str] = []
    try:
        feedback_summary = summarize_feedback(out_root=out_root, limit=args.feedback_limit)
        feedback = _status_feedback(feedback_summary, latest_dir)
        feedback_errors = feedback["errors"]
    except FeedbackError as exc:
        feedback_errors = [str(exc)]
        feedback = _empty_status_feedback(feedback_errors)

    status = str(check.get("status") or "unknown")
    errors = missing_reports + feedback_errors
    status_exit_code = 2 if errors else check_exit_code(status, _allow_warnings_from_config(args, config))
    next_actions = _status_next_actions(status, feedback, errors)
    payload = _status_payload(
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


def _handle_alpha(args: argparse.Namespace) -> int:
    output_format = getattr(args, "format", "text")
    quiet = output_format == "json"
    repo = Path(args.repo or ".").resolve()
    started_at = utc_now_iso()
    errors: list[str] = []

    try:
        config = _load_output_config(args, repo)
    except ConfigError as exc:
        message = f"Config error: {exc}"
        if quiet:
            print(
                json.dumps(
                    {
                        "schema_version": ALPHA_SUMMARY_SCHEMA,
                        "ok": False,
                        "summary_file": None,
                        "errors": [message],
                    },
                    indent=2,
                )
            )
        else:
            print(message)
        return 2

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
        errors.append("Doctor check did not report ready.")

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
    ended_at = utc_now_iso()
    status_exit_code = int(status_payload.get("status_exit_code") or status_exit)
    ok = not errors and status_exit_code == 0
    payload = {
        "schema_version": ALPHA_SUMMARY_SCHEMA,
        "ok": ok,
        "summary_file": str(summary_path),
        "started_at": started_at,
        "ended_at": ended_at,
        "repo": str(repo),
        "out": str(out_root),
        "latest_run": str(latest_dir) if latest_dir is not None else None,
        "bundle": str(latest_dir.with_suffix(".zip")) if latest_dir is not None else None,
        "agentledger_version": f"agentledger {__version__}",
        "python_version": f"Python {platform.python_version()}",
        "git_version": _git_version(),
        "doctor": doctor_summary,
        "status": status,
        "status_summary": status_summary,
        "status_exit_code": status_exit_code,
        "report_paths": report_paths,
        "feedback": feedback,
        "next_actions": next_actions,
        "errors": errors,
    }
    _write_alpha_summary(summary_path, payload)

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
    if "report_paths" in payload and not isinstance(payload.get("report_paths"), dict):
        errors.append("Alpha summary field report_paths must be an object.")
    if "feedback" in payload and not isinstance(payload.get("feedback"), dict):
        errors.append("Alpha summary field feedback must be an object.")
    return errors


def _format_alpha_summary(path: Path, payload: dict) -> str:
    status = payload.get("status") or "unknown"
    status_summary = payload.get("status_summary") or "No status summary."
    feedback = payload.get("feedback") if isinstance(payload.get("feedback"), dict) else {}
    paths = payload.get("report_paths") if isinstance(payload.get("report_paths"), dict) else {}
    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []

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


def _format_review(result: dict, paths: dict[str, str | None]) -> str:
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

    if result["blocking_rules"]:
        lines.append("Blockers:")
        for rule in result["blocking_rules"]:
            lines.append(f"- {rule['id']}: {rule['message']}")
    if result["warning_rules"]:
        lines.append("Warnings:")
        for rule in result["warning_rules"]:
            lines.append(f"- {rule['id']}: {rule['message']}")

    if result["status"] == "block":
        next_line = "Fix blockers, rerun the command, then review again."
    elif result["status"] == "warn":
        next_line = "Read the Markdown report and warning rules before accepting the work."
    else:
        next_line = "Read the Markdown report, then keep or share only evidence you have reviewed."
    lines.extend(
        [
            "Next:",
            f"- {next_line}",
            "- Do not commit .agentledger folders or zip bundles.",
        ]
    )
    return "\n".join(lines)


def _handle_review(args: argparse.Namespace) -> int:
    run_dir = _load_review_run_dir(args)
    if run_dir is None:
        return 2
    try:
        config = _load_check_config(args, run_dir)
    except ConfigError as exc:
        print(f"Config error: {exc}")
        return 2
    policy = _check_policy_from_config(config)
    allow_warnings = _allow_warnings_from_config(args, config)
    result = build_check(run_dir, policy)
    paths = _review_paths(run_dir)
    exit_code = check_exit_code(result["status"], allow_warnings)
    if getattr(args, "format", "text") == "json":
        payload = {
            "schema_version": "agentledger.review.v1",
            "status": result["status"],
            "ok": result["ok"],
            "summary": result["summary"],
            "run_dir": result["run_dir"],
            "command_exit_code": result.get("exit_code"),
            "paths": paths,
            "check": result,
            "review_exit_code": exit_code,
        }
        print(json.dumps(payload, indent=2))
    else:
        print(_format_review(result, paths))
    return exit_code


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
    if args.command_name == "alpha":
        return _handle_alpha(args)
    if args.command_name == "alpha-summary":
        return _handle_alpha_summary(args)
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
    if args.command_name == "verify-bundle":
        return _handle_verify_bundle(args)
    if args.command_name == "sign-bundle":
        return _handle_sign_bundle(args)
    parser.error("unknown command")
    return 2
