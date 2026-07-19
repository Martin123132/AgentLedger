from __future__ import annotations

import contextlib
import ctypes
import io
import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from . import cli
from .config import ConfigError, load_config


@dataclass(frozen=True)
class DesktopCommandResult:
    exit_code: int
    stdout: str
    stderr: str
    payload: dict[str, Any] | None = None

    @property
    def output(self) -> str:
        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)


def invoke_cli(arguments: Sequence[str], *, expect_json: bool = False) -> DesktopCommandResult:
    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = cli.main(list(arguments))
    except SystemExit as exc:
        exit_code = int(exc.code) if isinstance(exc.code, int) else 2
    except Exception as exc:  # pragma: no cover - desktop safety boundary
        print(f"AgentLedger desktop command failed: {exc}", file=stderr)
        exit_code = 2

    output = stdout.getvalue()
    payload = _json_payload(output) if expect_json else None
    return DesktopCommandResult(
        exit_code=exit_code,
        stdout=output,
        stderr=stderr.getvalue(),
        payload=payload,
    )


def load_dashboard(repo: Path, *, out: Path | None = None, history_limit: int = 25) -> dict[str, Any]:
    repo = repo.expanduser().resolve()
    resolved_out = resolve_desktop_out(repo, out)
    status_args = ["status", "--repo", str(repo), "--out", str(resolved_out), "--format", "json"]
    history_args = [
        "history",
        "--repo",
        str(repo),
        "--out",
        str(resolved_out),
        "--limit",
        str(history_limit),
        "--format",
        "json",
    ]

    status_result = invoke_cli(status_args, expect_json=True)
    history_result = invoke_cli(history_args, expect_json=True)
    status_payload = status_result.payload or {
        "ok": False,
        "status": "unknown",
        "repo": str(repo),
        "out": str(resolved_out),
        "latest_run": None,
        "paths": {},
        "check": None,
        "history_integrity": None,
        "feedback": {},
        "next_actions": [],
        "errors": [status_result.output or "Unable to read AgentLedger status."],
    }
    history_payload = history_result.payload or {"runs": []}
    return {
        "status": status_payload,
        "history": history_payload.get("runs") or [],
        "status_result": status_result,
        "history_result": history_result,
    }


def capture_repository(
    repo: Path,
    command_line: str,
    *,
    out: Path | None = None,
    privacy_mode: str = "summary",
    zip_bundle: bool = True,
    repomori: bool = False,
    jester: bool = False,
    tokometer: bool = False,
) -> DesktopCommandResult:
    repo = repo.expanduser().resolve()
    resolved_out = resolve_desktop_out(repo, out)
    command = split_command_line(command_line)
    if not command:
        return DesktopCommandResult(2, "", "Enter a command to capture.")

    arguments = [
        "run",
        "--repo",
        str(repo),
        "--out",
        str(resolved_out),
        "--privacy-mode",
        privacy_mode,
    ]
    if not zip_bundle:
        arguments.append("--no-zip")
    if not repomori:
        arguments.append("--no-repomori")
    if not jester:
        arguments.append("--no-jester")
    if not tokometer:
        arguments.append("--no-tokometer")
    arguments.extend(["--", *command])
    return invoke_cli(arguments)


def run_safe_demo() -> DesktopCommandResult:
    return invoke_cli(["try", "--format", "json"], expect_json=True)


def resolve_desktop_out(repo: Path, out: Path | None = None) -> Path:
    repo = repo.expanduser().resolve()
    if out is not None:
        return out.expanduser().resolve()
    try:
        configured = load_config(repo).out
    except ConfigError:
        configured = None
    if not configured:
        return (repo / ".agentledger").resolve()
    configured_path = Path(configured).expanduser()
    return configured_path.resolve() if configured_path.is_absolute() else (repo / configured_path).resolve()


def split_command_line(command_line: str) -> list[str]:
    command_line = command_line.strip()
    if not command_line:
        return []
    if os.name != "nt":
        return shlex.split(command_line)

    argc = ctypes.c_int()
    command_line_to_argv = ctypes.windll.shell32.CommandLineToArgvW
    command_line_to_argv.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_int)]
    command_line_to_argv.restype = ctypes.POINTER(ctypes.c_wchar_p)
    argv = command_line_to_argv(command_line, ctypes.byref(argc))
    if not argv:
        raise ValueError("Unable to parse the command line.")
    try:
        return [argv[index] for index in range(argc.value)]
    finally:
        ctypes.windll.kernel32.LocalFree(argv)


def _json_payload(output: str) -> dict[str, Any] | None:
    text = output.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                payload, _ = decoder.raw_decode(text, index)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None
    return payload if isinstance(payload, dict) else None
