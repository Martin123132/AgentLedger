from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

from .model import ToolArtifact
from .process import run_capture, tail_text
from .redaction import redact_command, redact_text


def _python_executable() -> str:
    return os.environ.get("AGENTLEDGER_PYTHON", "python")


def _npx_executable() -> str:
    configured = os.environ.get("AGENTLEDGER_NPX")
    if configured:
        return configured
    return shutil.which("npx") or shutil.which("npx.cmd") or "npx"


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
    try:
        result = run_capture(command, repo)
    except FileNotFoundError as exc:
        report_path.write_text(
            json.dumps(
                {
                    "schema_version": "agentledger.repomori_snapshot.v1",
                    "ok": False,
                    "label": label,
                    "repo": str(repo),
                    "error": redact_text(str(exc)),
                    "note": "Python executable was not found or RepoMori could not be launched.",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return ToolArtifact(
            name=f"repomori_snapshot_{label}",
            ok=False,
            command=redact_command(command),
            output_path=str(report_path),
            summary="RepoMori snapshot skipped because it could not be launched.",
        )
    report_path.write_text(redact_text(result.stdout or result.stderr), encoding="utf-8")
    summary = "RepoMori snapshot captured."
    if result.returncode != 0:
        summary = "RepoMori snapshot failed or RepoMori is not installed."
    return ToolArtifact(
        name=f"repomori_snapshot_{label}",
        ok=result.returncode == 0,
        command=redact_command(command),
        output_path=str(report_path),
        summary=summary if result.returncode == 0 else f"{summary} {tail_text(redact_text(result.stderr or result.stdout), 500)}",
        exit_code=result.returncode,
    )


def summarize_repomori_artifact(path: str | None) -> str | None:
    if not path:
        return None
    artifact_path = Path(path)
    if not artifact_path.exists():
        return None
    try:
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if isinstance(payload, dict) and payload.get("ok") is False:
        return str(payload.get("note") or payload.get("error") or "RepoMori artifact reports failure.")
    keys = []
    for key in ("pack", "pack_path", "snapshot", "snapshot_path", "handoff", "handoff_dir", "latest"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if value:
            keys.append(f"{key}={value}")
    if keys:
        return "; ".join(keys[:4])
    if isinstance(payload, dict):
        return f"RepoMori JSON keys: {', '.join(sorted(payload.keys())[:8])}"
    return None


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
    report_path.write_text(redact_text((result.stdout or "") + (result.stderr or "")), encoding="utf-8")
    if not diff.stdout.strip():
        summary = "No tracked diff to review."
    elif result.returncode == 0:
        summary = "Jester diff gate passed."
    else:
        summary = "Jester diff gate returned a blocking or warning result."
    return ToolArtifact(
        name="jester_diff",
        ok=result.returncode == 0,
        command=redact_command([jester, "diff", "--fail-on", "block"]),
        output_path=str(report_path),
        summary=summary,
        exit_code=result.returncode,
    )


def read_tokometer_usage(out_dir: Path) -> ToolArtifact:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "tokometer-summary.json"
    codex_home = Path(os.environ.get("TOKEN_GAUGE_CODEX_HOME", Path.home() / ".codex"))
    sessions = codex_home / "sessions"
    archived = codex_home / "archived_sessions"
    script = Path(__file__).resolve().parents[2] / "scripts" / "tokometer-summary.mjs"
    tokometer_root = Path(os.environ.get("AGENTLEDGER_TOKOMETER_ROOT", Path.home() / "OneDrive" / "Documents" / "codex-token-gauge"))
    command = [
        _npx_executable(),
        "-y",
        "tsx",
        str(script),
        "--tokometer-root",
        str(tokometer_root),
        "--out",
        str(report_path),
    ]
    try:
        result = run_capture(command, out_dir)
    except FileNotFoundError as exc:
        payload = {
            "schema_version": "agentledger.tokometer_summary.v1",
            "codex_home": str(codex_home),
            "sessions_exists": sessions.exists(),
            "archived_sessions_exists": archived.exists(),
            "tokometer_root": str(tokometer_root),
            "error": redact_text(str(exc)),
            "note": "npx/tsx was not available; recorded local Codex/Tokometer paths instead.",
        }
        report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return ToolArtifact(
            name="tokometer_summary",
            ok=False,
            command=redact_command(command),
            output_path=str(report_path),
            summary="Tokometer summary import skipped because npx/tsx was not available.",
        )
    except subprocess.SubprocessError as exc:
        payload = {
            "schema_version": "agentledger.tokometer_summary.v1",
            "codex_home": str(codex_home),
            "sessions_exists": sessions.exists(),
            "archived_sessions_exists": archived.exists(),
            "tokometer_root": str(tokometer_root),
            "error": redact_text(str(exc)),
            "note": "Tokometer summary subprocess failed; recorded local Codex/Tokometer paths instead.",
        }
        report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return ToolArtifact(
            name="tokometer_summary",
            ok=False,
            command=redact_command(command),
            output_path=str(report_path),
            summary="Tokometer summary import failed before completion.",
        )
    if result.returncode != 0:
        payload = {
            "schema_version": "agentledger.tokometer_summary.v1",
            "codex_home": str(codex_home),
            "sessions_exists": sessions.exists(),
            "archived_sessions_exists": archived.exists(),
            "tokometer_root": str(tokometer_root),
            "error": tail_text(redact_text(result.stderr or result.stdout), 2000),
            "note": "Direct Tokometer summary failed; recorded local Codex/Tokometer paths instead.",
        }
        report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return ToolArtifact(
            name="tokometer_summary",
            ok=False,
            command=redact_command(command),
            output_path=str(report_path),
            summary="Tokometer summary import failed; fallback path evidence recorded.",
            exit_code=result.returncode,
        )
    return ToolArtifact(
        name="tokometer_summary",
        ok=True,
        command=redact_command(command),
        output_path=str(report_path),
        summary="Imported Tokometer local usage summary.",
        exit_code=result.returncode,
    )


def run_tokensquash_reply(report_summary: str, out_dir: Path) -> ToolArtifact:
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "tokensquash-reply.txt"
    command = [_python_executable(), "-m", "tokensquash", "reply", "encode", "--summary", report_summary]
    result = run_capture(command, Path.cwd())
    report_path.write_text(redact_text((result.stdout or "") + (result.stderr or "")), encoding="utf-8")
    return ToolArtifact(
        name="tokensquash_reply",
        ok=result.returncode == 0,
        command=redact_command(command),
        output_path=str(report_path),
        summary="Compact reply encoded." if result.returncode == 0 else "TokenSquash not available or encode failed; skipped.",
        exit_code=result.returncode,
    )
