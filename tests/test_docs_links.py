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
    "COMMERCIAL-LICENSE.md",
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

SUPPORT_PACKET_MARKDOWN_EXAMPLE = ROOT / "docs" / "support-packet-markdown-example.md"
SUPPORT_PACKET_MARKDOWN_QA = ROOT / "docs" / "support-packet-markdown-qa.md"
ALPHA_FEEDBACK_ISSUE_TEMPLATE = ROOT / ".github" / "ISSUE_TEMPLATE" / "alpha-feedback.md"
ALPHA_FEEDBACK_READINESS = ROOT / "docs" / "alpha-feedback-readiness.md"
PUBLIC_ALPHA_TRIAL = ROOT / "docs" / "public-alpha-trial.md"
ALPHA_INSTALL_CONFIDENCE = ROOT / "docs" / "alpha-install-confidence.md"
PUBLIC_DEMO_SCRIPT = ROOT / "docs" / "public-demo-script.md"


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


def test_public_docs_do_not_suggest_c_drive_storage() -> None:
    paths = sorted(
        [
            ROOT / "README.md",
            *ROOT.joinpath("docs").glob("*.md"),
            *ROOT.joinpath(".github", "ISSUE_TEMPLATE").glob("*.md"),
        ]
    )
    forbidden = ("C:\\", "C:/", "C:\\Users", "OneDrive")
    offenders = []

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.relative_to(ROOT)} contains {token!r}")

    assert not offenders, "Public docs should avoid C-drive storage examples:\n" + "\n".join(offenders)


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


def test_first_run_doc_is_linked_from_readme() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    first_run = (ROOT / "docs" / "first-run.md").read_text(encoding="utf-8")

    assert "[docs/first-run.md](docs/first-run.md)" in readme
    assert "[docs/install.md](docs/install.md)" in readme
    assert "[docs/alpha-troubleshooting.md](docs/alpha-troubleshooting.md)" in readme
    assert 'python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.25-alpha"' in readme
    assert "python -m agentledger try" in first_run
    assert "python -m agentledger demo" in first_run
    assert "python -m agentledger alpha-guide --repo . --out .agentledger" in first_run
    assert "docs/install.md" in first_run
    assert "docs/alpha-troubleshooting.md" in first_run
    assert "`Read first:` block" in readme
    assert "`Read first:` block" in first_run
    assert "Do not commit or upload:" in first_run


def test_install_doc_covers_public_tag_and_source_check() -> None:
    install_doc = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")

    assert 'python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.25-alpha"' in install_doc
    assert 'python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@master"' in install_doc
    assert 'python -m pip install -e ".[dev]"' in install_doc
    assert "scripts/install-source-check.ps1" in install_doc
    assert "docs/alpha-install-confidence.md" in install_doc
    assert "python -m pip uninstall agentledger" in install_doc
    assert "Do not commit or upload `.agentledger/`" in install_doc


def test_alpha_install_confidence_doc_is_checked() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install_doc = (ROOT / "docs" / "install.md").read_text(encoding="utf-8")
    first_run = (ROOT / "docs" / "first-run.md").read_text(encoding="utf-8")
    trial = PUBLIC_ALPHA_TRIAL.read_text(encoding="utf-8")
    confidence = ALPHA_INSTALL_CONFIDENCE.read_text(encoding="utf-8")

    assert "[docs/alpha-install-confidence.md](docs/alpha-install-confidence.md)" in readme
    assert "docs/alpha-install-confidence.md" in install_doc
    assert "docs/alpha-install-confidence.md" in first_run
    assert "docs/alpha-install-confidence.md" in trial
    assert "`v0.1.25-alpha` is the current checked public alpha tag." in confidence
    assert "agentledger 0.1.25a0" in confidence
    assert "public install-from-tag smoke check" in confidence

    for command in [
        'python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.25-alpha"',
        "python -m agentledger --version",
        "python -m agentledger try",
        "python -m agentledger alpha-guide --repo . --out .agentledger",
        "python -m agentledger alpha --repo . --out .agentledger",
        "python -m agentledger status --out .agentledger --allow-warnings",
        "python -m agentledger support-packet --format markdown",
    ]:
        assert command in confidence

    for marker in [
        "Open the printed Markdown report first",
        "printed `status` command",
        "sanitized issue/comment body",
        ".agentledger/` evidence folders",
        "zip evidence bundles",
        "command transcripts",
        "signing keys",
        "temporary workspaces",
        "private repo paths",
        "private URLs",
        "credentials, tokens, or secrets",
        "customer data",
    ]:
        assert marker in confidence


def test_public_demo_script_doc_is_checked() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    confidence = ALPHA_INSTALL_CONFIDENCE.read_text(encoding="utf-8")
    demo_script = PUBLIC_DEMO_SCRIPT.read_text(encoding="utf-8")

    assert "[docs/public-demo-script.md](docs/public-demo-script.md)" in readme
    assert "docs/public-demo-script.md" in confidence
    assert "Three Command Demo" in demo_script
    assert "Share This" in demo_script
    assert "Keep Private" in demo_script

    for command in [
        'python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.25-alpha"',
        "python -m agentledger try",
        "python -m agentledger support-packet --format markdown",
        "python -m agentledger alpha-guide --repo . --out .agentledger",
        "python -m agentledger alpha --repo . --out .agentledger",
        "python -m agentledger status --out .agentledger --allow-warnings",
    ]:
        assert command in demo_script

    for marker in [
        "local-first black box recorder for AI coding agents",
        "Raw evidence stays local by default.",
        "support-packet Markdown headings",
        "whether local paths and raw evidence stayed private",
        "Share only reviewed snippets",
        ".agentledger/` evidence folders",
        "zip evidence bundles",
        "command transcripts",
        "signing keys",
        "temporary workspaces",
        "private repo paths",
        "private URLs",
        "credentials, tokens, or secrets",
        "customer data",
    ]:
        assert marker in demo_script


def test_public_alpha_trial_doc_is_checked() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    trial = PUBLIC_ALPHA_TRIAL.read_text(encoding="utf-8")
    compact_trial = " ".join(trial.split())
    commercial = (ROOT / "COMMERCIAL.md").read_text(encoding="utf-8")
    commercial_license = (ROOT / "COMMERCIAL-LICENSE.md").read_text(encoding="utf-8")

    assert "[docs/public-alpha-trial.md](docs/public-alpha-trial.md)" in readme
    assert 'python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.25-alpha"' in trial
    assert "agentledger 0.1.25a0" in trial

    for command in [
        "python -m agentledger --version",
        "python -m agentledger try",
        "python -m agentledger support-packet --format markdown",
        "python -m agentledger alpha-guide --repo . --out .agentledger",
    ]:
        assert command in trial

    for marker in [
        "D:\\Projects\\your-repo",
        "raw `.agentledger/` evidence folders",
        "zip evidence bundles",
        "command transcripts",
        "signing keys",
        "temp workspaces",
        "private repo paths",
        "private URLs",
        "credentials, tokens, or secrets",
        "customer data",
    ]:
        assert marker in trial

    assert "The public license allows non-commercial use under `LICENSE`." in compact_trial
    assert (
        "Commercial use requires separate written permission; see `COMMERCIAL.md` and "
        "`COMMERCIAL-LICENSE.md`."
    ) in compact_trial
    assert "Commercial use is not granted by the public license." in commercial
    assert "TWO HANDS NETWORK LTD" in commercial_license


def test_license_contact_footer_is_present() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    contact_block = """
## Contact us

For collaboration, information on existing products, or other enquiries, please contact (via Email):

Glyn : glyn@twohandsnetwork.co.uk
""".strip()

    assert license_text.strip().endswith(contact_block)


def test_alpha_docs_prefer_cross_platform_cli_and_keep_windows_extended_path() -> None:
    preferred_command = "python -m agentledger alpha --repo . --out .agentledger"
    guide_command = "python -m agentledger alpha-guide --repo . --out .agentledger"

    for path in ALPHA_DOCS:
        text = path.read_text(encoding="utf-8")
        assert guide_command in text, f"{path.relative_to(ROOT)} should document the alpha guide command"
        assert preferred_command in text, f"{path.relative_to(ROOT)} should document the preferred alpha CLI command"
        assert "scripts/alpha.ps1" in text, f"{path.relative_to(ROOT)} should keep the Windows extended alpha path"

    notes = (ROOT / "docs" / "alpha-notes.md").read_text(encoding="utf-8")
    assert "public quick-start flow now points at `agentledger alpha`" in notes


def test_alpha_help_and_docs_cover_public_alpha_options(capsys: pytest.CaptureFixture[str]) -> None:
    alpha_guide_help = _help_output(capsys, "alpha-guide")
    alpha_help = _help_output(capsys, "alpha")
    alpha_summary_help = _help_output(capsys, "alpha-summary")
    alpha_handoff_help = _help_output(capsys, "alpha-handoff")
    pack_alpha_help = _help_output(capsys, "pack-alpha")
    open_packet_help = _help_output(capsys, "open-packet")
    support_packet_help = _help_output(capsys, "support-packet")
    normalized_alpha_help = " ".join(alpha_help.split())
    normalized_alpha_summary_help = " ".join(alpha_summary_help.split())
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    checklist = (ROOT / "docs" / "alpha-checklist.md").read_text(encoding="utf-8")
    tester_guide = (ROOT / "docs" / "alpha-tester-guide.md").read_text(encoding="utf-8")
    contracts = (ROOT / "docs" / "json-contracts.md").read_text(encoding="utf-8")
    troubleshooting = (ROOT / "docs" / "alpha-troubleshooting.md").read_text(encoding="utf-8")
    docs_text = "\n".join([readme, checklist, tester_guide, contracts, troubleshooting])

    for option in ["--json-output", "--privacy-mode", "--strict", "--format"]:
        assert option in alpha_help

    for option in ["--repo", "--out", "--format"]:
        assert option in alpha_guide_help

    assert "current Python -m pytest" in normalized_alpha_help
    assert "--out OUT" in alpha_summary_help
    assert "Defaults to <out>/alpha" in normalized_alpha_summary_help
    assert "summary.json" in normalized_alpha_summary_help
    assert "--output-dir OUTPUT_DIR" in alpha_handoff_help
    assert "--strict" in alpha_handoff_help
    assert "--share-safe" in alpha_handoff_help
    assert "--redact-local-paths" in alpha_handoff_help
    assert "--output-dir OUTPUT_DIR" in pack_alpha_help
    assert "--strict" in pack_alpha_help
    assert "--out OUT" in open_packet_help
    assert "--format" in open_packet_help
    assert "--out OUT" in support_packet_help
    assert "--format" in support_packet_help

    for documented in [
        "--json-output <path>",
        "--strict",
        "alpha-guide --out .agentledger",
        "alpha --format json",
        "alpha-summary --out .agentledger",
        "alpha-handoff --out .agentledger",
        "alpha-handoff --out .agentledger --output-dir $env:TEMP\\agentledger-alpha-handoff-safe --share-safe",
        "pack-alpha --out .agentledger",
        "open-packet --out .agentledger",
        "support-packet --format markdown",
        "support-packet --format json",
        "alpha-troubleshooting.md",
        "install, command, packet, and reporting checks",
        "--redact-local-paths",
        "agentledger.alpha_handoff.v1",
        "agentledger.pack_alpha.v1",
        "agentledger.open_packet.v1",
        "agentledger.support_packet.v1",
    ]:
        assert documented in docs_text


def test_support_packet_markdown_example_command_is_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    example = SUPPORT_PACKET_MARKDOWN_EXAMPLE.read_text(encoding="utf-8")
    match = re.search(
        r"```powershell\n(?P<command>python -m agentledger support-packet --format markdown --out <private-output-dir>)\n```",
        example,
    )
    assert match is not None, "support-packet Markdown example should document the checked command"

    private_out = tmp_path / "private-output" / "private-client-ledger"
    documented_command = match.group("command").replace("<private-output-dir>", str(private_out))
    assert documented_command.startswith("python -m agentledger support-packet --format markdown --out ")

    assert cli.main(["support-packet", "--format", "markdown", "--out", str(private_out)]) == 0
    output = capsys.readouterr().out

    expected_markers = [
        "## AgentLedger alpha support report",
        "### Summary",
        "- Raw evidence copied: no",
        "- Local paths included: no",
        "- Raw evidence kept private: yes",
        "### Useful commands",
        "python -m agentledger status --out <agentledger-output> --allow-warnings",
        "### Keep private by default",
        "private repo paths, private URLs, non-public source, credentials, tokens, and secrets",
    ]
    for marker in expected_markers:
        assert marker in example
        assert marker in output

    assert "<agentledger-output>" in output
    assert str(private_out) not in output
    assert private_out.name not in output


def test_support_packet_markdown_qa_note_is_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    qa_note = SUPPORT_PACKET_MARKDOWN_QA.read_text(encoding="utf-8")
    feedback_template = (ROOT / "docs" / "alpha-feedback-template.md").read_text(encoding="utf-8")
    example = SUPPORT_PACKET_MARKDOWN_EXAMPLE.read_text(encoding="utf-8")

    assert "docs/support-packet-markdown-qa.md" in feedback_template
    assert "[docs/support-packet-markdown-qa.md](support-packet-markdown-qa.md)" in example
    assert ".github/ISSUE_TEMPLATE/alpha-feedback.md" in qa_note
    assert "docs/alpha-feedback-template.md" in qa_note
    assert "sanitized demo inputs only" in qa_note
    assert "private output path appeared anywhere" in qa_note

    match = re.search(
        r"```powershell\n(?P<command>python -m agentledger support-packet --format markdown --out <private-output-dir>)\n```",
        qa_note,
    )
    assert match is not None, "support-packet Markdown QA note should document the checked command"

    private_out = tmp_path / "qa-private-output" / "client-workspace-ledger"
    documented_command = match.group("command").replace("<private-output-dir>", str(private_out))
    assert documented_command.startswith("python -m agentledger support-packet --format markdown --out ")

    assert cli.main(["support-packet", "--format", "markdown", "--out", str(private_out)]) == 0
    output = capsys.readouterr().out

    expected_headings = [
        "## AgentLedger alpha support report",
        "### Summary",
        "### Command used",
        "### Generated review/share files reviewed",
        "### Redacted error text or first confusing message",
        "### Useful commands",
        "### Keep private by default",
    ]
    for heading in expected_headings:
        assert heading in qa_note
        assert heading in output

    for marker in [
        "Raw evidence copied: no",
        "Local paths included: no",
        "Raw evidence kept private: yes",
    ]:
        assert marker in qa_note
        assert marker in output

    assert "<agentledger-output>" in output
    assert str(private_out) not in output
    assert private_out.name not in output


def test_support_packet_markdown_issue_template_is_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    issue_template = ALPHA_FEEDBACK_ISSUE_TEMPLATE.read_text(encoding="utf-8")
    qa_note = SUPPORT_PACKET_MARKDOWN_QA.read_text(encoding="utf-8")
    feedback_template = (ROOT / "docs" / "alpha-feedback-template.md").read_text(encoding="utf-8")

    assert "Support-packet Markdown feedback" in issue_template
    assert "Support-packet Markdown feedback" in qa_note
    assert "Support-packet Markdown feedback" in feedback_template
    assert 'python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.25-alpha"' in issue_template
    assert "python -m agentledger --version" in issue_template
    assert "v0.1.25-alpha" in issue_template

    match = re.search(
        r"```powershell\n(?P<command>python -m agentledger support-packet --format markdown --out <private-output-dir>)\n```",
        issue_template,
    )
    assert match is not None, "alpha feedback issue template should document the checked support-packet command"

    private_out = tmp_path / "issue-private-output" / "customer-ledger"
    documented_command = match.group("command").replace("<private-output-dir>", str(private_out))
    assert documented_command.startswith("python -m agentledger support-packet --format markdown --out ")

    assert cli.main(["support-packet", "--format", "markdown", "--out", str(private_out)]) == 0
    output = capsys.readouterr().out

    expected_headings = [
        "## AgentLedger alpha support report",
        "### Summary",
        "### Command used",
        "### Generated review/share files reviewed",
        "### Redacted error text or first confusing message",
        "### Useful commands",
        "### Keep private by default",
    ]
    for heading in expected_headings:
        assert heading in issue_template
        assert heading in output

    for marker in [
        "<agentledger-output>",
        "supplied private output path",
        "private repo paths",
        "private URLs",
        "credentials",
        "tokens",
        "secrets",
        "customer data",
        "raw `.agentledger/` folders",
        "zip bundles",
        "transcripts",
        "signing keys",
        "temp workspaces",
    ]:
        assert marker in issue_template

    assert "<agentledger-output>" in output
    assert str(private_out) not in output
    assert private_out.name not in output


def test_alpha_feedback_readiness_note_is_checked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    readiness = ALPHA_FEEDBACK_READINESS.read_text(encoding="utf-8")
    issue_template = ALPHA_FEEDBACK_ISSUE_TEMPLATE.read_text(encoding="utf-8")
    qa_note = SUPPORT_PACKET_MARKDOWN_QA.read_text(encoding="utf-8")
    release_process = (ROOT / "docs" / "release-process.md").read_text(encoding="utf-8")

    assert "[docs/alpha-feedback-readiness.md](alpha-feedback-readiness.md)" in qa_note
    assert "`docs/alpha-feedback-readiness.md`" in release_process
    assert ".github/ISSUE_TEMPLATE/alpha-feedback.md" in readiness
    assert "Support-packet Markdown feedback" in readiness
    assert "Support-packet Markdown feedback" in issue_template
    assert "v0.1.25-alpha" in readiness
    assert "installed version and install method" in readiness
    assert "sanitized Markdown snippets" in release_process
    assert "copy-ready headings" in release_process
    assert "redaction confirmation" in release_process
    assert "no raw\nevidence bundles, private paths, secrets, or customer data" in release_process

    match = re.search(
        r"```powershell\n(?P<command>python -m agentledger support-packet --format markdown --out <private-output-dir>)\n```",
        readiness,
    )
    assert match is not None, "alpha feedback readiness should document the checked support-packet command"

    private_out = tmp_path / "readiness-private-output" / "sensitive-client-ledger"
    documented_command = match.group("command").replace("<private-output-dir>", str(private_out))
    assert documented_command.startswith("python -m agentledger support-packet --format markdown --out ")

    assert cli.main(["support-packet", "--format", "markdown", "--out", str(private_out)]) == 0
    output = capsys.readouterr().out

    expected_headings = [
        "## AgentLedger alpha support report",
        "### Summary",
        "### Command used",
        "### Generated review/share files reviewed",
        "### Redacted error text or first confusing message",
        "### Useful commands",
        "### Keep private by default",
    ]
    for heading in expected_headings:
        assert heading in readiness
        assert heading in issue_template
        assert heading in output

    for marker in [
        "<agentledger-output>",
        "raw `.agentledger/` folders",
        "zip bundles",
        "transcripts",
        "signing keys",
        "temp workspaces",
        "private paths",
        "private URLs",
        "credentials",
        "tokens",
        "secrets",
        "customer data",
    ]:
        assert marker in readiness
        assert marker in issue_template

    assert "<agentledger-output>" in output
    assert str(private_out) not in output
    assert private_out.name not in output
