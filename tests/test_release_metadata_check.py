from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_release_metadata.py"

spec = importlib.util.spec_from_file_location("check_release_metadata", SCRIPT)
assert spec is not None
check_release_metadata = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_release_metadata
assert spec.loader is not None
spec.loader.exec_module(check_release_metadata)


def write_release_repo(
    root: Path,
    *,
    pyproject_version: str = "0.1.8a0",
    package_version: str = "0.1.8a0",
    changelog_label: str = "0.1.8-alpha",
) -> None:
    package_dir = root / "src" / "agentledger"
    package_dir.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        f'''[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "agentledger"
version = "{pyproject_version}"
description = "Local-first black box recorder for AI coding agents."
readme = "README.md"
requires-python = ">=3.10"
license = {{ text = "PolyForm Noncommercial License 1.0.0" }}
authors = [{{ name = "Martin Ollett" }}]
dependencies = []
''',
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text(
        f'"""AgentLedger package."""\n\n__version__ = "{package_version}"\n',
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
    (root / "CHANGELOG.md").write_text(
        f"""# Changelog

## Unreleased

- Next work.

## {changelog_label} - 2026-06-14

- Released work.
""",
        encoding="utf-8",
    )


def test_release_metadata_check_passes_for_current_public_metadata(tmp_path: Path) -> None:
    write_release_repo(tmp_path)

    result = check_release_metadata.check_release_metadata(tmp_path)

    assert result["schema_version"] == "agentledger.release_metadata_check.v1"
    assert result["ok"] is True
    assert result["project_name"] == "agentledger"
    assert result["project_version"] == "0.1.8a0"
    assert result["package_version"] == "0.1.8a0"
    assert result["release_label"] == "0.1.8-alpha"
    assert result["errors"] == []


def test_release_metadata_check_reports_version_mismatch(tmp_path: Path) -> None:
    write_release_repo(tmp_path, package_version="0.1.7a0")

    result = check_release_metadata.check_release_metadata(tmp_path)

    assert result["ok"] is False
    assert any("package version" in error for error in result["errors"])
    assert any("0.1.7a0" in error and "0.1.8a0" in error for error in result["errors"])


def test_release_metadata_check_reports_missing_current_changelog_section(tmp_path: Path) -> None:
    write_release_repo(tmp_path, changelog_label="0.1.7-alpha")

    result = check_release_metadata.check_release_metadata(tmp_path)

    assert result["ok"] is False
    assert any("current release changelog" in error for error in result["errors"])
    assert any("0.1.8-alpha" in error for error in result["errors"])


def test_release_metadata_main_json_output(tmp_path: Path, capsys) -> None:
    write_release_repo(tmp_path)

    exit_code = check_release_metadata.main(
        ["--repo-root", str(tmp_path), "--format", "json"]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["release_label"] == "0.1.8-alpha"
