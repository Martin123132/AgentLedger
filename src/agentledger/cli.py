from __future__ import annotations

import argparse
import json
import subprocess
import re
import uuid
from pathlib import Path
from typing import Any

from .bundle import write_zip_bundle
from .classify import detect_test_command
from .doctor import doctor_json, format_doctor, run_doctor
from .export import write_html, write_json, write_markdown
from .gittools import snapshot
from .integrations import read_tokometer_usage, run_jester_diff, run_repomori_snapshot
from .model import CommandResult, LedgerReport, utc_now_iso
from .process import run_capture, tail_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentledger",
        description="Local-first black box recorder for AI coding-agent work.",
    )
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

    latest = sub.add_parser("open-latest", help="Print latest report paths from a run output directory.")
    latest.add_argument("--out", default=".agentledger", help="Evidence output directory.")

    return parser


def _clean_task(task: list[str]) -> list[str]:
    if task and task[0] == "--":
        return task[1:]
    return task


def _load_report(run_dir: Path) -> dict[str, Any]:
    report_path = run_dir / "agentledger-report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Missing report file: {report_path}")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid report payload in {report_path}")
    return payload


def _artifact_status_counts(artifacts: list[dict[str, Any]]) -> tuple[int, int]:
    passed = 0
    warned = 0
    for artifact in artifacts:
        if artifact.get("ok"):
            passed += 1
        else:
            warned += 1
    return passed, warned


def _changed_file_count(report: dict[str, Any]) -> int:
    after = report.get("after") or {}
    diff_stat = str(after.get("diff_stat") or "").strip()
    match = re.search(r"(\d+)\s+files?\s+changed", diff_stat)
    if match:
        return int(match.group(1))
    match_single = re.search(r"(\d+)\s+file changed", diff_stat)
    if match_single:
        return int(match_single.group(1))
    diff = str(after.get("diff") or "")
    return sum(1 for line in diff.splitlines() if line.startswith("diff --git "))


def _first_non_empty(payload: dict[str, Any] | None, keys: tuple[str, ...]) -> Any | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if value is not None:
            return value
    return None


def _tokometer_summary(report: dict[str, Any]) -> str | None:
    artifacts = report.get("artifacts") or []
    tokos = [artifact for artifact in artifacts if isinstance(artifact, dict) and artifact.get("name") == "tokometer_summary"]
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


def _integration_warnings(report: dict[str, Any]) -> list[str]:
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


def _command_text(report: dict[str, Any]) -> str:
    command = report.get("command")
    if not isinstance(command, dict):
        return "No command executed"
    parts = command.get("command") or []
    if isinstance(parts, list):
        return " ".join(str(item) for item in parts) if parts else "No command executed"
    return str(parts)


def _handle_inspect_report(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        print(f"Run directory not found: {run_dir}")
        return 2
    try:
        report = _load_report(run_dir)
    except (FileNotFoundError, ValueError, json.JSONDecodeError, OSError) as exc:
        print(f"Unable to read report: {exc}")
        return 2

    command = report.get("command")
    exit_code = "n/a" if not isinstance(command, dict) else command.get("exit_code", "n/a")
    test_framework = "n/a" if not isinstance(command, dict) else (command.get("test_framework") or "n/a")
    changed_files = _changed_file_count(report)
    passed, warned = _artifact_status_counts([artifact for artifact in report.get("artifacts", []) if isinstance(artifact, dict)])
    warnings = _integration_warnings(report)
    tokometer_summary = _tokometer_summary(report)
    after = report.get("after") or {}

    print(f"Report: {run_dir / 'agentledger-report.json'}")
    print(f"Command: {_command_text(report)}")
    print(f"Exit code: {exit_code}")
    print(f"Test framework: {test_framework}")
    print(f"Diff stat: {after.get('diff_stat') or 'no tracked diff'}")
    print(f"Changed files: {changed_files}")
    print(f"Artifacts: {passed} ok, {warned} warn")
    if tokometer_summary:
        print(f"Tokometer: {tokometer_summary}")
    for warning in warnings:
        print(f"Warning: {warning}")
    zip_path = run_dir.with_suffix(".zip")
    if zip_path.exists():
        print(f"Zip bundle: {zip_path}")
    return 0


def _handle_open_latest(args: argparse.Namespace) -> int:
    out_root = Path(args.out).resolve()
    latest_path = out_root / "latest.txt"
    if not latest_path.exists():
        print(f"No latest.txt found in {out_root}")
        return 2
    latest_dir = Path(latest_path.read_text(encoding="utf-8").strip())
    if not latest_dir.is_absolute():
        latest_dir = latest_dir if latest_dir.exists() else (out_root / latest_dir)
    if not latest_dir.exists():
        print(f"Latest report directory not found: {latest_dir}")
        return 2

    print(f"Latest report directory: {latest_dir}")
    print(f"Markdown: {latest_dir / 'agentledger-report.md'}")
    print(f"JSON: {latest_dir / 'agentledger-report.json'}")
    print(f"HTML: {latest_dir / 'agentledger-report.html'}")
    zip_path = latest_dir.with_suffix(".zip")
    if zip_path.exists():
        print(f"Zip: {zip_path}")
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
    transcripts = artifacts_dir / "command"
    transcripts.mkdir(parents=True, exist_ok=True)
    stdout_path = transcripts / "stdout.txt"
    stderr_path = transcripts / "stderr.txt"
    stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
    stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
    test_detected, test_framework = detect_test_command(command)
    return CommandResult(
        command=command,
        cwd=str(repo),
        started_at=started,
        ended_at=ended,
        exit_code=exit_code,
        stdout_tail=tail_text(stdout),
        stderr_tail=tail_text(stderr),
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
        return 0 if report["status"] in {"ready", "partial"} else 2
    if args.command_name == "inspect-report":
        return _handle_inspect_report(args)
    if args.command_name == "open-latest":
        return _handle_open_latest(args)
    parser.error("unknown command")
    return 2
