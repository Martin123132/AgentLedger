from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_notes.py"

spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
assert spec is not None
release_notes = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(release_notes)


def test_extract_changelog_section_by_version() -> None:
    changelog = """# Changelog

## Unreleased

- Draft work.

## 0.1.7-alpha - 2026-06-14

- Added release checks.
- Added JSON contracts.

## 0.1.6-alpha - 2026-06-14

- Older work.
"""

    section = release_notes.extract_changelog_section(changelog, "v0.1.7-alpha")

    assert section == "- Added release checks.\n- Added JSON contracts."
    assert "Older work" not in section


def test_normalize_version_accepts_pep440_alpha_version() -> None:
    assert release_notes.normalize_version("v0.1.7-alpha") == "0.1.7-alpha"
    assert release_notes.normalize_version("0.1.7a0") == "0.1.7-alpha"
    assert release_notes.normalize_version("0.1.7a2") == "0.1.7-alpha.2"


def test_extract_changelog_section_accepts_project_alpha_version() -> None:
    changelog = """# Changelog

## 0.1.7-alpha - 2026-06-14

- Added release checks.
"""

    section = release_notes.extract_changelog_section(changelog, "0.1.7a0")

    assert section == "- Added release checks."


def test_build_release_notes_uses_changelog_validation_and_footer() -> None:
    changelog = """# Changelog

## 0.1.7-alpha - 2026-06-14

- Added release checks.
  with wrapped detail.
"""

    notes = release_notes.build_release_notes(
        version="0.1.7-alpha",
        changelog_text=changelog,
        validation_lines=[
            "- Local release check passed.",
            "- Tag CI passed.",
        ],
    )

    assert notes.startswith("## Highlights\n\n- Added release checks.")
    assert "  with wrapped detail." in notes
    assert "## Validation\n\n- Local release check passed.\n- Tag CI passed." in notes
    assert "This is an alpha prerelease." in notes


def test_build_release_notes_defaults_to_todo_validation_template() -> None:
    changelog = """# Changelog

## 0.1.7-alpha

- Added release checks.
"""

    notes = release_notes.build_release_notes(
        version="0.1.7-alpha",
        changelog_text=changelog,
    )

    assert "- TODO: Local `scripts/release-check.ps1` passed." in notes
    assert "- TODO: Tag CI passed for `v0.1.7-alpha`." in notes


def test_validate_publish_ready_accepts_completed_release_notes() -> None:
    changelog = """# Changelog

## 0.1.7-alpha

- Added release checks.
"""
    notes = release_notes.build_release_notes(
        version="0.1.7a0",
        changelog_text=changelog,
        validation_lines=[
            "- Local release-check passed from a clean branch.",
            "- PR CI passed: https://github.com/Martin123132/AgentLedger/actions/runs/123.",
            "- Release Readiness passed: https://github.com/Martin123132/AgentLedger/actions/runs/456.",
            "- Tag CI passed for `v0.1.7-alpha`: https://github.com/Martin123132/AgentLedger/actions/runs/789.",
        ],
    )

    release_notes.validate_publish_ready(version="0.1.7a0", notes_text=notes)


def test_validate_publish_ready_rejects_todo_release_notes() -> None:
    changelog = """# Changelog

## 0.1.7-alpha

- Added release checks.
"""
    notes = release_notes.build_release_notes(
        version="0.1.7-alpha",
        changelog_text=changelog,
    )

    with pytest.raises(release_notes.ReleaseNotesError) as error:
        release_notes.validate_publish_ready(version="0.1.7-alpha", notes_text=notes)

    assert "TODO validation placeholders" in str(error.value)


def test_validate_publish_ready_allows_todo_word_in_highlights() -> None:
    changelog = """# Changelog

## 0.1.7-alpha

- Added a checker that catches TODO validation placeholders before release.
"""
    notes = release_notes.build_release_notes(
        version="0.1.7-alpha",
        changelog_text=changelog,
        validation_lines=[
            "- Local release-check passed from a clean branch.",
            "- Tag CI passed for `v0.1.7-alpha`: https://github.com/Martin123132/AgentLedger/actions/runs/789.",
        ],
    )

    release_notes.validate_publish_ready(version="0.1.7-alpha", notes_text=notes)


def test_validate_publish_ready_reports_missing_release_sections() -> None:
    with pytest.raises(release_notes.ReleaseNotesError) as error:
        release_notes.validate_publish_ready(
            version="0.1.7a0",
            notes_text="- Tag CI passed for v0.1.7-alpha.\n",
        )

    message = str(error.value)
    assert "Missing ## Highlights section." in message
    assert "Missing ## Validation section." in message
    assert "Missing alpha prerelease evidence-handling footer." in message


def test_main_writes_output_file(tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    output = tmp_path / "notes.md"
    changelog.write_text(
        """# Changelog

## 0.1.7-alpha

- Added release checks.
""",
        encoding="utf-8",
    )

    exit_code = release_notes.main(
        [
            "--version",
            "0.1.7-alpha",
            "--changelog",
            str(changelog),
            "--output",
            str(output),
            "--validation-line",
            "- Release readiness passed.",
        ]
    )

    assert exit_code == 0
    assert "- Release readiness passed." in output.read_text(encoding="utf-8")


def test_main_check_publish_ready_accepts_completed_notes(tmp_path: Path, capsys) -> None:
    notes_file = tmp_path / "notes.md"
    notes_file.write_text(
        """## Highlights

- Added release checks.

## Validation

- Local release-check passed.
- Tag CI passed for `v0.1.7-alpha`.

This is an alpha prerelease. Do not commit or upload `.agentledger/` evidence folders, zip bundles, or signing keys unless the contents have been reviewed.
""",
        encoding="utf-8",
    )

    exit_code = release_notes.main(
        [
            "--version",
            "0.1.7a0",
            "--notes-file",
            str(notes_file),
            "--check-publish-ready",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == "Release notes publish check OK: 0.1.7-alpha.\n"


def test_main_check_publish_ready_rejects_todo_notes(tmp_path: Path, capsys) -> None:
    notes_file = tmp_path / "notes.md"
    notes_file.write_text(
        """## Highlights

- Added release checks.

## Validation

- TODO: Tag CI passed for `v0.1.7-alpha`.

This is an alpha prerelease. Do not commit or upload `.agentledger/` evidence folders, zip bundles, or signing keys unless the contents have been reviewed.
""",
        encoding="utf-8",
    )

    exit_code = release_notes.main(
        [
            "--version",
            "0.1.7a0",
            "--notes-file",
            str(notes_file),
            "--check-publish-ready",
        ]
    )

    assert exit_code == 2
    assert "TODO validation placeholders" in capsys.readouterr().err


def test_main_check_mode_accepts_project_alpha_version(tmp_path: Path, capsys) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(
        """# Changelog

## 0.1.7-alpha

- Added release checks.
""",
        encoding="utf-8",
    )

    exit_code = release_notes.main(
        [
            "--version",
            "0.1.7a0",
            "--changelog",
            str(changelog),
            "--check",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == "Release notes source OK: 0.1.7-alpha.\n"
