from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

import pytest

from agentledger import cli


ROOT = Path(__file__).resolve().parents[1]

MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
CODE_SPAN_RE = re.compile(r"`([^`\n]+)`")

EXTERNAL_TARGET_PREFIXES = (
    "http://",
    "https://",
    "mailto:",
    "#",
)

REPO_FILE_PREFIXES = (
    ".github/",
    "docs/",
    "scripts/",
    "src/",
    "tests/",
)

REPO_FILE_NAMES = {
    ".agentledger.toml",
    ".gitignore",
    "ALPHA.md",
    "CHANGELOG.md",
    "COMMERCIAL.md",
    "LICENSE",
    "README.md",
    "ROADMAP.md",
    "SECURITY.md",
    "pyproject.toml",
}

REPO_FILE_SUFFIXES = (
    ".md",
    ".toml",
    ".yml",
    ".yaml",
    ".ps1",
    ".sh",
    ".py",
)

ALPHA_DOCS = [
    ROOT / "README.md",
    ROOT / "ALPHA.md",
    ROOT / "docs" / "alpha-checklist.md",
    ROOT / "docs" / "alpha-tester-guide.md",
]


def _help_output(capsys: pytest.CaptureFixture[str], *args: str) -> str:
    with pytest.raises(SystemExit) as exc:
        cli.main([*args, "--help"])
    assert exc.value.code == 0
    return capsys.readouterr().out


def _markdown_files() -> list[Path]:
    return sorted([*ROOT.glob("*.md"), *ROOT.joinpath("docs").glob("*.md")])


def _link_target_path(markdown_file: Path, raw_target: str) -> Path | None:
    target = raw_target.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = unquote(target)
    if target.startswith(EXTERNAL_TARGET_PREFIXES):
        return None

    path_part = target.split("#", 1)[0].replace("\\", "/")
    if not path_part:
        return None
    if "://" in path_part:
        return None
    return (markdown_file.parent / path_part).resolve()


def _looks_like_repo_file_reference(value: str) -> bool:
    target = value.strip().replace("\\", "/")
    if not target or any(character.isspace() for character in target):
        return False
    if target.startswith((".", "<")) and target not in REPO_FILE_NAMES:
        return target.startswith((".github/", ".agentledger.toml", ".gitignore"))
    if target in REPO_FILE_NAMES:
        return True
    return target.startswith(REPO_FILE_PREFIXES) and target.endswith(REPO_FILE_SUFFIXES)


def _config_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def test_markdown_links_point_to_existing_local_targets() -> None:
    missing = []
    for markdown_file in _markdown_files():
        text = markdown_file.read_text(encoding="utf-8")
        for match in MARKDOWN_LINK_RE.finditer(text):
            target_path = _link_target_path(markdown_file, match.group(1))
            if target_path is not None and not target_path.exists():
                missing.append(f"{markdown_file.relative_to(ROOT)} -> {match.group(1)}")

    assert not missing, "Missing Markdown link targets:\n" + "\n".join(missing)


def test_code_spanned_repo_file_references_exist() -> None:
    missing = []
    for markdown_file in _markdown_files():
        text = markdown_file.read_text(encoding="utf-8")
        for match in CODE_SPAN_RE.finditer(text):
            target = match.group(1)
            if not _looks_like_repo_file_reference(target):
                continue
            target_path = (ROOT / target.replace("\\", "/")).resolve()
            if not target_path.exists():
                missing.append(f"{markdown_file.relative_to(ROOT)} -> `{target}`")

    assert not missing, "Missing documented repo file references:\n" + "\n".join(missing)


def test_readme_public_alpha_config_matches_repository_config() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    config = (ROOT / ".agentledger.toml").read_text(encoding="utf-8")
    match = re.search(
        r"This repository includes a public-alpha example at `\.agentledger\.toml`:\n\n```toml\n(?P<config>.*?)\n```",
        readme,
        re.DOTALL,
    )

    assert match is not None, "README is missing the public-alpha .agentledger.toml example block"
    assert _config_lines(match.group("config")) == _config_lines(config)


def test_alpha_docs_prefer_cross_platform_cli_and_keep_windows_extended_path() -> None:
    preferred_command = "python -m agentledger alpha --repo . --out .agentledger"

    for path in ALPHA_DOCS:
        text = path.read_text(encoding="utf-8")
        assert preferred_command in text, f"{path.relative_to(ROOT)} should document the preferred alpha CLI command"
        assert "scripts/alpha.ps1" in text, f"{path.relative_to(ROOT)} should keep the Windows extended alpha path"

    notes = (ROOT / "docs" / "alpha-notes.md").read_text(encoding="utf-8")
    assert "public quick-start flow now points at `agentledger alpha`" in notes


def test_alpha_help_and_docs_cover_public_alpha_options(capsys: pytest.CaptureFixture[str]) -> None:
    alpha_help = _help_output(capsys, "alpha")
    alpha_summary_help = _help_output(capsys, "alpha-summary")
    alpha_handoff_help = _help_output(capsys, "alpha-handoff")
    normalized_alpha_help = " ".join(alpha_help.split())
    normalized_alpha_summary_help = " ".join(alpha_summary_help.split())
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "alpha-checklist.md").read_text(encoding="utf-8")
    tester_guide = (ROOT / "docs" / "alpha-tester-guide.md").read_text(encoding="utf-8")
    contracts = (ROOT / "docs" / "json-contracts.md").read_text(encoding="utf-8")
    docs_text = "\n".join([readme, checklist, tester_guide, contracts])

    for option in ["--json-output", "--privacy-mode", "--strict", "--format"]:
        assert option in alpha_help

    assert "current Python -m pytest" in normalized_alpha_help
    assert "--out OUT" in alpha_summary_help
    assert "Defaults to <out>/alpha" in normalized_alpha_summary_help
    assert "summary.json" in normalized_alpha_summary_help
    assert "--output-dir OUTPUT_DIR" in alpha_handoff_help
    assert "--strict" in alpha_handoff_help

    for documented in [
        "--json-output <path>",
        "--strict",
        "alpha --format json",
        "alpha-summary --out .agentledger",
        "alpha-handoff --out .agentledger",
        "agentledger.alpha_handoff.v1",
    ]:
        assert documented in docs_text
