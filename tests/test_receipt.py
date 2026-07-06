from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

from agentledger import cli


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "agentledger@example.local")
    git(repo, "config", "user.name", "AgentLedger Test")
    (repo / "README.md").write_text("# Demo\n", encoding="utf-8")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "initial")
    return repo


def parse_json_output(output: str) -> dict:
    start = output.find("{")
    end = output.rfind("}")
    assert start != -1 and end != -1 and end >= start
    return json.loads(output[start : end + 1])


def receipt_command(repo: Path, out: Path, *extra: str) -> list[str]:
    return [
        "receipt",
        "--repo",
        str(repo),
        "--out",
        str(out),
        "--no-repomori",
        "--no-jester",
        "--no-tokometer",
        *extra,
        "--format",
        "json",
        "--",
        sys.executable,
        "-c",
        "from pathlib import Path; Path('note.txt').write_text('hello')",
    ]


def test_receipt_command_writes_buyer_receipt_and_verifies_bundle(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(receipt_command(repo, out)) == 0

    payload = parse_json_output(capsys.readouterr().out)
    run_dir = Path(payload["run_dir"])
    bundle = Path(payload["evidence"]["bundle"])

    assert payload["schema_version"] == "agentledger.receipt.v1"
    assert payload["ok"] is True
    assert payload["acceptance"] == "review"
    assert payload["review"]["status"] == "warn"
    assert payload["bundle"]["ok"] is True
    assert payload["signature"] is None
    assert (run_dir / "agentledger-receipt.md").exists()
    assert (run_dir / "agentledger-receipt.json").exists()
    assert (run_dir / "agentledger-receipt.html").exists()
    assert bundle.exists()
    assert "AgentLedger Run Receipt" in (run_dir / "agentledger-receipt.md").read_text(encoding="utf-8")

    with ZipFile(bundle) as archive:
        members = set(archive.namelist())
    assert f"{run_dir.name}/agentledger-receipt.md" in members
    assert f"{run_dir.name}/agentledger-receipt.json" in members
    assert f"{run_dir.name}/agentledger-receipt.html" in members


def test_receipt_strict_returns_warning_exit(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(receipt_command(repo, out, "--strict")) == 1

    payload = parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.receipt.v1"
    assert payload["ok"] is False
    assert payload["acceptance"] == "blocked"
    assert payload["review"]["status"] == "warn"
    assert payload["receipt_exit_code"] == 1
    assert payload["bundle"]["ok"] is True


def test_receipt_can_sign_and_verify_bundle(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    key_file = tmp_path / "receipt-key.txt"
    key_file.write_text("shared-test-key\n", encoding="utf-8")

    assert cli.main(receipt_command(repo, out, "--signature-key-file", str(key_file))) == 0

    payload = parse_json_output(capsys.readouterr().out)
    assert payload["signature"]["ok"] is True
    assert payload["bundle"]["ok"] is True
    assert payload["bundle"]["signature"]["status"] == "verified"
    assert payload["bundle"]["signature"]["verified"] is True


def test_receipt_requires_task_command(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)

    assert cli.main(["receipt", "--repo", str(repo), "--format", "json"]) == 2

    payload = parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.receipt.v1"
    assert payload["ok"] is False
    assert payload["acceptance"] == "blocked"
    assert "No command supplied" in payload["errors"][0]
