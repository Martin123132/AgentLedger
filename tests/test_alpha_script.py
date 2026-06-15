from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALPHA_SCRIPT = ROOT / "scripts" / "alpha.ps1"


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
