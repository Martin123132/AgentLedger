from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_command_index.py"

spec = importlib.util.spec_from_file_location("release_command_index", SCRIPT)
assert spec is not None
release_command_index = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release_command_index
assert spec.loader is not None
spec.loader.exec_module(release_command_index)


def test_build_release_command_index_lists_ordered_release_flow() -> None:
    index = release_command_index.build_release_command_index(
        version="0.1.8a0",
        release_date="2026-06-15",
    )

    assert index["schema_version"] == "agentledger.release_command_index.v1"
    assert index["release_label"] == "0.1.8-alpha"
    assert index["tag"] == "v0.1.8-alpha"
    assert (
        index["artifacts"]["release_rehearsal_manifest"]
        == "$env:TEMP\\agentledger-release-rehearsal-0.1.8-alpha\\release-rehearsal-manifest.json"
    )
    assert (
        index["artifacts"]["release_rehearsal_receipt"]
        == "$env:TEMP\\agentledger-release-rehearsal-0.1.8-alpha\\release-rehearsal-receipt.md"
    )
    assert index["artifacts"]["release_readiness_report"] == "$env:TEMP\\agentledger-release-readiness-report.md"
    assert index["artifacts"]["release_check_json"] == "$env:TEMP\\agentledger-release-check.json"
    assert index["artifacts"]["post_release_dir"] == "$env:TEMP\\agentledger-post-release-0.1.8-alpha"

    section_names = [section["name"] for section in index["sections"]]
    assert section_names[:7] == [
        "1. Start clean",
        "2. Rehearse and prepare source files",
        "3. Validate the release branch",
        "4. Open and merge the release PR",
        "5. Run release readiness and tag",
        "6. Finalize and publish release notes",
        "7. Post-release checks and handoff",
    ]

    all_commands = "\n".join(
        command for section in index["sections"] for command in section["commands"]
    )
    for fragment in [
        "python scripts/rehearse_release.py --version 0.1.8a0",
        "python scripts/verify_release_rehearsal.py $env:TEMP\\agentledger-release-rehearsal-0.1.8-alpha\\release-rehearsal-manifest.json",
        "python scripts/release_artifact_doctor.py --version 0.1.8a0 --stage rehearsal --rehearsal-manifest $env:TEMP\\agentledger-release-rehearsal-0.1.8-alpha\\release-rehearsal-manifest.json",
        "python scripts/release_rehearsal_receipt.py $env:TEMP\\agentledger-release-rehearsal-0.1.8-alpha\\release-rehearsal-manifest.json --format markdown --output $env:TEMP\\agentledger-release-rehearsal-0.1.8-alpha\\release-rehearsal-receipt.md",
        "python scripts/release_readiness_report.py --format markdown",
        "python scripts/release_artifact_doctor.py --version 0.1.8a0 --stage final-notes",
        "gh workflow run \"Release Readiness\"",
        "git tag v0.1.8-alpha",
        "python scripts/post_release_check.py --version 0.1.8a0",
        "python scripts/release_evidence_packet.py --version 0.1.8a0",
    ]:
        assert fragment in all_commands


def test_format_markdown_uses_artifact_names_and_code_blocks() -> None:
    index = release_command_index.build_release_command_index(
        version="0.1.8a0",
        release_date="2026-06-15",
    )

    markdown = release_command_index.format_markdown(index)

    assert markdown.startswith("# AgentLedger Release Command Index\n")
    assert "## 6. Finalize and publish release notes" in markdown
    assert "```powershell" in markdown
    assert "`release_evidence_json`: `$env:TEMP\\agentledger-release-evidence.json`" in markdown
    assert "Do not commit `.agentledger/`." in markdown


def test_main_writes_json_command_index(tmp_path: Path, capsys) -> None:
    output = tmp_path / "release-command-index.json"

    exit_code = release_command_index.main(
        [
            "--version",
            "0.1.8a0",
            "--date",
            "2026-06-15",
            "--format",
            "json",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == f"Release command index written: {output}\n"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "agentledger.release_command_index.v1"
    assert payload["placeholders"] == [
        "<pr-number>",
        "<run-id>",
        "<tag-run-id>",
        "<pr-run>",
        "<master-run>",
        "<release-readiness-run>",
        "<tag-run>",
        "<merge-sha>",
    ]


def test_main_rejects_invalid_date(capsys) -> None:
    exit_code = release_command_index.main(
        ["--version", "0.1.8a0", "--date", "15-06-2026"]
    )

    assert exit_code == 2
    assert "release date must be YYYY-MM-DD" in capsys.readouterr().err
