from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "required": self.required,
        }


def _run(command: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=20,
        )
        return result.returncode, result.stdout.strip()
    except FileNotFoundError as exc:
        return 127, str(exc)
    except OSError as exc:
        return 1, str(exc)
    except subprocess.SubprocessError as exc:
        return 1, str(exc)


def run_doctor(repo: Path | None = None) -> dict[str, Any]:
    checks: list[Check] = []

    git_path = shutil.which("git")
    checks.append(Check("git", bool(git_path), git_path or "git not found", required=True))

    if repo:
        code, output = _run(["git", "rev-parse", "--show-toplevel"], repo)
        checks.append(Check("target_git_repo", code == 0, output or str(repo), required=True))

    python_code, python_output = _run(["python", "--version"])
    checks.append(Check("python", python_code == 0, python_output or "python not found", required=True))

    repomori_code, repomori_output = _run(["python", "-m", "repomori", "--help"])
    checks.append(Check("repomori", repomori_code == 0, "python -m repomori available" if repomori_code == 0 else repomori_output))

    jester_path = shutil.which("jester") or shutil.which("memento-mori-jester")
    checks.append(Check("jester", bool(jester_path), jester_path or "jester not found on PATH"))

    npx_path = shutil.which("npx") or shutil.which("npx.cmd")
    checks.append(Check("npx", bool(npx_path), npx_path or "npx not found"))

    tsx_code, tsx_output = _run([npx_path or "npx", "-y", "tsx", "--version"]) if npx_path else (127, "npx missing")
    checks.append(Check("tsx", tsx_code == 0, tsx_output or "tsx not available through npx"))

    tokometer_root = Path(os.environ.get("AGENTLEDGER_TOKOMETER_ROOT", Path.home() / "OneDrive" / "Documents" / "codex-token-gauge"))
    tokometer_usage = tokometer_root / "server" / "usage.ts"
    checks.append(Check("tokometer_checkout", tokometer_usage.exists(), str(tokometer_usage)))

    codex_home = Path(os.environ.get("TOKEN_GAUGE_CODEX_HOME", Path.home() / ".codex"))
    checks.append(Check("codex_home", codex_home.exists(), str(codex_home)))

    required_ok = all(check.ok for check in checks if check.required)
    optional_checks = [check for check in checks if not check.required]
    optional_ok = sum(1 for check in optional_checks if check.ok)
    missing_optional = [check.name for check in optional_checks if not check.ok]
    if required_ok:
        status = "ready"
    else:
        status = "blocked"

    return {
        "schema_version": "agentledger.doctor.v1",
        "status": status,
        "required_ok": required_ok,
        "optional": {
            "configured": optional_ok,
            "total": len(optional_checks),
            "missing": missing_optional,
        },
        "checks": [check.to_dict() for check in checks],
    }


def format_doctor(report: dict[str, Any]) -> str:
    optional = report.get("optional", {})
    missing_optional = optional.get("missing") or []
    if report["status"] == "ready" and missing_optional:
        header = "AgentLedger doctor: ready (required checks passed; optional integrations missing)"
    elif report["status"] == "ready":
        header = "AgentLedger doctor: ready (all checks passed)"
    else:
        header = "AgentLedger doctor: blocked (required setup needs attention)"

    lines = [header]
    if optional:
        lines.append(
            "Optional integrations: "
            f"{optional.get('configured', 0)}/{optional.get('total', 0)} configured"
        )
    for check in report["checks"]:
        required = "required" if check["required"] else "optional"
        if check["required"]:
            mark = "ok" if check["ok"] else "missing"
        else:
            mark = "available" if check["ok"] else "not configured"
        lines.append(f"- {check['name']}: {mark} ({required}) - {check['detail']}")
    return "\n".join(lines)


def doctor_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2)
