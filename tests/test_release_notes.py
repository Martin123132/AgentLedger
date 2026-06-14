from __future__ import annotations

import importlib.util
from pathlib import Path


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
