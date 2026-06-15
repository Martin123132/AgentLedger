from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_check_summary.py"

spec = importlib.util.spec_from_file_location("release_check_summary", SCRIPT)
assert spec is not None
release_check_summary = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release_check_summary
assert spec.loader is not None
spec.loader.exec_module(release_check_summary)


def sample_release_check_payload() -> dict:
    return {
        "schema_version": "agentledger.release_check.v1",
        "ok": True,
        "status": "ready",
        "repo": "D:\\Projects\\AgentLedger",
        "branch": "master",
        "head": "abc1234",
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
        "release_process": {
            "schema_version": "agentledger.release_process_check.v1",
            "ok": True,
            "status": "ready",
            "version": "0.1.8a0",
            "release_label": "0.1.8-alpha",
            "release_date": "2026-06-14",
            "repository": "Martin123132/AgentLedger",
            "doc": "D:\\Projects\\AgentLedger\\docs\\release-process.md",
            "index_schema_version": "agentledger.release_command_index.v1",
            "summary": {"total": 64, "passed": 64, "failed": 0},
            "checks": [],
            "errors": [],
            "next_actions": [],
        },
        "steps": [
            {"name": "Check release versions", "status": "passed", "seconds": 0.2, "error": None},
            {"name": "Check release metadata", "status": "passed", "seconds": 0.3, "error": None},
            {"name": "Check release process docs", "status": "passed", "seconds": 0.1, "error": None},
        ],
        "error": None,
    }


def test_render_release_check_markdown_includes_metadata_and_steps() -> None:
    markdown = release_check_summary.render_release_check_markdown(sample_release_check_payload())

    assert markdown.startswith("# AgentLedger Release Readiness\n")
    assert "- Result: passed" in markdown
    assert "- Release label: 0.1.8-alpha" in markdown
    assert "- Checks: 2 passed, 0 failed" in markdown
    assert "## Release Process" in markdown
    assert "- Checks: 64 passed, 0 failed, 64 total" in markdown
    assert "| Check release metadata | passed | 0.3 | n/a |" in markdown
    assert "| Check release process docs | passed | 0.1 | n/a |" in markdown
    assert "PolyForm Noncommercial License 1.0.0" in markdown


def test_render_release_check_markdown_allows_failed_summary_without_metadata() -> None:
    payload = sample_release_check_payload()
    payload["ok"] = False
    payload["status"] = "failed"
    payload["release_metadata"] = None
    payload["steps"] = [
        {
            "name": "Install editable package",
            "status": "failed",
            "seconds": 4.1,
            "error": "pip failed",
        }
    ]
    payload["error"] = "pip failed"

    markdown = release_check_summary.render_release_check_markdown(payload)

    assert "- Result: failed" in markdown
    assert "- Status: not available" in markdown
    assert "| Install editable package | failed | 4.1 | pip failed |" in markdown
    assert "## Error\n\npip failed" in markdown


def test_render_release_check_markdown_allows_early_failed_summary() -> None:
    payload = {
        "schema_version": "agentledger.release_check.v1",
        "ok": False,
        "status": "failed",
        "repo": None,
        "branch": None,
        "head": None,
        "agentledger_version": None,
        "package_version": None,
        "release_metadata": None,
        "steps": [],
        "error": "Could not find [project] version in pyproject.toml",
    }

    markdown = release_check_summary.render_release_check_markdown(payload)

    assert "- Result: failed" in markdown
    assert "- Version: n/a" in markdown
    assert "Could not find [project] version" in markdown


def test_validate_rejects_passing_summary_without_metadata() -> None:
    payload = sample_release_check_payload()
    payload["release_metadata"] = None

    with pytest.raises(release_check_summary.ReleaseCheckSummaryError) as error:
        release_check_summary.validate_release_check(payload)

    assert "release_metadata is required when ok is true" in str(error.value)


def test_validate_rejects_passing_summary_without_release_process() -> None:
    payload = sample_release_check_payload()
    payload["release_process"] = None

    with pytest.raises(release_check_summary.ReleaseCheckSummaryError) as error:
        release_check_summary.validate_release_check(payload)

    assert "release_process is required when ok is true" in str(error.value)


def test_main_writes_markdown_summary(tmp_path: Path, capsys) -> None:
    summary_json = tmp_path / "agentledger-release-check.json"
    output = tmp_path / "agentledger-release-check-summary.md"
    summary_json.write_text(json.dumps(sample_release_check_payload()), encoding="utf-8")

    exit_code = release_check_summary.main([str(summary_json), "--output", str(output)])

    assert exit_code == 0
    assert capsys.readouterr().out == ""
    assert output.read_text(encoding="utf-8").startswith("# AgentLedger Release Readiness\n")


def test_main_reports_invalid_json_shape(tmp_path: Path, capsys) -> None:
    summary_json = tmp_path / "agentledger-release-check.json"
    summary_json.write_text(
        json.dumps({"schema_version": "agentledger.release_check.v1", "ok": True}),
        encoding="utf-8",
    )

    exit_code = release_check_summary.main([str(summary_json)])

    assert exit_code == 2
    assert "status must be a non-empty string" in capsys.readouterr().err
