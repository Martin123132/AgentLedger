from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "rehearse_release.py"

spec = importlib.util.spec_from_file_location("rehearse_release", SCRIPT)
assert spec is not None
rehearse_release = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = rehearse_release
assert spec.loader is not None
spec.loader.exec_module(rehearse_release)


def write_release_repo(root: Path, changelog_body: str = "- Added release prep.\n") -> None:
    package_dir = root / "src" / "agentledger"
    package_dir.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "agentledger"
version = "0.1.7a0"
description = "Local-first black box recorder for AI coding agents."
requires-python = ">=3.10"
license = { text = "PolyForm Noncommercial License 1.0.0" }
authors = [{ name = "Martin Ollett" }]
dependencies = []
""",
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text(
        '__version__ = "0.1.7a0"\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(
        f"""# Changelog

## Unreleased

{changelog_body}
## 0.1.7-alpha - 2026-06-14

- Previous release.
""",
        encoding="utf-8",
    )
    (root / "README.md").write_text(
        """# AgentLedger

Source-available for non-commercial use under the PolyForm Noncommercial License 1.0.0.
Commercial use requires separate permission.
""",
        encoding="utf-8",
    )
    (root / "LICENSE").write_text(
        "# PolyForm Noncommercial License 1.0.0\n",
        encoding="utf-8",
    )
    (root / "COMMERCIAL.md").write_text(
        "Commercial use is not granted by the public license.\n",
        encoding="utf-8",
    )


def test_rehearsal_dry_run_writes_summary_without_mutating_repo(tmp_path: Path) -> None:
    write_release_repo(tmp_path)
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_text(encoding="utf-8")
        for path in [
            tmp_path / "pyproject.toml",
            tmp_path / "src" / "agentledger" / "__init__.py",
            tmp_path / "CHANGELOG.md",
        ]
    }

    result = rehearse_release.rehearse_release(
        repo_root=tmp_path,
        version="0.1.8a0",
        release_date="2026-06-15",
        output_dir=tmp_path / "rehearsal",
        require_clean_git=False,
        run_full_release_check=False,
    )

    assert result["ok"] is True
    assert result["status"] == "rehearsal_passed"
    assert result["release_version"] == "0.1.8-alpha"
    assert result["working_tree_dirty"] is None
    assert Path(result["release_command_index_json"]).exists()
    assert Path(result["release_command_index_markdown"]).exists()
    assert Path(result["release_metadata_json"]).exists()
    assert result["release_readiness_json"] is None
    assert any(
        step["name"] == "Fast release readiness report" and step["status"] == "skipped"
        for step in result["steps"]
    )

    draft_notes = Path(result["draft_release_notes"])
    assert draft_notes.exists()
    draft_text = draft_notes.read_text(encoding="utf-8")
    assert "- Added release prep." in draft_text
    assert "- TODO: Tag CI passed for `v0.1.8-alpha`." in draft_text

    summary_json = Path(result["summary_json"])
    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["schema_version"] == "agentledger.release_rehearsal.v1"
    assert summary["ok"] is True
    assert summary["release_command_index_markdown"].endswith("release-command-index.md")
    assert summary["release_metadata_json"].endswith("release-metadata.json")
    assert any(step["status"] == "pending" for step in summary["steps"])
    assert any(step["status"] == "skipped" for step in summary["steps"])
    summary_markdown = Path(result["summary_markdown"])
    assert summary_markdown.exists()
    summary_text = summary_markdown.read_text(encoding="utf-8")
    assert "- Release command index:" in summary_text
    assert "- Release metadata JSON:" in summary_text
    assert "- Fast readiness report: not written" in summary_text

    after = {
        path.relative_to(tmp_path).as_posix(): path.read_text(encoding="utf-8")
        for path in [
            tmp_path / "pyproject.toml",
            tmp_path / "src" / "agentledger" / "__init__.py",
            tmp_path / "CHANGELOG.md",
        ]
    }
    assert after == before


def test_rehearsal_reports_release_prep_failure(tmp_path: Path) -> None:
    write_release_repo(tmp_path, changelog_body="\n")

    result = rehearse_release.rehearse_release(
        repo_root=tmp_path,
        version="0.1.8a0",
        release_date="2026-06-15",
        output_dir=tmp_path / "rehearsal",
        require_clean_git=False,
        run_full_release_check=False,
    )

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["steps"][-1]["name"] == "Release prep dry run"
    assert "Unreleased section is empty" in result["steps"][-1]["detail"]
    assert Path(result["summary_json"]).exists()


def test_rehearsal_records_release_check_summary_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_release_repo(tmp_path)

    def fake_release_check(repo_root: Path, output_dir: Path) -> dict[str, object]:
        json_path = output_dir / "release-check.json"
        summary_path = output_dir / "release-check-summary.md"
        log_path = output_dir / "release-check.log"
        json_path.write_text('{"ok": true, "status": "ready"}\n', encoding="utf-8")
        summary_path.write_text("# AgentLedger Release Readiness\n", encoding="utf-8")
        log_path.write_text("release-check passed\n", encoding="utf-8")
        return {
            "json": str(json_path),
            "summary": str(summary_path),
            "log": str(log_path),
            "status": "ready",
            "steps": 3,
        }

    monkeypatch.setattr(rehearse_release, "run_release_check", fake_release_check)

    result = rehearse_release.rehearse_release(
        repo_root=tmp_path,
        version="0.1.8a0",
        release_date="2026-06-15",
        output_dir=tmp_path / "rehearsal",
        require_clean_git=False,
        run_full_release_check=True,
    )

    assert result["ok"] is True
    assert result["release_check_summary"] == str(tmp_path / "rehearsal" / "release-check-summary.md")
    summary_text = Path(result["summary_markdown"]).read_text(encoding="utf-8")
    assert f"- Release-check summary: {result['release_check_summary']}" in summary_text
    assert "Use the release-check JSON and summary paths" in summary_text


def test_rehearsal_records_fast_readiness_report_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_release_repo(tmp_path)

    monkeypatch.setattr(
        rehearse_release,
        "collect_git_state",
        lambda repo_root, *, require_clean_git: {
            "branch": "release-test",
            "head": "abc1234",
            "working_tree_dirty": False,
            "status": "",
            "skipped": False,
        },
    )

    def fake_readiness(
        repo_root: Path,
        output_dir: Path,
        *,
        require_clean_git: bool,
    ) -> dict[str, str]:
        json_path = output_dir / "release-readiness-report.json"
        markdown_path = output_dir / "release-readiness-report.md"
        json_path.write_text('{"ok": true, "status": "ready"}\n', encoding="utf-8")
        markdown_path.write_text("# AgentLedger Release Readiness Report\n", encoding="utf-8")
        return {
            "json": str(json_path),
            "markdown": str(markdown_path),
            "status": "ready",
            "checks": "6",
        }

    monkeypatch.setattr(
        rehearse_release,
        "write_release_readiness_report",
        fake_readiness,
    )

    result = rehearse_release.rehearse_release(
        repo_root=tmp_path,
        version="0.1.8a0",
        release_date="2026-06-15",
        output_dir=tmp_path / "rehearsal",
        require_clean_git=True,
        run_full_release_check=False,
    )

    assert result["ok"] is True
    assert result["release_readiness_json"] == str(
        tmp_path / "rehearsal" / "release-readiness-report.json"
    )
    assert result["release_readiness_markdown"] == str(
        tmp_path / "rehearsal" / "release-readiness-report.md"
    )
    summary_text = Path(result["summary_markdown"]).read_text(encoding="utf-8")
    assert "- Fast readiness report:" in summary_text
    assert "release-readiness-report.md" in summary_text


def test_main_skip_release_check(tmp_path: Path, capsys) -> None:
    write_release_repo(tmp_path)

    exit_code = rehearse_release.main(
        [
            "--repo-root",
            str(tmp_path),
            "--version",
            "0.1.8a0",
            "--date",
            "2026-06-15",
            "--output-dir",
            str(tmp_path / "rehearsal"),
            "--allow-dirty",
            "--skip-release-check",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Release rehearsal: 0.1.8a0 -> 0.1.8-alpha" in output
    assert "Status: rehearsal_passed" in output
