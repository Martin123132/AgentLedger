from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL_CHECK_SCRIPT = ROOT / "scripts" / "install-check.ps1"
INSTALL_SOURCE_CHECK_SCRIPT = ROOT / "scripts" / "install-source-check.ps1"


def test_install_check_script_prints_step_markers() -> None:
    text = INSTALL_CHECK_SCRIPT.read_text(encoding="utf-8")

    assert 'Write-Host "AgentLedger install check"' in text
    assert '$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"' in text
    assert 'Write-Host "- Source checkout: $repoRoot"' in text
    assert 'Write-Host "== Create temporary virtual environment =="' in text
    assert 'Write-Host "== Check build backend =="' in text
    assert 'Write-Host "== Install AgentLedger from local checkout =="' in text
    assert 'Write-Host "== Verify console script =="' in text
    assert 'Write-Host "== Verify module entry point =="' in text
    assert 'Write-Host "== Verify help command =="' in text
    assert 'Write-Host "- Temporary workspace will be removed: $root"' in text


def test_install_source_check_script_installs_source_spec_and_runs_demo() -> None:
    text = INSTALL_SOURCE_CHECK_SCRIPT.read_text(encoding="utf-8")

    assert 'Write-Host "AgentLedger source install check"' in text
    assert '$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"' in text
    assert 'Write-Host "- Source: $Source"' in text
    assert 'Write-Host "== Create temporary virtual environment =="' in text
    assert 'Write-Host "== Check build backend =="' in text
    assert 'Write-Host "== Install AgentLedger from source spec =="' in text
    assert '& $python -m pip install --no-build-isolation --no-deps $Source' in text
    assert 'Write-Host "== Verify module entry point =="' in text
    assert 'Write-Host "== Verify demo command =="' in text
    assert '& $python -m agentledger demo --output-dir $demoWorkspace --format json | Out-Null' in text
    assert 'Write-Host "- Temporary workspace will be removed: $root"' in text
