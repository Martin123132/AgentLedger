from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "post_release_check.py"

spec = importlib.util.spec_from_file_location("post_release_check", SCRIPT)
assert spec is not None
post_release_check = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = post_release_check
assert spec.loader is not None
spec.loader.exec_module(post_release_check)


def release_check_payload() -> dict:
    return {
        "schema_version": "agentledger.release_check.v1",
        "ok": True,
        "status": "ready",
        "repo": "D:\\Projects\\AgentLedger",
        "branch": "master",
        "head": "abcdef1",
        "agentledger_version": "0.1.8a0",
        "package_version": "0.1.8a0",
        "require_clean_git": True,
        "skip_editable_install": False,
        "working_tree_dirty": False,
        "wheel": "agentledger-0.1.8a0-py3-none-any.whl",
        "release_metadata": {
            "schema_version": "agentledger.release_metadata_check.v1",
            "ok": True,
            "status": "ready",
            "repo": "D:\\Projects\\AgentLedger",
            "project_name": "agentledger",
            "project_version": "0.1.8a0",
            "package_version": "0.1.8a0",
            "release_label": "0.1.8-alpha",
            "license": "PolyForm Noncommercial License 1.0.0",
            "checks": [
                {"name": "project name", "status": "passed", "detail": "agentledger"},
                {"name": "license metadata", "status": "passed", "detail": "ok"},
            ],
            "errors": [],
        },
        "steps": [
            {"name": "Check release versions", "status": "passed", "seconds": 0.2, "error": None},
            {"name": "Check release metadata", "status": "passed", "seconds": 0.1, "error": None},
        ],
        "error": None,
    }


def release_body() -> str:
    return """## Highlights

- Added post-release packet flow.

## Validation

- Local release-check passed for `0.1.8a0` at `abcdef1`; release metadata checks: 2 passed, 0 failed.
- PR CI passed on Ubuntu and Windows: https://github.com/Martin123132/AgentLedger/actions/runs/1001.
- Master CI passed for `abcdef1234567890`: https://github.com/Martin123132/AgentLedger/actions/runs/1002.
- Release Readiness passed on master: https://github.com/Martin123132/AgentLedger/actions/runs/1003.
- Tag CI passed for `v0.1.8-alpha`: https://github.com/Martin123132/AgentLedger/actions/runs/1004.

This is an alpha prerelease. Do not commit or upload `.agentledger/` evidence folders, zip bundles, or signing keys unless the contents have been reviewed.
"""


def github_release_payload(**overrides) -> dict:
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


def write_inputs(tmp_path: Path, *, release: dict | None = None) -> tuple[Path, Path, Path, Path]:
    release_payload = release_check_payload()
    release_check_json = tmp_path / "agentledger-release-check.json"
    release_check_json.write_text(json.dumps(release_payload), encoding="utf-8")
    release_check_summary = tmp_path / "agentledger-release-check-summary.md"
    release_check_summary.write_text(
        post_release_check.release_evidence_packet.release_check_summary.render_release_check_markdown(
            release_payload
        ),
        encoding="utf-8",
    )
    release_notes = tmp_path / "agentledger-0.1.8-alpha-release.md"
    release_notes.write_text(release_body(), encoding="utf-8")
    release_json = tmp_path / "gh-release.json"
    release_json.write_text(json.dumps(release or github_release_payload()), encoding="utf-8")
    return release_check_json, release_check_summary, release_notes, release_json


def test_run_post_release_check_writes_github_check_and_packet(tmp_path: Path) -> None:
    release_check_json, release_check_summary, release_notes, release_json = write_inputs(tmp_path)

    summary = post_release_check.run_post_release_check(
        version="0.1.8a0",
        release_check_json=release_check_json,
        release_check_summary_file=release_check_summary,
        release_notes_file=release_notes,
        release_json=release_json,
        output_dir=tmp_path / "post-release",
    )

    assert summary["schema_version"] == "agentledger.post_release_check.v1"
    assert summary["ok"] is True
    assert summary["status"] == "ready"
    assert Path(summary["summary_json"]).exists()
    assert Path(summary["summary_markdown"]).exists()
    assert Path(summary["github_release_check_json"]).exists()
    assert Path(summary["github_release_check_markdown"]).exists()
    packet = json.loads(Path(summary["release_evidence_packet_json"]).read_text(encoding="utf-8"))
    assert packet["schema_version"] == "agentledger.release_evidence_packet.v1"
    assert packet["private_evidence_included"] is False


def test_run_post_release_check_records_failed_github_release_check(tmp_path: Path) -> None:
    release_check_json, release_check_summary, release_notes, release_json = write_inputs(
        tmp_path,
        release=github_release_payload(isDraft=True),
    )

    summary = post_release_check.run_post_release_check(
        version="0.1.8a0",
        release_check_json=release_check_json,
        release_check_summary_file=release_check_summary,
        release_notes_file=release_notes,
        release_json=release_json,
        output_dir=tmp_path / "post-release",
    )

    assert summary["ok"] is False
    assert summary["status"] == "failed"
    assert summary["release_evidence_packet_json"] is None
    assert any("not draft" in error for error in summary["errors"])
    github_check = json.loads(Path(summary["github_release_check_json"]).read_text(encoding="utf-8"))
    assert github_check["ok"] is False


def test_main_reports_post_release_outputs(tmp_path: Path, capsys) -> None:
    release_check_json, release_check_summary, release_notes, release_json = write_inputs(tmp_path)
    output_dir = tmp_path / "post-release"

    exit_code = post_release_check.main(
        [
            "--version",
            "0.1.8a0",
            "--release-check-json",
            str(release_check_json),
            "--release-check-summary",
            str(release_check_summary),
            "--release-notes",
            str(release_notes),
            "--release-json",
            str(release_json),
            "--output-dir",
            str(output_dir),
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Post-release check: 0.1.8a0 -> v0.1.8-alpha" in output
    assert "Status: ready" in output
    assert f"Summary: {output_dir / 'agentledger-post-release-check.md'}" in output
    assert f"Release evidence packet JSON: {output_dir / 'agentledger-release-evidence.json'}" in output
