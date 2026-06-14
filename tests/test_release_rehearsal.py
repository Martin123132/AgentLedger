from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


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

    draft_notes = Path(result["draft_release_notes"])
    assert draft_notes.exists()
    draft_text = draft_notes.read_text(encoding="utf-8")
    assert "- Added release prep." in draft_text
    assert "- TODO: Tag CI passed for `v0.1.8-alpha`." in draft_text

    summary_json = Path(result["summary_json"])
    summary = json.loads(summary_json.read_text(encoding="utf-8"))
    assert summary["schema_version"] == "agentledger.release_rehearsal.v1"
    assert summary["ok"] is True
    assert any(step["status"] == "pending" for step in summary["steps"])
    assert any(step["status"] == "skipped" for step in summary["steps"])
    assert Path(result["summary_markdown"]).exists()

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
