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
    assert 'schema_version = "agentledger.alpha_summary.v1"' in text
    assert "summary_file = $resolvedSummaryPath" in text
    assert 'Join-Path $Out "alpha-summary.json"' in text
    assert '$statusPayload = ($statusJsonOutput -join "`n") | ConvertFrom-Json' in text
    assert "errors = @()" in text
    assert "$alphaSummary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $resolvedSummaryPath -Encoding UTF8" in text
    assert 'Write-Host "- Alpha summary JSON: $resolvedSummaryPath"' in text
