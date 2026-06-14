from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALPHA_SCRIPT = ROOT / "scripts" / "alpha.ps1"


def test_alpha_script_validates_status_command() -> None:
    text = ALPHA_SCRIPT.read_text(encoding="utf-8")

    assert 'Invoke-CapturedCommand "Show latest status"' in text
    assert '"agentledger", "status", "--repo", ".", "--out", $Out, "--allow-warnings"' in text
    assert 'Invoke-CheckedCommand "Check latest status JSON"' in text
    assert '"status", "--repo", ".", "--out", $Out, "--format", "json", "--allow-warnings"' in text
    assert "$statusSummary = ($statusOutput | Select-Object -First 1)" in text
    assert 'Write-Host "- Status: $statusSummary"' in text
