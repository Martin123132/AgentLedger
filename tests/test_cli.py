from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from agentledger.cli import main
from agentledger.doctor import run_doctor


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


def test_snapshot_writes_json_and_markdown(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    code = main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"])

    assert code == 0
    latest = Path((out / "latest.txt").read_text(encoding="utf-8"))
    report = json.loads((latest / "agentledger-report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "agentledger.report.v1"
    assert report["target_repo"] == str(repo.resolve())
    assert (latest / "agentledger-report.md").exists()
    assert (latest / "agentledger-report.html").exists()
    assert latest.with_suffix(".zip").exists()


def test_run_captures_command_and_diff(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    code = main(
        [
            "run",
            "--repo",
            str(repo),
            "--out",
            str(out),
            "--no-repomori",
            "--no-jester",
            "--no-tokometer",
            "--",
            "python",
            "-c",
            "from pathlib import Path; Path('note.txt').write_text('hello')",
        ]
    )

    assert code == 0
    latest = Path((out / "latest.txt").read_text(encoding="utf-8"))
    report = json.loads((latest / "agentledger-report.json").read_text(encoding="utf-8"))
    assert report["command"]["exit_code"] == 0
    assert Path(report["command"]["stdout_path"]).exists()
    assert Path(report["command"]["stderr_path"]).exists()
    assert report["command"]["test_detected"] is False
    assert "?? note.txt" in report["after"]["status"]


def test_run_detects_pytest_command(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    code = main(
        [
            "run",
            "--repo",
            str(repo),
            "--out",
            str(out),
            "--no-repomori",
            "--no-jester",
            "--no-tokometer",
            "--",
            "python",
            "-m",
            "pytest",
            "--version",
        ]
    )

    assert code == 0
    latest = Path((out / "latest.txt").read_text(encoding="utf-8"))
    report = json.loads((latest / "agentledger-report.json").read_text(encoding="utf-8"))
    assert report["command"]["test_detected"] is True
    assert report["command"]["test_framework"] == "pytest"


def test_missing_optional_jester_does_not_fail_successful_command(tmp_path: Path, monkeypatch) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    import agentledger.integrations as integrations

    original_which = integrations.shutil.which

    def fake_which(name: str):
        if name in {"jester", "memento-mori-jester"}:
            return None
        return original_which(name)

    monkeypatch.setattr(integrations.shutil, "which", fake_which)

    code = main(
        [
            "run",
            "--repo",
            str(repo),
            "--out",
            str(out),
            "--no-repomori",
            "--no-tokometer",
            "--",
            sys.executable,
            "-c",
            "print('ok')",
        ]
    )

    assert code == 0


def test_doctor_returns_status() -> None:
    report = run_doctor()
    assert report["schema_version"] == "agentledger.doctor.v1"
    assert report["status"] in {"ready", "partial", "blocked"}
    assert report["checks"]
