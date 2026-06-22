from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_readiness_report.py"

spec = importlib.util.spec_from_file_location("release_readiness_report", SCRIPT)
assert spec is not None
release_readiness_report = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release_readiness_report
assert spec.loader is not None
spec.loader.exec_module(release_readiness_report)


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def write_release_repo(root: Path) -> Path:
    repo = root / "repo"
    package_dir = repo / "src" / "agentledger"
    docs_dir = repo / "docs"
    package_dir.mkdir(parents=True)
    docs_dir.mkdir(parents=True)
    (repo / "pyproject.toml").write_text(
        """[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "agentledger"
version = "0.1.21a0"
description = "Local-first black box recorder for AI coding agents."
readme = "README.md"
requires-python = ">=3.10"
license = { text = "PolyForm Noncommercial License 1.0.0" }
authors = [{ name = "Martin Ollett" }]
dependencies = []
""",
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text(
        '"""AgentLedger package."""\n\n__version__ = "0.1.21a0"\n',
        encoding="utf-8",
    )
    (repo / "README.md").write_text(
        """# AgentLedger

Source-available for non-commercial use under the PolyForm Noncommercial License 1.0.0.
Commercial use requires separate permission.
""",
        encoding="utf-8",
    )
    (repo / "LICENSE").write_text("# PolyForm Noncommercial License 1.0.0\n", encoding="utf-8")
    (repo / "COMMERCIAL.md").write_text(
        "Commercial use is not granted by the public license.\n",
        encoding="utf-8",
    )
    (repo / "CHANGELOG.md").write_text(
        """# Changelog

## Unreleased

- Next work.

## 0.1.21-alpha - 2026-06-22

- Released work.
""",
        encoding="utf-8",
    )
    (docs_dir / "release-process.md").write_text(
        (ROOT / "docs" / "release-process.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    git(repo, "init")
    git(repo, "config", "user.email", "agentledger-report@example.local")
    git(repo, "config", "user.name", "AgentLedger Report Test")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "initial")
    return repo


def test_release_readiness_report_passes_for_clean_release_repo(tmp_path: Path) -> None:
    repo = write_release_repo(tmp_path)

    result = release_readiness_report.build_release_readiness_report(repo_root=repo)

    assert result["schema_version"] == "agentledger.release_readiness_report.v1"
    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["working_tree_dirty"] is False
    assert result["project_version"] == "0.1.21a0"
    assert result["release_date"] == "2026-06-22"
    assert result["release_metadata"]["ok"] is True
    assert result["release_process"]["ok"] is True
    assert result["summary"] == {"total": 6, "passed": 6, "warnings": 0, "failed": 0}
    assert [check["name"] for check in result["checks"]] == [
        "release metadata",
        "release process docs",
        "release notes source",
        "diff whitespace",
        "tracked private artifacts",
        "working tree",
    ]


def test_release_readiness_report_warns_for_dirty_worktree_by_default(tmp_path: Path) -> None:
    repo = write_release_repo(tmp_path)
    with (repo / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("\nLocal edit.\n")

    result = release_readiness_report.build_release_readiness_report(repo_root=repo)

    assert result["ok"] is True
    assert result["status"] == "ready_with_warnings"
    assert result["working_tree_dirty"] is True
    assert result["summary"]["warnings"] == 1
    assert any(check["name"] == "working tree" and check["status"] == "warning" for check in result["checks"])
    assert result["next_actions"] == [
        "Rerun with --require-clean-git from a clean checkout before tagging."
    ]


def test_release_readiness_report_can_require_clean_git(tmp_path: Path) -> None:
    repo = write_release_repo(tmp_path)
    with (repo / "README.md").open("a", encoding="utf-8") as handle:
        handle.write("\nLocal edit.\n")

    result = release_readiness_report.build_release_readiness_report(
        repo_root=repo,
        require_clean_git=True,
    )

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["summary"]["failed"] == 1
    assert any(check["name"] == "working tree" and check["status"] == "failed" for check in result["checks"])


def test_main_writes_json_report(tmp_path: Path, capsys) -> None:
    repo = write_release_repo(tmp_path)
    output = tmp_path / "release-readiness-report.json"

    exit_code = release_readiness_report.main(
        ["--repo-root", str(repo), "--format", "json", "--output", str(output)]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == f"Release readiness report written: {output}\n"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "agentledger.release_readiness_report.v1"
    assert payload["ok"] is True


def test_format_markdown_includes_check_table(tmp_path: Path) -> None:
    repo = write_release_repo(tmp_path)
    result = release_readiness_report.build_release_readiness_report(repo_root=repo)

    markdown = release_readiness_report.format_markdown(result)

    assert markdown.startswith("# AgentLedger Release Readiness Report\n")
    assert "- Result: ready" in markdown
    assert "| release | release metadata | passed |" in markdown
