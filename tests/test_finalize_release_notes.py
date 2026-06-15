from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finalize_release_notes.py"

spec = importlib.util.spec_from_file_location("finalize_release_notes", SCRIPT)
assert spec is not None
finalize_release_notes = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = finalize_release_notes
assert spec.loader is not None
spec.loader.exec_module(finalize_release_notes)


RUN_1 = "https://github.com/Martin123132/AgentLedger/actions/runs/1001"
RUN_2 = "https://github.com/Martin123132/AgentLedger/actions/runs/1002"
RUN_3 = "https://github.com/Martin123132/AgentLedger/actions/runs/1003"
RUN_4 = "https://github.com/Martin123132/AgentLedger/actions/runs/1004"


def sample_release_check_payload(**overrides) -> dict:
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


def write_release_inputs(tmp_path: Path, payload: dict | None = None) -> tuple[Path, Path, Path]:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        """# Changelog

## Unreleased

- Next work.

## 0.1.8-alpha - 2026-06-15

- Added guarded release notes finalization.
""",
        encoding="utf-8",
    )
    release_check_json = tmp_path / "agentledger-release-check.json"
    release_payload = payload or sample_release_check_payload()
    release_check_json.write_text(json.dumps(release_payload), encoding="utf-8")
    summary = tmp_path / "agentledger-release-check-summary.md"
    summary.write_text(
        finalize_release_notes.release_check_summary.render_release_check_markdown(release_payload),
        encoding="utf-8",
    )
    return changelog, release_check_json, summary


def finalize_args(changelog: Path, release_check_json: Path, summary: Path, output: Path) -> list[str]:
    return [
        "--version",
        "0.1.8a0",
        "--changelog",
        str(changelog),
        "--release-check-json",
        str(release_check_json),
        "--release-check-summary",
        str(summary),
        "--pr-ci-url",
        RUN_1,
        "--master-ci-url",
        RUN_2,
        "--release-readiness-url",
        RUN_3,
        "--tag-ci-url",
        RUN_4,
        "--merge-sha",
        "abcdef1234567890",
        "--output",
        str(output),
    ]


def test_finalize_release_notes_builds_publish_ready_notes(tmp_path: Path) -> None:
    changelog, release_check_json, summary = write_release_inputs(tmp_path)

    notes = finalize_release_notes.finalize_release_notes(
        version="0.1.8a0",
        changelog=changelog,
        release_check_json=release_check_json,
        release_check_summary_file=summary,
        pr_ci_url=RUN_1,
        master_ci_url=RUN_2,
        release_readiness_url=RUN_3,
        tag_ci_url=RUN_4,
        merge_sha="abcdef1234567890",
    )

    assert "## Highlights" in notes
    assert "- Added guarded release notes finalization." in notes
    assert "Local release-check passed for `0.1.8a0` at `abcdef1`" in notes
    assert "release metadata checks: 2 passed, 0 failed" in notes
    assert f"Tag CI passed for `v0.1.8-alpha`: {RUN_4}." in notes
    assert "TODO" not in notes
    finalize_release_notes.release_notes.validate_publish_ready(
        version="0.1.8a0",
        notes_text=notes,
    )


def test_finalize_release_notes_rejects_dirty_release_check(tmp_path: Path) -> None:
    payload = sample_release_check_payload(
        status="passed_with_dirty_tree",
        require_clean_git=False,
        working_tree_dirty=True,
    )
    changelog, release_check_json, summary = write_release_inputs(tmp_path, payload)

    with pytest.raises(finalize_release_notes.FinalizeReleaseNotesError) as error:
        finalize_release_notes.finalize_release_notes(
            version="0.1.8a0",
            changelog=changelog,
            release_check_json=release_check_json,
            release_check_summary_file=summary,
            pr_ci_url=RUN_1,
            master_ci_url=RUN_2,
            release_readiness_url=RUN_3,
            tag_ci_url=RUN_4,
            merge_sha="abcdef1234567890",
        )

    assert "status=ready from a clean checkout" in str(error.value)


def test_finalize_release_notes_rejects_stale_rendered_summary(tmp_path: Path) -> None:
    changelog, release_check_json, summary = write_release_inputs(tmp_path)
    summary.write_text("# AgentLedger Release Readiness\n\n## Release Metadata\n", encoding="utf-8")

    with pytest.raises(finalize_release_notes.FinalizeReleaseNotesError) as error:
        finalize_release_notes.finalize_release_notes(
            version="0.1.8a0",
            changelog=changelog,
            release_check_json=release_check_json,
            release_check_summary_file=summary,
            pr_ci_url=RUN_1,
            master_ci_url=RUN_2,
            release_readiness_url=RUN_3,
            tag_ci_url=RUN_4,
            merge_sha="abcdef1234567890",
        )

    assert "Markdown summary is missing expected fragment" in str(error.value)


def test_finalize_release_notes_rejects_non_actions_urls(tmp_path: Path) -> None:
    changelog, release_check_json, summary = write_release_inputs(tmp_path)

    with pytest.raises(finalize_release_notes.FinalizeReleaseNotesError) as error:
        finalize_release_notes.finalize_release_notes(
            version="0.1.8a0",
            changelog=changelog,
            release_check_json=release_check_json,
            release_check_summary_file=summary,
            pr_ci_url="https://example.com/actions/runs/1001",
            master_ci_url=RUN_2,
            release_readiness_url=RUN_3,
            tag_ci_url=RUN_4,
            merge_sha="abcdef1234567890",
        )

    assert "pr-ci-url must be a GitHub Actions run URL" in str(error.value)


def test_main_writes_final_release_notes(tmp_path: Path, capsys) -> None:
    changelog, release_check_json, summary = write_release_inputs(tmp_path)
    output = tmp_path / "agentledger-0.1.8-alpha-release.md"

    exit_code = finalize_release_notes.main(
        finalize_args(changelog, release_check_json, summary, output)
    )

    assert exit_code == 0
    assert capsys.readouterr().out == f"Final release notes ready: {output}\n"
    assert f"Release Readiness passed on master: {RUN_3}." in output.read_text(encoding="utf-8")


def test_main_reports_finalize_errors(tmp_path: Path, capsys) -> None:
    changelog, release_check_json, summary = write_release_inputs(tmp_path)
    output = tmp_path / "release.md"
    args = finalize_args(changelog, release_check_json, summary, output)
    args[args.index("--merge-sha") + 1] = "not-a-sha"

    exit_code = finalize_release_notes.main(args)

    assert exit_code == 2
    assert "merge SHA must be 7 to 40 hexadecimal characters" in capsys.readouterr().err
