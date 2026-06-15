from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check_release_process.py"

spec = importlib.util.spec_from_file_location("check_release_process", SCRIPT)
assert spec is not None
check_release_process = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = check_release_process
assert spec.loader is not None
spec.loader.exec_module(check_release_process)


def test_release_process_doc_matches_generated_command_index() -> None:
    result = check_release_process.check_release_process()

    assert result["schema_version"] == "agentledger.release_process_check.v1"
    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["index_schema_version"] == "agentledger.release_command_index.v1"
    assert result["summary"]["failed"] == 0
    assert result["summary"]["total"] >= 60
    assert not result["errors"]
    assert all("next_action" not in check for check in result["checks"])


def test_release_process_check_reports_missing_index_command(tmp_path: Path) -> None:
    doc = ROOT / "docs" / "release-process.md"
    text = doc.read_text(encoding="utf-8")
    missing_command = "gh pr ready <pr-number>"
    assert missing_command in text
    drifted = tmp_path / "release-process.md"
    drifted.write_text(text.replace(missing_command, "gh pr ready"), encoding="utf-8")

    result = check_release_process.check_release_process(doc=drifted)

    assert result["ok"] is False
    assert result["status"] == "failed"
    assert missing_command in result["errors"][0] or any(missing_command in error for error in result["errors"])
    assert any(
        check["category"] == "command"
        and check["expected"] == missing_command
        and check["status"] == "failed"
        for check in result["checks"]
    )
    assert result["next_actions"] == [
        "Update docs/release-process.md or scripts/release_command_index.py so the release flow stays aligned."
    ]


def test_main_writes_json_result(tmp_path: Path, capsys) -> None:
    output = tmp_path / "release-process-check.json"

    exit_code = check_release_process.main(
        ["--format", "json", "--output", str(output)]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == f"Release process check written: {output}\n"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "agentledger.release_process_check.v1"
    assert payload["ok"] is True


def test_main_returns_nonzero_for_drifted_doc(tmp_path: Path, capsys) -> None:
    doc = ROOT / "docs" / "release-process.md"
    text = doc.read_text(encoding="utf-8")
    drifted = tmp_path / "release-process.md"
    drifted.write_text(text.replace("gh pr create --draft --fill", "gh pr create"), encoding="utf-8")

    exit_code = check_release_process.main(["--doc", str(drifted)])

    assert exit_code == 2
    output = capsys.readouterr().out
    assert "Release process check FAILED" in output
    assert "gh pr create --draft --fill" in output
