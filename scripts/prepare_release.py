from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
import importlib.util
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
RELEASE_NOTES_SCRIPT = ROOT / "scripts" / "release_notes.py"

PACKAGE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:a\d+)?$")
PEP440_ALPHA_RE = re.compile(r"^(?P<base>\d+\.\d+\.\d+)a(?P<number>\d+)$")
HEADING_RE = re.compile(r"^## (?P<title>.+?)\s*$")


class ReleasePrepError(ValueError):
    pass


@dataclass(frozen=True)
class ReleasePrepResult:
    package_version: str
    release_version: str
    release_date: str
    changed_files: tuple[str, ...]
    release_notes_output: str | None
    dry_run: bool


def validate_package_version(version: str) -> str:
    normalized = version.strip()
    if not normalized:
        raise ReleasePrepError("Version must not be empty.")
    if normalized.startswith("v") or "-" in normalized:
        raise ReleasePrepError(
            "Use the PEP 440 package version, for example 0.1.8a0, not a tag or changelog label."
        )
    if not PACKAGE_VERSION_RE.match(normalized):
        raise ReleasePrepError(
            "Version must look like 0.1.8 or 0.1.8a0 for the current alpha release flow."
        )
    return normalized


def changelog_version(package_version: str) -> str:
    normalized = validate_package_version(package_version)
    match = PEP440_ALPHA_RE.match(normalized)
    if not match:
        return normalized

    alpha_number = int(match.group("number"))
    if alpha_number == 0:
        return f"{match.group('base')}-alpha"
    return f"{match.group('base')}-alpha.{alpha_number}"


def validate_release_date(release_date: str) -> str:
    normalized = release_date.strip()
    try:
        date.fromisoformat(normalized)
    except ValueError as error:
        raise ReleasePrepError("Release date must use YYYY-MM-DD format.") from error
    return normalized


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    return ""


def replace_project_version(pyproject_text: str, version: str) -> str:
    lines = pyproject_text.splitlines(keepends=True)
    in_project = False
    replaced = 0

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "[project]":
            in_project = True
            continue
        if in_project and stripped.startswith("[") and stripped.endswith("]"):
            break
        if in_project and re.match(r"^\s*version\s*=", line):
            lines[index] = f'version = "{version}"{_line_ending(line)}'
            replaced += 1

    if replaced != 1:
        raise ReleasePrepError(
            f"Expected exactly one [project] version in pyproject.toml, found {replaced}."
        )
    return "".join(lines)


def replace_package_version(init_text: str, version: str) -> str:
    pattern = re.compile(r'^(__version__\s*=\s*)"[^"]+"', re.MULTILINE)
    updated, replaced = pattern.subn(rf'\1"{version}"', init_text)
    if replaced != 1:
        raise ReleasePrepError(
            f"Expected exactly one agentledger.__version__ assignment, found {replaced}."
        )
    return updated


def _section_version(title: str) -> str:
    return title.split(" - ", 1)[0].strip()


def prepare_changelog(changelog_text: str, package_version: str, release_date: str) -> str:
    release_version = changelog_version(package_version)
    heading = f"## {release_version} - {validate_release_date(release_date)}"
    lines = changelog_text.splitlines()

    unreleased_index: int | None = None
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if not match:
            continue
        title = match.group("title")
        version = _section_version(title)
        if version == release_version:
            raise ReleasePrepError(f"CHANGELOG.md already has a section for {release_version}.")
        if title.strip() == "Unreleased":
            unreleased_index = index

    if unreleased_index is None:
        raise ReleasePrepError("Could not find a ## Unreleased section in CHANGELOG.md.")

    next_heading = len(lines)
    for index in range(unreleased_index + 1, len(lines)):
        if HEADING_RE.match(lines[index]):
            next_heading = index
            break

    body = "\n".join(lines[unreleased_index + 1 : next_heading]).strip()
    if not body:
        raise ReleasePrepError("CHANGELOG.md Unreleased section is empty.")

    body_lines = body.splitlines()
    updated_lines = (
        lines[: unreleased_index + 1]
        + ["", heading, ""]
        + body_lines
        + [""]
        + lines[next_heading:]
    )
    return "\n".join(updated_lines).rstrip() + "\n"


def load_release_notes_module():
    spec = importlib.util.spec_from_file_location("agentledger_release_notes", RELEASE_NOTES_SCRIPT)
    if spec is None or spec.loader is None:
        raise ReleasePrepError(f"Could not load release notes script: {RELEASE_NOTES_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_release_notes_from_changelog(*, package_version: str, changelog_text: str) -> str:
    release_notes = load_release_notes_module()
    try:
        return release_notes.build_release_notes(
            version=package_version,
            changelog_text=changelog_text,
        )
    except release_notes.ReleaseNotesError as error:
        raise ReleasePrepError(str(error)) from error


def resolve_output_path(repo_root: Path, output: Path) -> Path:
    if output.is_absolute():
        return output
    return repo_root / output


def prepare_release(
    *,
    repo_root: Path,
    version: str,
    release_date: str,
    release_notes_output: Path | None = None,
    dry_run: bool = False,
) -> ReleasePrepResult:
    package_version = validate_package_version(version)
    normalized_date = validate_release_date(release_date)
    root = repo_root.resolve()

    files = {
        "pyproject.toml": root / "pyproject.toml",
        "src/agentledger/__init__.py": root / "src" / "agentledger" / "__init__.py",
        "CHANGELOG.md": root / "CHANGELOG.md",
    }
    missing = [name for name, path in files.items() if not path.exists()]
    if missing:
        raise ReleasePrepError(f"Missing required release file(s): {', '.join(missing)}.")

    updated = {
        "pyproject.toml": replace_project_version(
            files["pyproject.toml"].read_text(encoding="utf-8-sig"),
            package_version,
        ),
        "src/agentledger/__init__.py": replace_package_version(
            files["src/agentledger/__init__.py"].read_text(encoding="utf-8-sig"),
            package_version,
        ),
        "CHANGELOG.md": prepare_changelog(
            files["CHANGELOG.md"].read_text(encoding="utf-8-sig"),
            package_version,
            normalized_date,
        ),
    }

    changed_files = tuple(
        name
        for name, path in files.items()
        if path.read_text(encoding="utf-8-sig") != updated[name]
    )
    if not changed_files:
        raise ReleasePrepError("Release prep would not change any files.")

    output_path: Path | None = None
    output_text: str | None = None
    if release_notes_output is not None:
        output_path = resolve_output_path(root, release_notes_output)
        output_text = build_release_notes_from_changelog(
            package_version=package_version,
            changelog_text=updated["CHANGELOG.md"],
        )

    if not dry_run:
        for name in changed_files:
            files[name].write_text(updated[name], encoding="utf-8")
        if output_path is not None and output_text is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output_text, encoding="utf-8")

    return ReleasePrepResult(
        package_version=package_version,
        release_version=changelog_version(package_version),
        release_date=normalized_date,
        changed_files=changed_files,
        release_notes_output=str(output_path) if output_path else None,
        dry_run=dry_run,
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare AgentLedger version files and changelog for a release."
    )
    parser.add_argument(
        "--version",
        required=True,
        help="PEP 440 package version to write, for example 0.1.8a0.",
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Release date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Repository root. Defaults to this script's parent repository.",
    )
    parser.add_argument(
        "--release-notes-output",
        type=Path,
        help="Optional path for draft GitHub release notes generated from the prepared changelog.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report planned changes without writing files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = prepare_release(
            repo_root=args.repo_root,
            version=args.version,
            release_date=args.date,
            release_notes_output=args.release_notes_output,
            dry_run=args.dry_run,
        )
    except (OSError, ReleasePrepError) as error:
        print(f"prepare_release.py: {error}", file=sys.stderr)
        return 2

    print(f"Release prep: {result.package_version} -> {result.release_version}")
    print(f"Date: {result.release_date}")
    if result.dry_run:
        print("Dry run: no files written.")
    print("Changed files:")
    for path in result.changed_files:
        print(f"- {path}")
    if result.release_notes_output:
        label = "Planned release notes" if result.dry_run else "Release notes"
        print(f"{label}: {result.release_notes_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
