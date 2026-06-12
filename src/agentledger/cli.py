from __future__ import annotations

import argparse
import json
import subprocess
import uuid
from zipfile import BadZipFile, ZipFile
from pathlib import Path

from . import __version__
from .bundle import write_zip_bundle
from .classify import detect_test_command
from .doctor import doctor_json, format_doctor, run_doctor
from .export import write_html, write_json, write_markdown
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentledger",
        description="Local-first black box recorder for AI coding-agent work.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command_name", required=True)

    run = sub.add_parser("run", help="Capture before/after repo state around a command.")
    run.add_argument("--repo", default=".", help="Target git repository.")
    run.add_argument("--out", default=".agentledger", help="Evidence output directory.")
    run.add_argument("--no-repomori", action="store_true", help="Skip RepoMori snapshot hooks.")
    run.add_argument("--no-jester", action="store_true", help="Skip Jester diff gate.")
    run.add_argument("--no-tokometer", action="store_true", help="Skip Tokometer path evidence.")
    run.add_argument("--no-zip", action="store_true", help="Skip zip bundle export.")
    run.add_argument("task", nargs=argparse.REMAINDER, help="Command to run after --.")

    snap = sub.add_parser("snapshot", help="Capture repository state without running a command.")
    snap.add_argument("--repo", default=".", help="Target git repository.")
    snap.add_argument("--out", default=".agentledger", help="Evidence output directory.")
    snap.add_argument("--no-repomori", action="store_true", help="Skip RepoMori snapshot hook.")
    snap.add_argument("--no-tokometer", action="store_true", help="Skip Tokometer path evidence.")
    snap.add_argument("--no-zip", action="store_true", help="Skip zip bundle export.")

    doctor = sub.add_parser("doctor", help="Check local AgentLedger integration readiness.")
    doctor.add_argument("--repo", default=None, help="Optional target git repository to validate.")
    doctor.add_argument("--json", action="store_true", help="Print machine-readable doctor report.")

    inspect = sub.add_parser("inspect-report", help="Print a concise summary of an existing run report folder.")
    inspect.add_argument("run_dir", help="Path to run directory.")
    inspect.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    latest = sub.add_parser("open-latest", help="Print latest report paths from a run output directory.")
    latest.add_argument("--out", default=".agentledger", help="Evidence output directory.")

    history = sub.add_parser("history", help="List recent AgentLedger runs from a run output directory.")
    history.add_argument("--out", default=".agentledger", help="Evidence output directory.")
    history.add_argument("--limit", type=int, default=10, help="Maximum number of runs to show.")
    history.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    compare = sub.add_parser("compare", help="Compare two report folders side by side.")
    compare.add_argument("old_run_dir", help="Path to older run directory.")
    compare.add_argument("new_run_dir", help="Path to newer run directory.")
    compare.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")

    verify = sub.add_parser("verify-bundle", help="Validate a zip evidence bundle.")
    verify.add_argument("bundle", help="Path to bundle zip file.")

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
            "run_dir": str(run_dir),
            "command": report_command_text(report),
            "exit_code": exit_code if exit_code is not None else None,
            "test_framework": test_framework,
            "changed_files": changed_files,
            "artifacts": {"ok": passed, "warn": warned},
            "tokometer": tokometer,
        }
        print(json.dumps(payload, indent=2))
        return 0

    print(f"Report: {run_dir / 'agentledger-report.json'}")
    print(f"Command: {report_command_text(report)}")
    print(f"Exit code: {exit_code if exit_code is not None else 'n/a'}")
    print(f"Test framework: {test_framework}")
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

    if getattr(args, "format", "text") == "json":
        print(
            json.dumps(
                {
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
    return 0


def _handle_verify_bundle(args: argparse.Namespace) -> int:
    zip_path = Path(args.bundle).resolve()
    if not zip_path.exists():
        print(f"Bundle not found: {zip_path}")
        return 2

    missing_members = []

    try:
        with ZipFile(zip_path, "r") as archive:
            members = archive.namelist()
            report_member = _find_bundle_member(members, "agentledger-report.json")
            if report_member is None:
                print(f"Missing agentledger-report.json in {zip_path}")
                return 2
            markdown_member = _find_bundle_member(members, "agentledger-report.md")
            html_member = _find_bundle_member(members, "agentledger-report.html")
            if markdown_member is None:
                missing_members.append("Missing markdown report in bundle.")
            if html_member is None:
                missing_members.append("Missing HTML report in bundle.")
            try:
                payload = json.loads(archive.read(report_member).decode("utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                print(f"Invalid JSON in {report_member}")
                return 2
            if not isinstance(payload, dict):
                print("Bundle report payload is not a JSON object")
                return 2
            if payload.get("schema_version") != "agentledger.report.v1":
                print(f"Unexpected report schema: {payload.get('schema_version')}")
                return 2
    except (OSError, BadZipFile):
        print(f"Unable to open zip file: {zip_path}")
        return 2

    if missing_members:
        for message in missing_members:
            print(message)
        return 2

    changed = changed_file_count(payload)
    passed, warned = artifact_status_counts([artifact for artifact in payload.get("artifacts", []) if isinstance(artifact, dict)])
    print(f"Bundle OK: {zip_path}")
    print(f"Run ID: {payload.get('run_id', '(missing run_id)')}")
    print(f"Report: {report_member}")
    print(f"Markdown: {markdown_member}")
    print(f"HTML: {html_member}")
    print(f"Command: {report_command_text(payload)}")
    print(f"Changed files: {changed}")
    print(f"Artifacts: {passed} ok, {warned} warn")
    return 0


def _handle_open_latest(args: argparse.Namespace) -> int:
    out_root = Path(args.out).resolve()
    latest_path = out_root / "latest.txt"
    if not out_root.exists():
        print(f"No AgentLedger output directory found: {out_root}")
        print(f"Run a capture first: python -m agentledger run --out {out_root} -- <command>")
        return 2
    if not latest_path.exists():
        print(f"No latest run pointer found: {latest_path}")
        print(f"Run a capture first: python -m agentledger run --out {out_root} -- <command>")
        return 2
    latest_value = latest_path.read_text(encoding="utf-8").strip()
    if not latest_value:
        print(f"Latest run pointer is empty: {latest_path}")
        print("Run another capture to refresh latest.txt.")
        return 2
    latest_dir = Path(latest_value)
    if not latest_dir.is_absolute():
        latest_dir = latest_dir if latest_dir.exists() else (out_root / latest_dir)
    if not latest_dir.exists():
        print(f"Latest report directory not found: {latest_dir}")
        print(f"latest.txt points to: {latest_value}")
        print("Run another capture to refresh latest.txt.")
        return 2

    markdown_path = latest_dir / "agentledger-report.md"
    json_path = latest_dir / "agentledger-report.json"
    html_path = latest_dir / "agentledger-report.html"
    missing_reports = [
        str(path)
        for path in (markdown_path, json_path, html_path)
        if not path.exists()
    ]

    print(f"Latest run: {latest_dir}")
    print(f"Markdown report: {markdown_path}")
    print(f"JSON report: {json_path}")
    print(f"HTML report: {html_path}")
    zip_path = latest_dir.with_suffix(".zip")
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
        "artifacts": {"ok": passed, "warn": warned},
        "markdown": str(run_dir / "agentledger-report.md"),
        "json": str(run_dir / "agentledger-report.json"),
        "html": str(run_dir / "agentledger-report.html"),
        "zip": str(run_dir.with_suffix(".zip")) if run_dir.with_suffix(".zip").exists() else None,
    }


def _handle_history(args: argparse.Namespace) -> int:
    out_root = Path(args.out).resolve()
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
        print(json.dumps({"out": str(out_root), "runs": summaries}, indent=2))
        return 0

    if not summaries:
        print(f"No AgentLedger runs found in {out_root}")
        return 0

    print(f"AgentLedger runs in {out_root}:")
    for item in summaries:
        exit_code = item["exit_code"] if item["exit_code"] is not None else "n/a"
        print(
            f"{item['run_id']} | exit={exit_code} | changed={item['changed_files']} | "
            f"test={item['test_framework']} | command={item['command']}"
        )
        print(f"  report={item['markdown']}")
    return 0


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


def _capture(args: argparse.Namespace, task: list[str] | None) -> int:
    repo = Path(args.repo).resolve()
    out_root = Path(args.out).resolve()
    run_id = f"{utc_now_iso().replace(':', '').replace('+', 'Z')}-{uuid.uuid4().hex[:8]}"
    run_dir = out_root / run_id
    artifacts_dir = run_dir / "artifacts"
    run_dir.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    artifacts = []
    started = utc_now_iso()
    before = snapshot(repo)

    if not getattr(args, "no_repomori", False):
        artifacts.append(run_repomori_snapshot(repo, artifacts_dir, "before"))

    command_result = None
    command = _clean_task(task or [])
    if command:
        command_result = _run_task(command, repo, artifacts_dir)
    elif task is not None:
        warnings.append("No command supplied after --; captured repository state only.")

    after = snapshot(repo)

    if not getattr(args, "no_repomori", False):
        artifacts.append(run_repomori_snapshot(repo, artifacts_dir, "after"))
    if not getattr(args, "no_jester", False) and hasattr(args, "no_jester"):
        artifacts.append(run_jester_diff(repo, artifacts_dir))
    if not getattr(args, "no_tokometer", False):
        artifacts.append(read_tokometer_usage(artifacts_dir))

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
        artifacts=artifacts,
        warnings=warnings,
    )
    write_json(report, run_dir / "agentledger-report.json")
    write_markdown(report, run_dir / "agentledger-report.md")
    write_html(report, run_dir / "agentledger-report.html")
    if not getattr(args, "no_zip", False):
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
    if args.command_name == "compare":
        return _handle_compare(args)
    if args.command_name == "verify-bundle":
        return _handle_verify_bundle(args)
    parser.error("unknown command")
    return 2
