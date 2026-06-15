from __future__ import annotations

import importlib.util
from pathlib import Path
import re
import sys
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "release-process.md"
PREPARE_RELEASE_SCRIPT = ROOT / "scripts" / "prepare_release.py"
RELEASE_NOTES_SCRIPT = ROOT / "scripts" / "release_notes.py"

PACKAGE_VERSION_RE = re.compile(r"\b\d+\.\d+\.\d+a\d+\b")
RELEASE_LABEL_RE = re.compile(r"\bv?(\d+\.\d+\.\d+-alpha(?:\.\d+)?)\b")
TEMP_RELEASE_NOTES_RE = re.compile(
    r"agentledger-(\d+\.\d+\.\d+-alpha(?:\.\d+)?)-release\.md"
)


def load_script(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prepare_release = load_script("prepare_release_for_docs", PREPARE_RELEASE_SCRIPT)
release_notes = load_script("release_notes_for_docs", RELEASE_NOTES_SCRIPT)


def test_release_process_example_versions_match_release_tooling() -> None:
    text = DOC.read_text(encoding="utf-8")
    package_versions = set(PACKAGE_VERSION_RE.findall(text))
    assert package_versions, "Release process should document at least one package version example."

    expected_labels = {prepare_release.changelog_version(version) for version in package_versions}
    release_notes_labels = {release_notes.normalize_version(version) for version in package_versions}
    documented_labels = {match.group(1) for match in RELEASE_LABEL_RE.finditer(text)}
    temp_file_labels = set(TEMP_RELEASE_NOTES_RE.findall(text))

    assert release_notes_labels == expected_labels
    assert documented_labels == expected_labels
    assert temp_file_labels == expected_labels
    for label in expected_labels:
        assert f"v{label}" in text


def test_release_process_documents_required_release_gates() -> None:
    text = DOC.read_text(encoding="utf-8")
    required_fragments = [
        "git switch master",
        "git pull --ff-only origin master",
        "git status --short --branch",
        'python -m pip install -e ".[dev]"',
        "python scripts/rehearse_release.py --version",
        "agentledger-release-rehearsal",
        "python scripts/prepare_release.py --version",
        "--release-notes-output",
        "--dry-run",
        "python scripts/check_release_metadata.py",
        "python scripts/release_notes.py --version",
        "--notes-file",
        "--check-publish-ready",
        "python -m pytest",
        (
            "powershell -NoProfile -ExecutionPolicy Bypass -File "
            "scripts/release-check.ps1 -RequireCleanGit"
        ),
        "-JsonOutput",
        "agentledger-release-check.json",
        "agentledger.release_check.v1",
        "python scripts/release_check_summary.py",
        "agentledger-release-check-summary.md",
        "python scripts/finalize_release_notes.py",
        "--release-check-json",
        "--release-check-summary",
        "--pr-ci-url",
        "--master-ci-url",
        "--release-readiness-url",
        "--tag-ci-url",
        "--merge-sha",
        'gh workflow run "Release Readiness"',
        "gh run watch <run-id>",
        "git tag v",
        "git push origin v",
        "gh release view v",
        "python scripts/check_github_release.py",
        "agentledger-github-release-check.json",
        "agentledger-github-release-check.md",
        "agentledger.github_release_check.v1",
        "python scripts/release_evidence_packet.py",
        "agentledger-release-evidence.md",
        "agentledger-release-evidence.json",
        "agentledger.release_evidence_packet.v1",
        ".agentledger/",
        "*.zip",
        "signing keys",
    ]

    missing = [fragment for fragment in required_fragments if fragment not in text]
    assert not missing, "Release process is missing required gate(s):\n" + "\n".join(missing)
