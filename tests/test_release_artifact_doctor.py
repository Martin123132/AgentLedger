from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_artifact_doctor.py"

spec = importlib.util.spec_from_file_location("release_artifact_doctor", SCRIPT)
assert spec is not None
release_artifact_doctor = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release_artifact_doctor
assert spec.loader is not None
spec.loader.exec_module(release_artifact_doctor)


def release_check_payload(**overrides) -> dict:
    payload = {
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
    payload.update(overrides)
    return payload


def release_notes_body() -> str:
    return """## Highlights

- Added release artifact doctor.

## Validation

- Local release-check passed for `0.1.8a0` at `abcdef1`; release metadata checks: 2 passed, 0 failed.
- PR CI passed on Ubuntu and Windows: https://github.com/Martin123132/AgentLedger/actions/runs/1001.
- Master CI passed for `abcdef1234567890`: https://github.com/Martin123132/AgentLedger/actions/runs/1002.
- Release Readiness passed on master: https://github.com/Martin123132/AgentLedger/actions/runs/1003.
- Tag CI passed for `v0.1.8-alpha`: https://github.com/Martin123132/AgentLedger/actions/runs/1004.

This is an alpha prerelease. Do not commit or upload `.agentledger/` evidence folders, zip bundles, or signing keys unless the contents have been reviewed.
"""


def github_release_check_payload(**overrides) -> dict:
    payload = {
        "schema_version": "agentledger.github_release_check.v1",
        "ok": True,
        "status": "ready",
        "repository": "Martin123132/AgentLedger",
        "version": "0.1.8a0",
        "release_label": "0.1.8-alpha",
        "tag": "v0.1.8-alpha",
        "release": {
            "tag_name": "v0.1.8-alpha",
            "name": "v0.1.8-alpha",
            "url": "https://github.com/Martin123132/AgentLedger/releases/tag/v0.1.8-alpha",
            "is_draft": False,
            "is_prerelease": True,
            "target_commitish": "abcdef1234567890",
            "created_at": "2026-06-15T05:00:00Z",
            "published_at": "2026-06-15T05:10:00Z",
        },
        "checks": [
            {"name": "release tag", "status": "passed", "detail": "tag is correct"},
            {"name": "not draft", "status": "passed", "detail": "not draft"},
            {"name": "release body", "status": "passed", "detail": "publish-ready"},
        ],
        "errors": [],
    }
    payload.update(overrides)
    return payload


def write_inputs(tmp_path: Path, *, release_payload: dict | None = None) -> dict[str, Path]:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        """# Changelog

## Unreleased

- Next work.

## 0.1.8-alpha - 2026-06-15

- Added release artifact doctor.
""",
        encoding="utf-8",
    )
    payload = release_payload or release_check_payload()
    release_check_json = tmp_path / "agentledger-release-check.json"
    release_check_json.write_text(json.dumps(payload), encoding="utf-8")
    release_check_summary = tmp_path / "agentledger-release-check-summary.md"
    release_check_summary.write_text(
        release_artifact_doctor.release_check_summary.render_release_check_markdown(payload),
        encoding="utf-8",
    )
    notes = tmp_path / "agentledger-0.1.8-alpha-release.md"
    notes.write_text(release_notes_body(), encoding="utf-8")
    github_check = tmp_path / "agentledger-github-release-check.json"
    github_check.write_text(json.dumps(github_release_check_payload()), encoding="utf-8")
    return {
        "changelog": changelog,
        "release_check_json": release_check_json,
        "release_check_summary": release_check_summary,
        "release_notes": notes,
        "github_release_check": github_check,
    }


def test_final_notes_stage_validates_release_check_and_changelog(tmp_path: Path) -> None:
    paths = write_inputs(tmp_path)

    result = release_artifact_doctor.check_release_artifacts(
        version="0.1.8a0",
        stage="final-notes",
        release_check_json=paths["release_check_json"],
        release_check_summary_file=paths["release_check_summary"],
        changelog=paths["changelog"],
    )

    assert result["schema_version"] == "agentledger.release_artifact_doctor.v1"
    assert result["ok"] is True
    assert result["status"] == "ready"
    assert {check["name"] for check in result["checks"]} >= {
        "CHANGELOG.md",
        "changelog release section",
        "release-check readiness for final notes",
    }


def test_post_release_stage_validates_publish_ready_notes(tmp_path: Path) -> None:
    paths = write_inputs(tmp_path)

    result = release_artifact_doctor.check_release_artifacts(
        version="0.1.8a0",
        stage="post-release",
        release_check_json=paths["release_check_json"],
        release_check_summary_file=paths["release_check_summary"],
        release_notes_file=paths["release_notes"],
    )

    assert result["ok"] is True
    assert any(check["name"] == "release notes publish readiness" for check in result["checks"])


def test_evidence_packet_stage_validates_github_release_check(tmp_path: Path) -> None:
    paths = write_inputs(tmp_path)

    result = release_artifact_doctor.check_release_artifacts(
        version="0.1.8a0",
        stage="evidence-packet",
        release_check_json=paths["release_check_json"],
        release_check_summary_file=paths["release_check_summary"],
        release_notes_file=paths["release_notes"],
        github_release_check_json=paths["github_release_check"],
    )

    assert result["ok"] is True
    assert any(check["name"] == "GitHub release check readiness" for check in result["checks"])


def test_doctor_reports_missing_artifacts_with_next_actions(tmp_path: Path) -> None:
    missing = tmp_path / "missing-release-check.json"
    result = release_artifact_doctor.check_release_artifacts(
        version="0.1.8a0",
        stage="post-release",
        release_check_json=missing,
        release_check_summary_file=None,
        release_notes_file=None,
    )

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert "Run `scripts/release-check.ps1 -RequireCleanGit -JsonOutput <path>`." in result["next_actions"]
    assert "Run `scripts/finalize_release_notes.py` with real CI URLs and merge SHA." in result["next_actions"]
    assert any(check["detail"] == "File does not exist." for check in result["checks"])


def test_main_writes_json_result(tmp_path: Path, capsys) -> None:
    paths = write_inputs(tmp_path)
    output = tmp_path / "release-artifact-doctor.json"

    exit_code = release_artifact_doctor.main(
        [
            "--version",
            "0.1.8a0",
            "--stage",
            "evidence-packet",
            "--release-check-json",
            str(paths["release_check_json"]),
            "--release-check-summary",
            str(paths["release_check_summary"]),
            "--release-notes",
            str(paths["release_notes"]),
            "--github-release-check-json",
            str(paths["github_release_check"]),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == f"Release artifact doctor written: {output}\n"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["stage"] == "evidence-packet"


def test_main_returns_nonzero_for_blocked_stage(tmp_path: Path, capsys) -> None:
    exit_code = release_artifact_doctor.main(
        [
            "--version",
            "0.1.8a0",
            "--stage",
            "post-release",
            "--release-check-json",
            str(tmp_path / "missing.json"),
        ]
    )

    assert exit_code == 2
    output = capsys.readouterr().out
    assert "Release artifact doctor BLOCKED: post-release" in output
    assert "Next actions:" in output
