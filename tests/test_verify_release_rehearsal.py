from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_release_rehearsal.py"

spec = importlib.util.spec_from_file_location("verify_release_rehearsal", SCRIPT)
assert spec is not None
verify_release_rehearsal = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = verify_release_rehearsal
assert spec.loader is not None
spec.loader.exec_module(verify_release_rehearsal)


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


def write_rehearsal(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    write_release_repo(repo)
    result = verify_release_rehearsal.rehearse_release.rehearse_release(
        repo_root=repo,
        version="0.1.8a0",
        release_date="2026-06-15",
        output_dir=tmp_path / "rehearsal",
        require_clean_git=False,
        run_full_release_check=False,
    )
    return Path(result["manifest_json"])


def test_verify_release_rehearsal_manifest_reports_ready(tmp_path: Path) -> None:
    manifest = write_rehearsal(tmp_path)

    result = verify_release_rehearsal.verify_release_rehearsal_manifest(manifest)

    assert result["schema_version"] == "agentledger.release_rehearsal_manifest_verify.v1"
    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["package_version"] == "0.1.8a0"
    assert result["release_version"] == "0.1.8-alpha"
    assert result["output_dir"] == str(manifest.parent.resolve())
    assert result["artifact_count"] >= 6
    assert result["verified_artifacts"] == result["artifact_count"]
    assert result["errors"] == []


def test_verify_release_rehearsal_manifest_detects_hash_drift(tmp_path: Path) -> None:
    manifest = write_rehearsal(tmp_path)
    metadata = manifest.parent / "release-metadata.json"
    contents = bytearray(metadata.read_bytes())
    contents[-2] = ord("X") if contents[-2] != ord("X") else ord("Y")
    metadata.write_bytes(contents)

    result = verify_release_rehearsal.verify_release_rehearsal_manifest(manifest)

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert result["verified_artifacts"] == 0
    assert any("hash drifted" in error for error in result["errors"])


def test_main_writes_json_result(tmp_path: Path, capsys) -> None:
    manifest = write_rehearsal(tmp_path)
    output = tmp_path / "verify-result.json"

    exit_code = verify_release_rehearsal.main(
        [
            str(manifest),
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == (
        f"Release rehearsal manifest verification written: {output}\n"
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["manifest_json"] == str(manifest.resolve())


def test_main_returns_nonzero_for_invalid_manifest(tmp_path: Path, capsys) -> None:
    manifest = write_rehearsal(tmp_path)
    (manifest.parent / "release-command-index.json").unlink()

    exit_code = verify_release_rehearsal.main([str(manifest)])

    assert exit_code == 2
    output = capsys.readouterr().out
    assert "Release rehearsal manifest FAILED" in output
    assert "file is missing" in output
