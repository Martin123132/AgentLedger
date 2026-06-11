from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .model import ToolArtifact
from .process import run_capture, tail_text


def _python_executable() -> str:
    return os.environ.get("AGENTLEDGER_PYTHON", "python")


def _node_executable() -> str:
    return os.environ.get("AGENTLEDGER_NODE", "node")


def run_repomori_snapshot(repo: Path, out_dir: Path, label: str) -> ToolArtifact:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / f"repomori-{label}.json"
    command = [
        _python_executable(),
        "-m",
        "repomori",
        "snapshot",
        str(repo),
        "--out-dir",
        str(out_dir / "repomori-packs"),
        "--handoff",
        "AgentLedger evidence snapshot",
        "--json",
    ]
    result = run_capture(command, repo)
    report_path.write_text(result.stdout or result.stderr, encoding="utf-8")
    return ToolArtifact(
        name=f"repomori_snapshot_{label}",
        ok=result.returncode == 0,
        command=command,
        output_path=str(report_path),
        summary="RepoMori snapshot captured." if result.returncode == 0 else tail_text(result.stderr or result.stdout, 500),
        exit_code=result.returncode,
    )


def run_jester_diff(repo: Path, out_dir: Path) -> ToolArtifact:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "jester-diff.txt"
    jester = shutil.which("jester") or shutil.which("memento-mori-jester")
    if not jester:
        return ToolArtifact(
            name="jester_diff",
            ok=False,
            output_path=str(report_path),
            summary="Jester CLI was not found on PATH; skipped diff safety gate.",
        )
    diff = run_capture(["git", "diff"], repo)
    result = run_capture([jester, "diff", "--fail-on", "block"], repo, input_text=diff.stdout)
    report_path.write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8")
    if not diff.stdout.strip():
        summary = "No tracked diff to review."
    elif result.returncode == 0:
        summary = "Jester diff gate passed."
    else:
        summary = "Jester diff gate returned a blocking or warning result."
    return ToolArtifact(
        name="jester_diff",
        ok=result.returncode == 0,
        command=[jester, "diff", "--fail-on", "block"],
        output_path=str(report_path),
        summary=summary,
        exit_code=result.returncode,
    )


def read_tokometer_usage(out_dir: Path) -> ToolArtifact:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "tokometer-local-paths.json"
    codex_home = Path(os.environ.get("TOKEN_GAUGE_CODEX_HOME", Path.home() / ".codex"))
    sessions = codex_home / "sessions"
    archived = codex_home / "archived_sessions"
    payload = {
        "codex_home": str(codex_home),
        "sessions_exists": sessions.exists(),
        "archived_sessions_exists": archived.exists(),
        "note": "AgentLedger currently records Tokometer-compatible local paths. Full token summary API integration is planned.",
    }
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return ToolArtifact(
        name="tokometer_paths",
        ok=sessions.exists() or archived.exists(),
        output_path=str(report_path),
        summary="Recorded local Codex/Tokometer paths for usage evidence.",
    )


def run_tokensquash_reply(report_summary: str, out_dir: Path) -> ToolArtifact:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "tokensquash-reply.txt"
    command = [_python_executable(), "-m", "tokensquash", "reply", "encode", "--summary", report_summary]
    result = run_capture(command, Path.cwd())
    report_path.write_text((result.stdout or "") + (result.stderr or ""), encoding="utf-8")
    return ToolArtifact(
        name="tokensquash_reply",
        ok=result.returncode == 0,
        command=command,
        output_path=str(report_path),
        summary="Compact reply encoded." if result.returncode == 0 else "TokenSquash not available or encode failed; skipped.",
        exit_code=result.returncode,
    )
