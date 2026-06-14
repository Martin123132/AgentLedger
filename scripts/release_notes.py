from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANGELOG = ROOT / "CHANGELOG.md"
ALPHA_FOOTER = (
    "This is an alpha prerelease. Do not commit or upload `.agentledger/` "
    "evidence folders, zip bundles, or signing keys unless the contents have "
    "been reviewed."
)

HEADING_RE = re.compile(r"^## (?P<title>.+?)\s*$")


class ReleaseNotesError(ValueError):
    pass


def normalize_version(version: str) -> str:
    normalized = version.strip()
    if normalized.startswith("v"):
        normalized = normalized[1:]
    if not normalized:
        raise ReleaseNotesError("Version must not be empty.")
    return normalized


def section_version(title: str) -> str:
    return title.split(" - ", 1)[0].strip()


def extract_changelog_section(changelog_text: str, version: str) -> str:
    wanted = normalize_version(version)
    lines = changelog_text.splitlines()
    start: int | None = None

    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match and section_version(match.group("title")) == wanted:
            start = index + 1
            break

    if start is None:
        raise ReleaseNotesError(f"Could not find changelog section for {wanted}.")

    end = len(lines)
    for index in range(start, len(lines)):
        if HEADING_RE.match(lines[index]):
            end = index
            break

    body = "\n".join(lines[start:end]).strip()
    if not body:
        raise ReleaseNotesError(f"Changelog section for {wanted} is empty.")
    return body


def default_validation_lines(version: str) -> list[str]:
    normalized = normalize_version(version)
    return [
        "- TODO: Local `scripts/release-check.ps1` passed.",
        "- TODO: Local `scripts/release-check.ps1 -SkipEditableInstall -RequireCleanGit` passed from a clean committed branch.",
        "- TODO: PR CI passed on Ubuntu and Windows.",
        "- TODO: Master CI passed at `<merge-sha>`.",
        f"- TODO: Tag CI passed for `v{normalized}`.",
    ]


def build_release_notes(
    *,
    version: str,
    changelog_text: str,
    validation_lines: list[str] | None = None,
    include_alpha_footer: bool = True,
) -> str:
    normalized = normalize_version(version)
    highlights = extract_changelog_section(changelog_text, normalized)
    validation = validation_lines if validation_lines is not None else default_validation_lines(normalized)
    validation_block = "\n".join(line.rstrip() for line in validation if line.strip())
    if not validation_block:
        raise ReleaseNotesError("At least one validation line is required.")

    parts = [
        "## Highlights",
        highlights,
        "## Validation",
        validation_block,
    ]
    if include_alpha_footer:
        parts.append(ALPHA_FOOTER)
    return "\n\n".join(parts).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate draft GitHub release notes from CHANGELOG.md."
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Changelog version to extract, with or without a leading v.",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=DEFAULT_CHANGELOG,
        help="Path to CHANGELOG.md. Defaults to the repository changelog.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write notes to this file instead of stdout.",
    )
    parser.add_argument(
        "--validation-line",
        action="append",
        dest="validation_lines",
        help="Validation bullet to include. Repeat to replace the default TODO validation template.",
    )
    parser.add_argument(
        "--no-alpha-footer",
        action="store_true",
        help="Omit the alpha prerelease evidence-handling footer.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        changelog_text = args.changelog.read_text(encoding="utf-8-sig")
        notes = build_release_notes(
            version=args.version,
            changelog_text=changelog_text,
            validation_lines=args.validation_lines,
            include_alpha_footer=not args.no_alpha_footer,
        )
    except (OSError, ReleaseNotesError) as error:
        print(f"release_notes.py: {error}", file=sys.stderr)
        return 2

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(notes, encoding="utf-8")
    else:
        print(notes, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
