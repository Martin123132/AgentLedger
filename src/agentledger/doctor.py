from __future__ import annotations

import json
import os
import re
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
    hint: str = "No action needed."

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "required": self.required,
            "hint": "No action needed." if self.ok else self.hint,
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
    checks.append(
        Check(
            "git",
            bool(git_path),
            git_path or "git not found",
            required=True,
            hint="Install Git and make sure git is available on PATH.",
        )
    )

    if repo:
        code, output = _run(["git", "rev-parse", "--show-toplevel"], repo)
        checks.append(
            Check(
                "target_git_repo",
                code == 0,
                output or str(repo),
                required=True,
                hint="Run from a git checkout or pass --repo <path> to an existing git repo.",
            )
        )

    python_code, python_output = _run(["python", "--version"])
    checks.append(
        Check(
            "python",
            python_code == 0,
            python_output or "python not found",
            required=True,
            hint="Install Python 3.10+ and make sure python is available on PATH.",
        )
    )

    repomori_code, repomori_output = _run(["python", "-m", "repomori", "--help"])
    checks.append(
        Check(
            "repomori",
            repomori_code == 0,
            "python -m repomori available" if repomori_code == 0 else repomori_output,
            hint="Optional: install RepoMori, or keep using --no-repomori / repomori = false.",
        )
    )

    jester_path = shutil.which("jester") or shutil.which("memento-mori-jester")
    checks.append(
        Check(
            "jester",
            bool(jester_path),
            jester_path or "jester not found on PATH",
            hint="Optional: install Jester, or keep using --no-jester / jester = false.",
        )
    )

    npx_path = shutil.which("npx") or shutil.which("npx.cmd")
    checks.append(
        Check(
            "npx",
            bool(npx_path),
            npx_path or "npx not found",
            hint="Optional: install Node.js/npm if you need npx-based helper integrations.",
        )
    )

    tsx_code, tsx_output = _run([npx_path or "npx", "-y", "tsx", "--version"]) if npx_path else (127, "npx missing")
    checks.append(
        Check(
            "tsx",
            tsx_code == 0,
            tsx_output or "tsx not available through npx",
            hint="Optional: make sure npx can run tsx, usually with npx -y tsx --version.",
        )
    )

    tokometer_root = Path(os.environ.get("AGENTLEDGER_TOKOMETER_ROOT", Path.home() / "OneDrive" / "Documents" / "codex-token-gauge"))
    tokometer_usage = tokometer_root / "server" / "usage.ts"
    checks.append(
        Check(
            "tokometer_checkout",
            tokometer_usage.exists(),
            str(tokometer_usage),
            hint="Optional: set AGENTLEDGER_TOKOMETER_ROOT to a codex-token-gauge checkout, or keep tokometer = false.",
        )
    )

    codex_home = Path(os.environ.get("TOKEN_GAUGE_CODEX_HOME", Path.home() / ".codex"))
    checks.append(
        Check(
            "codex_home",
            codex_home.exists(),
            str(codex_home),
            hint="Optional: set TOKEN_GAUGE_CODEX_HOME to the Codex home directory if needed.",
        )
    )

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
        if not check["ok"] and check.get("hint"):
            lines.append(f"  Hint: {check['hint']}")
    return "\n".join(lines)


def _doctor_markdown_status(report: dict[str, Any]) -> str:
    optional = report.get("optional", {}) if isinstance(report.get("optional"), dict) else {}
    missing_optional = optional.get("missing") or []
    if report.get("status") == "ready" and missing_optional:
        return "ready - required checks passed; optional integrations are missing"
    if report.get("status") == "ready":
        return "ready - all checks passed"
    return "blocked - required setup needs attention"


def _doctor_markdown_detail(check: dict[str, Any]) -> str:
    detail = str(check.get("detail") or "").replace("\r", " ").replace("\n", " ").strip()
    if not detail:
        return "No detail reported."
    if _contains_local_path(detail):
        return "<local path redacted>"
    if check.get("ok"):
        return "available"
    return detail


def _contains_local_path(value: str) -> bool:
    if re.search(r"\b[A-Za-z]:[\\/]", value):
        return True
    home = str(Path.home())
    if home and home.lower() in value.lower():
        return True
    return bool(re.search(r"(^|[\s'\"=])/(Users|home|mnt|tmp|var|opt)(/|\b)", value))


def _doctor_markdown_checks(report: dict[str, Any], *, required: bool) -> list[str]:
    lines: list[str] = []
    checks = [check for check in report.get("checks") or [] if bool(check.get("required")) is required]
    if not checks:
        lines.append("- None")
        return lines
    for check in checks:
        mark = "x" if check.get("ok") else " "
        state = "ok" if check.get("ok") else ("missing" if required else "not configured")
        lines.append(f"- [{mark}] `{check.get('name', 'unknown')}`: {state} - {_doctor_markdown_detail(check)}")
        if not check.get("ok") and check.get("hint"):
            lines.append(f"  - Next: {check['hint']}")
    return lines


def format_doctor_markdown(report: dict[str, Any]) -> str:
    optional = report.get("optional", {}) if isinstance(report.get("optional"), dict) else {}
    lines = [
        "## AgentLedger doctor report",
        "",
        "### Summary",
        f"- Status: {_doctor_markdown_status(report)}",
        f"- Required setup: {'pass' if report.get('required_ok') else 'fix required'}",
        f"- Optional integrations configured: {optional.get('configured', 0)}/{optional.get('total', 0)}",
        "- Raw evidence copied: no",
        "- Local paths included: no",
        "- Raw evidence kept private: yes",
        "",
        "### Required checks",
    ]
    lines.extend(_doctor_markdown_checks(report, required=True))
    lines.extend(["", "### Optional integrations"])
    lines.extend(_doctor_markdown_checks(report, required=False))
    lines.extend(
        [
            "",
            "### What to try next",
            "- If required checks are blocked, fix the `Next:` hint above and rerun `python -m agentledger doctor --repo . --format markdown`.",
            "- If required checks pass, run `python -m agentledger try` for the safe demo.",
            "- For a real repo, run `python -m agentledger alpha-guide --repo . --out .agentledger` before creating evidence.",
            "- For a copy-ready support report, run `python -m agentledger support-packet --format markdown`.",
            "",
            "### Troubleshooting map",
            "- Install problems: `python -m agentledger doctor --repo . --format markdown`.",
            "- Command problems: `python -m agentledger status --out .agentledger --allow-warnings`.",
            "- Packet confusion: `python -m agentledger open-packet --out .agentledger`.",
            "- Privacy-safe reporting: paste only reviewed packet/export text or redacted errors.",
            "",
            "### Keep private by default",
            "- Raw `.agentledger/` run folders and local evidence output folders.",
            "- Zip evidence bundles, command transcripts, terminal logs, full reports, and raw diffs.",
            "- Temporary demo workspaces, signing keys, private repo paths, private URLs, credentials, tokens, and secrets.",
        ]
    )
    return "\n".join(lines)


def doctor_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2)
