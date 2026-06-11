from __future__ import annotations

import argparse
import subprocess
import uuid
from pathlib import Path

from .export import write_json, write_markdown
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
    run.add_argument("task", nargs=argparse.REMAINDER, help="Command to run after --.")

    snap = sub.add_parser("snapshot", help="Capture repository state without running a command.")
    snap.add_argument("--repo", default=".", help="Target git repository.")
    snap.add_argument("--out", default=".agentledger", help="Evidence output directory.")
    snap.add_argument("--no-repomori", action="store_true", help="Skip RepoMori snapshot hook.")
    snap.add_argument("--no-tokometer", action="store_true", help="Skip Tokometer path evidence.")

    return parser


def _clean_task(task: list[str]) -> list[str]:
    if task and task[0] == "--":
        return task[1:]
    return task


def _run_task(command: list[str], repo: Path) -> CommandResult:
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
    return CommandResult(
        command=command,
        cwd=str(repo),
        started_at=started,
        ended_at=ended,
        exit_code=exit_code,
        stdout_tail=tail_text(stdout),
        stderr_tail=tail_text(stderr),
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
        command_result = _run_task(command, repo)
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
    latest = out_root / "latest.txt"
    latest.write_text(str(run_dir), encoding="utf-8")

    print(f"AgentLedger report: {run_dir / 'agentledger-report.md'}")
    if command_result and command_result.exit_code != 0:
        return command_result.exit_code
    blocking = [artifact for artifact in artifacts if artifact.name == "jester_diff" and not artifact.ok]
    return 2 if blocking else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command_name == "run":
        return _capture(args, args.task)
    if args.command_name == "snapshot":
        return _capture(args, None)
    parser.error("unknown command")
    return 2
