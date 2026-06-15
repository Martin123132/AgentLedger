from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import release_notes


SCHEMA_VERSION = "agentledger.release_command_index.v1"
DEFAULT_REPOSITORY = "Martin123132/AgentLedger"


class ReleaseCommandIndexError(ValueError):
    pass


def validate_release_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ReleaseCommandIndexError("release date must be YYYY-MM-DD.") from error


def _temp_path(name: str) -> str:
    return f"$env:TEMP\\{name}"


def artifact_paths(release_label: str) -> dict[str, str]:
    return {
        "release_rehearsal_dir": _temp_path(f"agentledger-release-rehearsal-{release_label}"),
        "draft_release_notes": _temp_path(f"agentledger-{release_label}-release.md"),
        "release_check_json": _temp_path("agentledger-release-check.json"),
        "release_check_summary": _temp_path("agentledger-release-check-summary.md"),
        "github_release_check_json": _temp_path("agentledger-github-release-check.json"),
        "github_release_check_markdown": _temp_path("agentledger-github-release-check.md"),
        "release_evidence_json": _temp_path("agentledger-release-evidence.json"),
        "release_evidence_markdown": _temp_path("agentledger-release-evidence.md"),
        "post_release_dir": _temp_path(f"agentledger-post-release-{release_label}"),
    }


def _section(name: str, purpose: str, commands: list[str], notes: list[str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "purpose": purpose,
        "commands": commands,
        "notes": notes or [],
    }


def build_release_command_index(
    *,
    version: str,
    release_date: str,
    repository: str = DEFAULT_REPOSITORY,
) -> dict[str, Any]:
    package_version = version.strip()
    if not package_version:
        raise ReleaseCommandIndexError("version must not be empty.")
    release_label = release_notes.normalize_version(package_version)
    release_date = validate_release_date(release_date)
    tag = f"v{release_label}"
    artifacts = artifact_paths(release_label)
    actions_base = f"https://github.com/{repository}/actions/runs"

    sections = [
        _section(
            "1. Start clean",
            "Synchronize master and confirm the local checkout is healthy before release prep.",
            [
                "git switch master",
                "git pull --ff-only origin master",
                "git status --short --branch",
                'python -m pip install -e ".[dev]"',
                "python -m pytest",
            ],
        ),
        _section(
            "2. Rehearse and prepare source files",
            "Dry-run the release, then write the version/changelog changes and draft release notes.",
            [
                (
                    f"python scripts/rehearse_release.py --version {package_version} "
                    f"--date {release_date} --output-dir {artifacts['release_rehearsal_dir']}"
                ),
                (
                    f"python scripts/prepare_release.py --version {package_version} "
                    f"--date {release_date} --release-notes-output {artifacts['draft_release_notes']} --dry-run"
                ),
                (
                    f"python scripts/prepare_release.py --version {package_version} "
                    f"--date {release_date} --release-notes-output {artifacts['draft_release_notes']}"
                ),
            ],
            [
                "Keep generated release notes and rehearsal output outside the repo.",
            ],
        ),
        _section(
            "3. Validate the release branch",
            "Run local metadata, tests, release readiness, and artifact preflight before opening the PR.",
            [
                "python scripts/check_release_metadata.py",
                f"python scripts/release_notes.py --version {package_version} --check",
                "python -m pytest",
                (
                    "powershell -NoProfile -ExecutionPolicy Bypass -File "
                    f"scripts/release-check.ps1 -RequireCleanGit -JsonOutput {artifacts['release_check_json']}"
                ),
                (
                    f"python scripts/release_check_summary.py {artifacts['release_check_json']} "
                    f"--output {artifacts['release_check_summary']}"
                ),
                (
                    f"python scripts/release_artifact_doctor.py --version {package_version} "
                    f"--stage final-notes --release-check-json {artifacts['release_check_json']} "
                    f"--release-check-summary {artifacts['release_check_summary']}"
                ),
            ],
        ),
        _section(
            "4. Open and merge the release PR",
            "Open a PR, wait for CI, and merge only after checks pass.",
            [
                "git status --short --branch --untracked-files=all",
                "git diff --stat",
                "gh pr create --draft --fill",
                "gh pr checks <pr-number> --watch --interval 10",
                "gh pr ready <pr-number>",
                "gh pr merge <pr-number> --merge --delete-branch",
                "git switch master",
                "git pull --ff-only origin master",
            ],
            [
                "Do not merge if `.agentledger/`, zip bundles, signing keys, or temp release artifacts appear in the PR diff.",
            ],
        ),
        _section(
            "5. Run release readiness and tag",
            "Run the manual readiness workflow on master, then push the release tag.",
            [
                (
                    f'gh workflow run "Release Readiness" --repo {repository} --ref master '
                    "-f require_clean_git=true -f skip_editable_install=false"
                ),
                f'gh run list --repo {repository} --workflow "Release Readiness" --limit 1',
                f"gh run watch <run-id> --repo {repository} --interval 10 --exit-status",
                f"git tag {tag}",
                f"git push origin {tag}",
                f"gh run list --repo {repository} --limit 5",
                f"gh run watch <tag-run-id> --repo {repository} --interval 10 --exit-status",
            ],
        ),
        _section(
            "6. Finalize and publish release notes",
            "Build publish-ready release notes from checked evidence and create the GitHub prerelease.",
            [
                (
                    f"python scripts/release_artifact_doctor.py --version {package_version} "
                    f"--stage final-notes --release-check-json {artifacts['release_check_json']} "
                    f"--release-check-summary {artifacts['release_check_summary']}"
                ),
                (
                    f"python scripts/finalize_release_notes.py --version {package_version} "
                    f"--release-check-json {artifacts['release_check_json']} "
                    f"--release-check-summary {artifacts['release_check_summary']} "
                    f"--pr-ci-url {actions_base}/<pr-run> "
                    f"--master-ci-url {actions_base}/<master-run> "
                    f"--release-readiness-url {actions_base}/<release-readiness-run> "
                    f"--tag-ci-url {actions_base}/<tag-run> "
                    f"--merge-sha <merge-sha> --output {artifacts['draft_release_notes']}"
                ),
                (
                    f"python scripts/release_notes.py --version {package_version} "
                    f"--notes-file {artifacts['draft_release_notes']} --check-publish-ready"
                ),
                (
                    f"gh release create {tag} --repo {repository} --title {tag} "
                    f"--notes-file {artifacts['draft_release_notes']} --prerelease"
                ),
            ],
            [
                "Replace every placeholder run id and merge SHA before publishing.",
            ],
        ),
        _section(
            "7. Post-release checks and handoff",
            "Verify the published release and write public-safe handoff summaries.",
            [
                f"gh release view {tag} --repo {repository}",
                (
                    f"python scripts/release_artifact_doctor.py --version {package_version} "
                    f"--stage post-release --release-check-json {artifacts['release_check_json']} "
                    f"--release-check-summary {artifacts['release_check_summary']} "
                    f"--release-notes {artifacts['draft_release_notes']}"
                ),
                (
                    f"python scripts/post_release_check.py --version {package_version} "
                    f"--release-check-json {artifacts['release_check_json']} "
                    f"--release-check-summary {artifacts['release_check_summary']} "
                    f"--release-notes {artifacts['draft_release_notes']} "
                    f"--output-dir {artifacts['post_release_dir']}"
                ),
                f"python scripts/release_notes.py --version {package_version} --check",
            ],
        ),
        _section(
            "Optional: lower-level evidence packet debug",
            "Use this when validating saved GitHub release-check JSON by hand.",
            [
                (
                    f"python scripts/check_github_release.py --version {package_version} "
                    f"--format json --output {artifacts['github_release_check_json']}"
                ),
                (
                    f"python scripts/check_github_release.py --version {package_version} "
                    f"--format markdown --output {artifacts['github_release_check_markdown']}"
                ),
                (
                    f"python scripts/release_artifact_doctor.py --version {package_version} "
                    f"--stage evidence-packet --release-check-json {artifacts['release_check_json']} "
                    f"--release-check-summary {artifacts['release_check_summary']} "
                    f"--release-notes {artifacts['draft_release_notes']} "
                    f"--github-release-check-json {artifacts['github_release_check_json']}"
                ),
                (
                    f"python scripts/release_evidence_packet.py --version {package_version} "
                    f"--release-check-json {artifacts['release_check_json']} "
                    f"--release-check-summary {artifacts['release_check_summary']} "
                    f"--release-notes {artifacts['draft_release_notes']} "
                    f"--github-release-check-json {artifacts['github_release_check_json']} "
                    f"--output {artifacts['release_evidence_markdown']} "
                    f"--json-output {artifacts['release_evidence_json']}"
                ),
            ],
        ),
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "version": package_version,
        "release_label": release_label,
        "tag": tag,
        "release_date": release_date,
        "repository": repository,
        "artifacts": artifacts,
        "placeholders": [
            "<pr-number>",
            "<run-id>",
            "<tag-run-id>",
            "<pr-run>",
            "<master-run>",
            "<release-readiness-run>",
            "<tag-run>",
            "<merge-sha>",
        ],
        "do_not_commit": [
            ".agentledger/",
            "*.zip",
            ".agentledger-signing-key",
            "signing keys",
            "temp release artifacts",
        ],
        "sections": sections,
    }


def format_text(index: dict[str, Any]) -> str:
    lines = [
        f"AgentLedger release command index: {index['version']} -> {index['tag']}",
        f"Schema: {index['schema_version']}",
        f"Release date: {index['release_date']}",
        f"Repository: {index['repository']}",
        "",
        "Artifacts:",
    ]
    for name, value in index["artifacts"].items():
        lines.append(f"- {name}: {value}")
    for section in index["sections"]:
        lines.extend(["", section["name"], section["purpose"]])
        for command in section["commands"]:
            lines.append(f"  {command}")
        for note in section["notes"]:
            lines.append(f"  Note: {note}")
    lines.extend(["", "Do not commit: " + ", ".join(index["do_not_commit"])])
    return "\n".join(lines).rstrip() + "\n"


def format_markdown(index: dict[str, Any]) -> str:
    lines = [
        "# AgentLedger Release Command Index",
        "",
        f"- Schema: `{index['schema_version']}`",
        f"- Version: {index['version']}",
        f"- Release label: {index['release_label']}",
        f"- Tag: {index['tag']}",
        f"- Release date: {index['release_date']}",
        f"- Repository: {index['repository']}",
        "",
        "## Artifacts",
        "",
    ]
    for name, value in index["artifacts"].items():
        lines.append(f"- `{name}`: `{value}`")
    for section in index["sections"]:
        lines.extend(["", f"## {section['name']}", "", section["purpose"], "", "```powershell"])
        lines.extend(section["commands"])
        lines.append("```")
        if section["notes"]:
            lines.append("")
            for note in section["notes"]:
                lines.append(f"- {note}")
    lines.extend(["", "## Handling Notes", ""])
    for item in index["do_not_commit"]:
        lines.append(f"- Do not commit `{item}`.")
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print the ordered AgentLedger release-day command index."
    )
    parser.add_argument("--version", required=True, help="Package version, for example 0.1.8a0.")
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Release date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPOSITORY,
        help=f"GitHub repository. Defaults to {DEFAULT_REPOSITORY}.",
    )
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--output", type=Path, help="Write formatted command index to this path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        index = build_release_command_index(
            version=args.version,
            release_date=args.date,
            repository=args.repo,
        )
    except (ReleaseCommandIndexError, release_notes.ReleaseNotesError) as error:
        print(f"release_command_index.py: {error}", file=sys.stderr)
        return 2

    if args.format == "json":
        rendered = json.dumps(index, indent=2) + "\n"
    elif args.format == "markdown":
        rendered = format_markdown(index)
    else:
        rendered = format_text(index)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Release command index written: {args.output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
