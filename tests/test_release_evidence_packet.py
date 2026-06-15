from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_evidence_packet.py"

spec = importlib.util.spec_from_file_location("release_evidence_packet", SCRIPT)
assert spec is not None
release_evidence_packet = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release_evidence_packet
assert spec.loader is not None
spec.loader.exec_module(release_evidence_packet)


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

- Added release evidence packet tooling.

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


def write_inputs(tmp_path: Path, *, github_payload: dict | None = None) -> tuple[Path, Path, Path, Path]:
    release_payload = release_check_payload()
    release_check_json = tmp_path / "agentledger-release-check.json"
    release_check_json.write_text(json.dumps(release_payload), encoding="utf-8")
    release_check_summary = tmp_path / "agentledger-release-check-summary.md"
    release_check_summary.write_text(
        release_evidence_packet.release_check_summary.render_release_check_markdown(release_payload),
        encoding="utf-8",
    )
    notes = tmp_path / "agentledger-0.1.8-alpha-release.md"
    notes.write_text(release_notes_body(), encoding="utf-8")
    github_json = tmp_path / "agentledger-github-release-check.json"
    github_json.write_text(json.dumps(github_payload or github_release_check_payload()), encoding="utf-8")
    return release_check_json, release_check_summary, notes, github_json


def test_build_release_evidence_packet_summarizes_validated_artifacts(tmp_path: Path) -> None:
    release_check_json, release_check_summary, notes, github_json = write_inputs(tmp_path)

    packet = release_evidence_packet.build_release_evidence_packet(
        version="0.1.8a0",
        release_check_json=release_check_json,
        release_check_summary_file=release_check_summary,
        release_notes_file=notes,
        github_release_check_json=github_json,
    )
    markdown = release_evidence_packet.render_release_evidence_packet_markdown(packet)

    assert packet["schema_version"] == "agentledger.release_evidence_packet.v1"
    assert packet["private_evidence_included"] is False
    assert packet["release_check"]["metadata_checks_passed"] == 2
    assert packet["github_release_check"]["checks_failed"] == 0
    assert str(tmp_path) not in json.dumps(packet)
    assert "Added release evidence packet tooling" not in markdown
    assert markdown.startswith("# AgentLedger Release Evidence Packet\n")
    assert "https://github.com/Martin123132/AgentLedger/releases/tag/v0.1.8-alpha" in markdown
    assert "| release-notes | agentledger-0.1.8-alpha-release.md | validated summary only |" in markdown


def test_main_writes_markdown_and_json_packets(tmp_path: Path, capsys) -> None:
    release_check_json, release_check_summary, notes, github_json = write_inputs(tmp_path)
    markdown_output = tmp_path / "agentledger-release-evidence.md"
    json_output = tmp_path / "agentledger-release-evidence.json"

    exit_code = release_evidence_packet.main(
        [
            "--version",
            "0.1.8a0",
            "--release-check-json",
            str(release_check_json),
            "--release-check-summary",
            str(release_check_summary),
            "--release-notes",
            str(notes),
            "--github-release-check-json",
            str(github_json),
            "--output",
            str(markdown_output),
            "--json-output",
            str(json_output),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == (
        f"Release evidence packet written: {markdown_output}, {json_output}\n"
    )
    assert markdown_output.read_text(encoding="utf-8").startswith(
        "# AgentLedger Release Evidence Packet\n"
    )
    assert json.loads(json_output.read_text(encoding="utf-8"))["ok"] is True


def test_build_release_evidence_packet_rejects_private_evidence_paths(tmp_path: Path) -> None:
    release_check_json, release_check_summary, notes, github_json = write_inputs(tmp_path)
    private_dir = tmp_path / ".agentledger"
    private_dir.mkdir()
    private_release_check = private_dir / release_check_json.name
    private_release_check.write_text(release_check_json.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(release_evidence_packet.ReleaseEvidencePacketError) as error:
        release_evidence_packet.build_release_evidence_packet(
            version="0.1.8a0",
            release_check_json=private_release_check,
            release_check_summary_file=release_check_summary,
            release_notes_file=notes,
            github_release_check_json=github_json,
        )

    assert ".agentledger" in str(error.value)


def test_build_release_evidence_packet_rejects_failed_github_release_check(tmp_path: Path) -> None:
    github_payload = github_release_check_payload(
        ok=False,
        status="failed",
        errors=["release body: Missing ## Validation section."],
    )
    release_check_json, release_check_summary, notes, github_json = write_inputs(
        tmp_path,
        github_payload=github_payload,
    )

    with pytest.raises(release_evidence_packet.ReleaseEvidencePacketError) as error:
        release_evidence_packet.build_release_evidence_packet(
            version="0.1.8a0",
            release_check_json=release_check_json,
            release_check_summary_file=release_check_summary,
            release_notes_file=notes,
            github_release_check_json=github_json,
        )

    assert "GitHub release check must have ok=true" in str(error.value)


def test_main_reports_stale_release_check_summary(tmp_path: Path, capsys) -> None:
    release_check_json, release_check_summary, notes, github_json = write_inputs(tmp_path)
    release_check_summary.write_text("# AgentLedger Release Readiness\n", encoding="utf-8")

    exit_code = release_evidence_packet.main(
        [
            "--version",
            "0.1.8a0",
            "--release-check-json",
            str(release_check_json),
            "--release-check-summary",
            str(release_check_summary),
            "--release-notes",
            str(notes),
            "--github-release-check-json",
            str(github_json),
        ]
    )

    assert exit_code == 2
    assert "does not match the JSON input" in capsys.readouterr().err
