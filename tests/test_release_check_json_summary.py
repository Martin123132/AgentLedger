from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release-check.ps1"
WORKFLOW = ROOT / ".github" / "workflows" / "release-check.yml"
README = ROOT / "README.md"
RELEASE_PROCESS = ROOT / "docs" / "release-process.md"


def test_release_check_script_defines_json_summary_contract() -> None:
    text = SCRIPT.read_text(encoding="utf-8")

    assert "[string] $JsonOutput" in text
    assert 'schema_version = "agentledger.release_check.v1"' in text
    assert "Write-JsonSummary -Path $JsonOutput" in text

    for field in [
        "ok =",
        "status =",
        "repo =",
        "branch =",
        "head =",
        "agentledger_version =",
        "package_version =",
        "require_clean_git =",
        "skip_editable_install =",
        "working_tree_dirty =",
        "wheel =",
        "release_metadata =",
        "steps =",
        "error =",
    ]:
        assert field in text

    assert "scripts/check_release_metadata.py" in text


def test_release_readiness_workflow_emits_json_summary() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "agentledger-release-check.json" in text
    assert "agentledger-release-check-summary.md" in text
    assert '"-JsonOutput", $summaryPath' in text
    assert "Get-Content -Raw -LiteralPath $summaryPath" in text
    assert "python scripts/release_check_summary.py $summaryPath --output $markdownSummaryPath" in text
    assert "$env:GITHUB_STEP_SUMMARY" in text
    assert "exit $exitCode" in text


def test_release_check_json_summary_is_documented() -> None:
    for path in [README, RELEASE_PROCESS]:
        text = path.read_text(encoding="utf-8")
        assert "-JsonOutput" in text
        assert "agentledger-release-check.json" in text
        assert "agentledger.release_check.v1" in text
        assert "scripts/check_release_metadata.py" in text
        assert "scripts/release_check_summary.py" in text
