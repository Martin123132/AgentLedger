from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ALPHA_SCRIPT = ROOT / "scripts" / "alpha.ps1"
ENSURE_GIT_SCRIPT = ROOT / "scripts" / "ensure-git.ps1"


def _powershell() -> str | None:
    for candidate in ("pwsh", "powershell"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def test_alpha_script_validates_status_command() -> None:
    text = ALPHA_SCRIPT.read_text(encoding="utf-8")

    assert 'Invoke-CapturedCommand "Show latest status"' in text
    assert '"agentledger", "status", "--repo", ".", "--out", $Out, "--allow-warnings"' in text
    assert 'Invoke-CapturedCommand "Check latest status JSON"' in text
    assert '"status", "--repo", ".", "--out", $Out, "--format", "json", "--allow-warnings"' in text
    assert "$statusSummary = ($statusOutput | Select-Object -First 1)" in text
    assert 'Write-Host "- Status: $statusSummary"' in text


def test_alpha_script_writes_json_summary() -> None:
    text = ALPHA_SCRIPT.read_text(encoding="utf-8")

    assert "[string] $JsonOutput" in text
    assert "function Write-AlphaSummary" in text
    assert 'schema_version = "agentledger.alpha_summary.v1"' in text
    assert "summary_file = $resolvedSummaryPath" in text
    assert 'Join-Path $Out "alpha-summary.json"' in text
    assert '$statusPayload = ($statusJsonOutput -join "`n") | ConvertFrom-Json' in text
    assert "errors = @()" in text
    assert "Write-AlphaSummary -Path $resolvedSummaryPath -Payload $alphaSummary" in text
    assert "$Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8" in text
    assert 'Write-Host "- Alpha summary JSON: $resolvedSummaryPath"' in text


def test_alpha_script_handles_summary_write_failures() -> None:
    text = ALPHA_SCRIPT.read_text(encoding="utf-8")

    assert "$script:alphaExitCode = 0" in text
    assert "function Add-AlphaSummaryWriteError" in text
    assert "Unable to write alpha summary ${resolvedSummaryPath}" in text
    assert 'Write-Host "- Alpha summary JSON: not written"' in text
    assert 'Write-Host "- Alpha summary write error: $summaryWriteError"' in text
    assert "Choose a writable alpha summary path, then run scripts/alpha.ps1 again." in text
    assert '$Payload["ok"] = $false' in text
    assert '$Payload["status_exit_code"] = 2' in text
    assert "exit $script:alphaExitCode" in text


def test_alpha_script_writes_blocked_doctor_summary() -> None:
    text = ALPHA_SCRIPT.read_text(encoding="utf-8")

    assert "function Invoke-CapturedCommandResult" in text
    assert "function Write-AlphaBlockedSummary" in text
    assert "function Get-DoctorRepairActions" in text
    assert "function Get-DoctorSetupErrors" in text
    assert 'status = "block"' in text
    assert 'latest_run = $null' in text
    assert 'bundle = $null' in text
    assert 'report_paths = [ordered]@{}' in text
    assert 'next_actions = @(Get-DoctorRepairActions -DoctorPayload $DoctorPayload)' in text
    assert 'errors = @(Get-DoctorSetupErrors -DoctorPayload $DoctorPayload)' in text
    assert 'Fix ${name}: $hint' in text
    assert "After fixing required setup, run scripts/alpha.ps1 again." in text
    assert 'if ($doctorResult.ExitCode -ne 0)' in text
    assert "$script:skipAlphaRemainder = $true" in text
    assert "if (-not $script:skipAlphaRemainder)" in text


def test_alpha_script_blocked_doctor_summary_executes(tmp_path: Path) -> None:
    if sys.platform != "win32":
        pytest.skip("alpha.ps1 execution regression is Windows-only")
    shell = _powershell()
    if shell is None:
        pytest.skip("PowerShell is not available")

    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    script = scripts_dir / "alpha.ps1"
    ensure_git = scripts_dir / "ensure-git.ps1"
    script.write_text(ALPHA_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    ensure_git.write_text(ENSURE_GIT_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    summary = tmp_path / "alpha-summary.json"

    env = os.environ.copy()
    python_path = str(ROOT / "src")
    if env.get("PYTHONPATH"):
        env["PYTHONPATH"] = python_path + os.pathsep + env["PYTHONPATH"]
    else:
        env["PYTHONPATH"] = python_path
    result = subprocess.run(
        [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script),
            "-Out",
            "ledger",
            "-JsonOutput",
            str(summary),
            "-SkipEditableInstall",
        ],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60,
    )

    assert result.returncode == 2, result.stdout
    assert "== Alpha blocked ==" in result.stdout
    assert "Fix target_git_repo:" in result.stdout
    assert "== Run install check ==" not in result.stdout
    payload = json.loads(summary.read_text(encoding="utf-8-sig"))
    assert payload["schema_version"] == "agentledger.alpha_summary.v1"
    assert payload["ok"] is False
    assert payload["summary_file"] == str(summary)
    assert payload["status"] == "block"
    assert payload["latest_run"] is None
    assert payload["bundle"] is None
    assert payload["report_paths"] == {}
    assert any("Required doctor check failed: target_git_repo" in error for error in payload["errors"])
    assert payload["next_actions"] == [
        "Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo.",
        "After fixing required setup, run scripts/alpha.ps1 again.",
    ]
