from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "agentledger.release_metadata_check.v1"

EXPECTED_NAME = "agentledger"
EXPECTED_DESCRIPTION = "Local-first black box recorder for AI coding agents."
EXPECTED_REQUIRES_PYTHON = ">=3.10"
EXPECTED_LICENSE = "PolyForm Noncommercial License 1.0.0"
EXPECTED_AUTHOR = "Martin Ollett"
EXPECTED_RUNTIME_DEPENDENCIES = "[]"

PACKAGE_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:a\d+)?$")
PEP440_ALPHA_RE = re.compile(r"^(?P<base>\d+\.\d+\.\d+)a(?P<number>\d+)$")
PROJECT_ASSIGNMENT_RE = re.compile(r"^(?P<key>[A-Za-z0-9_-]+)\s*=\s*(?P<value>.+?)\s*$")
PACKAGE_VERSION_ASSIGNMENT_RE = re.compile(r'^__version__\s*=\s*"(?P<version>[^"]+)"', re.MULTILINE)


def _parse_quoted_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if len(stripped) < 2 or stripped[0] != '"' or stripped[-1] != '"':
        return None
    return stripped[1:-1]


def _parse_inline_text_table(value: str | None, key: str) -> str | None:
    if value is None:
        return None
    match = re.search(rf'\b{re.escape(key)}\s*=\s*"([^"]+)"', value)
    if not match:
        return None
    return match.group(1)


def _parse_author_names(value: str | None) -> list[str]:
    if value is None:
        return []
    return re.findall(r'\bname\s*=\s*"([^"]+)"', value)


def parse_project_table(pyproject_text: str) -> dict[str, str]:
    project: dict[str, str] = {}
    in_project = False
    for raw_line in pyproject_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[project]":
            in_project = True
            continue
        if in_project and line.startswith("[") and line.endswith("]"):
            break
        if not in_project:
            continue
        match = PROJECT_ASSIGNMENT_RE.match(line)
        if match:
            project[match.group("key")] = match.group("value")
    return project


def package_version_from_init(init_text: str) -> str | None:
    match = PACKAGE_VERSION_ASSIGNMENT_RE.search(init_text)
    if not match:
        return None
    return match.group("version")


def changelog_version(package_version: str | None) -> str | None:
    if not package_version:
        return None
    normalized = package_version.strip()
    if not PACKAGE_VERSION_RE.match(normalized):
        return None
    match = PEP440_ALPHA_RE.match(normalized)
    if not match:
        return normalized
    alpha_number = int(match.group("number"))
    if alpha_number == 0:
        return f"{match.group('base')}-alpha"
    return f"{match.group('base')}-alpha.{alpha_number}"


def _add_check(checks: list[dict[str, str]], name: str, ok: bool, detail: str) -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if ok else "failed",
            "detail": detail,
        }
    )


def _has_changelog_section(changelog_text: str, label: str) -> bool:
    heading_re = re.compile(rf"^##\s+{re.escape(label)}(?:\s+-\s+.+)?\s*$", re.MULTILINE)
    return bool(heading_re.search(changelog_text))


def check_release_metadata(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    files = {
        "pyproject.toml": root / "pyproject.toml",
        "src/agentledger/__init__.py": root / "src" / "agentledger" / "__init__.py",
        "README.md": root / "README.md",
        "LICENSE": root / "LICENSE",
        "COMMERCIAL.md": root / "COMMERCIAL.md",
        "CHANGELOG.md": root / "CHANGELOG.md",
    }

    checks: list[dict[str, str]] = []
    texts: dict[str, str] = {}
    for name, path in files.items():
        exists = path.exists()
        _add_check(
            checks,
            f"required file: {name}",
            exists,
            f"{name} exists" if exists else f"{name} is missing",
        )
        if exists:
            texts[name] = path.read_text(encoding="utf-8-sig")

    project = parse_project_table(texts.get("pyproject.toml", ""))
    project_name = _parse_quoted_string(project.get("name"))
    project_version = _parse_quoted_string(project.get("version"))
    package_version = package_version_from_init(texts.get("src/agentledger/__init__.py", ""))
    release_label = changelog_version(project_version)
    license_text = _parse_inline_text_table(project.get("license"), "text")
    authors = _parse_author_names(project.get("authors"))

    _add_check(
        checks,
        "project name",
        project_name == EXPECTED_NAME,
        f"project name is {project_name!r}; expected {EXPECTED_NAME!r}",
    )
    _add_check(
        checks,
        "project version format",
        bool(project_version and PACKAGE_VERSION_RE.match(project_version)),
        f"project version is {project_version!r}; expected a PEP 440 alpha/final version",
    )
    _add_check(
        checks,
        "package version",
        project_version is not None and package_version == project_version,
        f"agentledger.__version__ is {package_version!r}; pyproject version is {project_version!r}",
    )
    _add_check(
        checks,
        "project description",
        _parse_quoted_string(project.get("description")) == EXPECTED_DESCRIPTION,
        f"project description should be {EXPECTED_DESCRIPTION!r}",
    )
    _add_check(
        checks,
        "python requirement",
        _parse_quoted_string(project.get("requires-python")) == EXPECTED_REQUIRES_PYTHON,
        f"requires-python should be {EXPECTED_REQUIRES_PYTHON!r}",
    )
    _add_check(
        checks,
        "license metadata",
        license_text == EXPECTED_LICENSE,
        f"project license is {license_text!r}; expected {EXPECTED_LICENSE!r}",
    )
    _add_check(
        checks,
        "author metadata",
        EXPECTED_AUTHOR in authors,
        f"project authors are {authors!r}; expected {EXPECTED_AUTHOR!r}",
    )
    _add_check(
        checks,
        "runtime dependencies",
        project.get("dependencies", "").strip() == EXPECTED_RUNTIME_DEPENDENCIES,
        "runtime dependencies should remain empty for the current stdlib-only alpha package",
    )

    readme = texts.get("README.md", "")
    license_file = texts.get("LICENSE", "")
    commercial = texts.get("COMMERCIAL.md", "")
    changelog = texts.get("CHANGELOG.md", "")
    _add_check(
        checks,
        "readme license notice",
        EXPECTED_LICENSE in readme and "Commercial use requires separate permission." in readme,
        "README should state the noncommercial license and commercial-use requirement",
    )
    _add_check(
        checks,
        "license file",
        f"# {EXPECTED_LICENSE}" in license_file,
        f"LICENSE should contain # {EXPECTED_LICENSE}",
    )
    _add_check(
        checks,
        "commercial terms",
        "Commercial use is not granted by the public license." in commercial,
        "COMMERCIAL.md should explain that commercial use needs separate permission",
    )
    _add_check(
        checks,
        "unreleased changelog",
        "## Unreleased" in changelog,
        "CHANGELOG.md should keep a ## Unreleased section for new work",
    )
    _add_check(
        checks,
        "current release changelog",
        bool(release_label and _has_changelog_section(changelog, release_label)),
        f"CHANGELOG.md should contain a section for current release label {release_label!r}",
    )

    failed = [check for check in checks if check["status"] == "failed"]
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not failed,
        "status": "ready" if not failed else "failed",
        "repo": str(root),
        "project_name": project_name,
        "project_version": project_version,
        "package_version": package_version,
        "release_label": release_label,
        "license": license_text,
        "checks": checks,
        "errors": [f"{check['name']}: {check['detail']}" for check in failed],
    }


def format_text(result: dict[str, Any]) -> str:
    status = "OK" if result["ok"] else "FAILED"
    lines = [
        (
            f"Release metadata {status}: {result.get('project_name') or 'unknown'} "
            f"{result.get('project_version') or 'unknown'}"
        )
    ]
    if result.get("release_label"):
        lines.append(f"Release label: {result['release_label']}")
    for check in result["checks"]:
        prefix = "OK" if check["status"] == "passed" else "FAIL"
        lines.append(f"- {prefix}: {check['name']} - {check['detail']}")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check AgentLedger release metadata, license notices, and version alignment."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Repository root. Defaults to this script's parent repository.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = check_release_metadata(args.repo_root)
    except OSError as error:
        result = {
            "schema_version": SCHEMA_VERSION,
            "ok": False,
            "status": "failed",
            "repo": str(args.repo_root.resolve()),
            "project_name": None,
            "project_version": None,
            "package_version": None,
            "release_label": None,
            "license": None,
            "checks": [],
            "errors": [str(error)],
        }

    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        print(format_text(result))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
