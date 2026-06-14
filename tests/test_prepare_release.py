from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "prepare_release.py"

spec = importlib.util.spec_from_file_location("prepare_release", SCRIPT)
assert spec is not None
prepare_release = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = prepare_release
assert spec.loader is not None
spec.loader.exec_module(prepare_release)


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


def test_changelog_version_maps_pep440_alpha_version() -> None:
    assert prepare_release.changelog_version("0.1.8a0") == "0.1.8-alpha"
    assert prepare_release.changelog_version("0.1.8a2") == "0.1.8-alpha.2"
    assert prepare_release.changelog_version("0.1.8") == "0.1.8"


def test_prepare_release_updates_versions_and_moves_unreleased(tmp_path: Path) -> None:
    write_release_repo(tmp_path)

    result = prepare_release.prepare_release(
        repo_root=tmp_path,
        version="0.1.8a0",
        release_date="2026-06-15",
    )

    assert result.package_version == "0.1.8a0"
    assert result.release_version == "0.1.8-alpha"
    assert result.changed_files == (
        "pyproject.toml",
        "src/agentledger/__init__.py",
        "CHANGELOG.md",
    )
    assert 'version = "0.1.8a0"' in (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert '__version__ = "0.1.8a0"' in (
        tmp_path / "src" / "agentledger" / "__init__.py"
    ).read_text(encoding="utf-8")

    changelog = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## Unreleased\n\n## 0.1.8-alpha - 2026-06-15" in changelog
    assert "- Added release prep." in changelog
    assert changelog.index("## 0.1.8-alpha") < changelog.index("## 0.1.7-alpha")


def test_prepare_release_dry_run_does_not_write_files(tmp_path: Path) -> None:
    write_release_repo(tmp_path)
    before = (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8")

    result = prepare_release.prepare_release(
        repo_root=tmp_path,
        version="0.1.8a0",
        release_date="2026-06-15",
        dry_run=True,
    )

    assert result.dry_run is True
    assert (tmp_path / "CHANGELOG.md").read_text(encoding="utf-8") == before


def test_prepare_release_writes_release_notes_from_prepared_changelog(tmp_path: Path) -> None:
    write_release_repo(tmp_path)
    notes = tmp_path / "release-notes.md"

    result = prepare_release.prepare_release(
        repo_root=tmp_path,
        version="0.1.8a0",
        release_date="2026-06-15",
        release_notes_output=notes,
    )

    assert result.release_notes_output == str(notes)
    text = notes.read_text(encoding="utf-8")
    assert text.startswith("## Highlights\n\n- Added release prep.")
    assert "- TODO: Tag CI passed for `v0.1.8-alpha`." in text
    assert "This is an alpha prerelease." in text


def test_prepare_release_dry_run_does_not_write_release_notes(tmp_path: Path) -> None:
    write_release_repo(tmp_path)
    notes = tmp_path / "release-notes.md"

    result = prepare_release.prepare_release(
        repo_root=tmp_path,
        version="0.1.8a0",
        release_date="2026-06-15",
        release_notes_output=notes,
        dry_run=True,
    )

    assert result.release_notes_output == str(notes)
    assert not notes.exists()


def test_prepare_release_rejects_existing_release_section(tmp_path: Path) -> None:
    write_release_repo(tmp_path)

    try:
        prepare_release.prepare_release(
            repo_root=tmp_path,
            version="0.1.7a0",
            release_date="2026-06-15",
        )
    except prepare_release.ReleasePrepError as error:
        assert "already has a section for 0.1.7-alpha" in str(error)
    else:
        raise AssertionError("prepare_release should reject duplicate release sections")


def test_prepare_release_rejects_empty_unreleased_section(tmp_path: Path) -> None:
    write_release_repo(tmp_path, changelog_body="\n")

    try:
        prepare_release.prepare_release(
            repo_root=tmp_path,
            version="0.1.8a0",
            release_date="2026-06-15",
        )
    except prepare_release.ReleasePrepError as error:
        assert "Unreleased section is empty" in str(error)
    else:
        raise AssertionError("prepare_release should require release notes")


def test_main_dry_run_reports_changed_files(tmp_path: Path, capsys) -> None:
    write_release_repo(tmp_path)

    exit_code = prepare_release.main(
        [
            "--repo-root",
            str(tmp_path),
            "--version",
            "0.1.8a0",
            "--date",
            "2026-06-15",
            "--release-notes-output",
            "draft-release.md",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Release prep: 0.1.8a0 -> 0.1.8-alpha" in output
    assert "Dry run: no files written." in output
    assert "- CHANGELOG.md" in output
    assert f"Planned release notes: {tmp_path / 'draft-release.md'}" in output
