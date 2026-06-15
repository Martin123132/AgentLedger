from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_github_release.py"

spec = importlib.util.spec_from_file_location("check_github_release", SCRIPT)
assert spec is not None
check_github_release = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_github_release
assert spec.loader is not None
spec.loader.exec_module(check_github_release)


def release_body() -> str:
    return """## Highlights

- Added release checks.

## Validation

- Local release-check passed for `0.1.8a0` at `abc1234`; release metadata checks: 19 passed, 0 failed.
- PR CI passed on Ubuntu and Windows: https://github.com/Martin123132/AgentLedger/actions/runs/1001.
- Master CI passed for `abcdef1234567890`: https://github.com/Martin123132/AgentLedger/actions/runs/1002.
- Release Readiness passed on master: https://github.com/Martin123132/AgentLedger/actions/runs/1003.
- Tag CI passed for `v0.1.8-alpha`: https://github.com/Martin123132/AgentLedger/actions/runs/1004.

This is an alpha prerelease. Do not commit or upload `.agentledger/` evidence folders, zip bundles, or signing keys unless the contents have been reviewed.
"""


def sample_release(**overrides) -> dict:
    release = {
        "tagName": "v0.1.8-alpha",
        "name": "v0.1.8-alpha",
        "url": "https://github.com/Martin123132/AgentLedger/releases/tag/v0.1.8-alpha",
        "isDraft": False,
        "isPrerelease": True,
        "targetCommitish": "abcdef1234567890",
        "createdAt": "2026-06-15T05:00:00Z",
        "publishedAt": "2026-06-15T05:10:00Z",
        "body": release_body(),
    }
    release.update(overrides)
    return release


def test_check_github_release_accepts_publish_ready_prerelease() -> None:
    result = check_github_release.check_github_release(
        version="0.1.8a0",
        release=sample_release(),
    )

    assert result["schema_version"] == "agentledger.github_release_check.v1"
    assert result["ok"] is True
    assert result["tag"] == "v0.1.8-alpha"
    assert result["release"]["is_prerelease"] is True
    assert result["errors"] == []


def test_check_github_release_rejects_draft_release() -> None:
    result = check_github_release.check_github_release(
        version="0.1.8a0",
        release=sample_release(isDraft=True),
    )

    assert result["ok"] is False
    assert any("not draft" in error for error in result["errors"])


def test_check_github_release_rejects_non_prerelease_by_default() -> None:
    result = check_github_release.check_github_release(
        version="0.1.8a0",
        release=sample_release(isPrerelease=False),
    )

    assert result["ok"] is False
    assert any("prerelease status" in error for error in result["errors"])


def test_check_github_release_can_allow_final_release() -> None:
    result = check_github_release.check_github_release(
        version="0.1.8a0",
        release=sample_release(isPrerelease=False),
        require_prerelease=False,
    )

    assert result["ok"] is True


def test_check_github_release_rejects_unpublishable_body() -> None:
    result = check_github_release.check_github_release(
        version="0.1.8a0",
        release=sample_release(body="## Highlights\n\n- TODO: later.\n"),
    )

    assert result["ok"] is False
    assert any("release body" in error and "Missing ## Validation section" in error for error in result["errors"])


def test_main_reads_release_json_and_writes_markdown(tmp_path: Path, capsys) -> None:
    release_json = tmp_path / "release.json"
    output = tmp_path / "release-check.md"
    release_json.write_text(json.dumps(sample_release()), encoding="utf-8")

    exit_code = check_github_release.main(
        [
            "--version",
            "0.1.8a0",
            "--release-json",
            str(release_json),
            "--format",
            "markdown",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == f"GitHub release check written: {output}\n"
    text = output.read_text(encoding="utf-8")
    assert text.startswith("# AgentLedger GitHub Release Check\n")
    assert "| release body | passed |" in text


def test_main_returns_nonzero_for_failed_release_check(tmp_path: Path, capsys) -> None:
    release_json = tmp_path / "release.json"
    release_json.write_text(json.dumps(sample_release(isDraft=True)), encoding="utf-8")

    exit_code = check_github_release.main(
        ["--version", "0.1.8a0", "--release-json", str(release_json), "--format", "json"]
    )

    assert exit_code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is False
    assert any("not draft" in error for error in payload["errors"])
