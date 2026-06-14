from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote


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
