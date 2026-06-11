from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from agentledger import cli
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

    code = cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"])

    assert code == 0
    latest = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    report = json.loads((latest / "agentledger-report.json").read_text(encoding="utf-8"))
    assert report["schema_version"] == "agentledger.report.v1"
    assert report["target_repo"] == str(repo.resolve())
    assert (latest / "agentledger-report.md").exists()
    assert (latest / "agentledger-report.html").exists()
    assert latest.with_suffix(".zip").exists()


def test_run_captures_command_and_diff(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    code = cli.main(
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

    code = cli.main(
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

    code = cli.main(
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


def test_open_latest_prints_report_paths(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"]) == 0
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

    assert latest_dir.exists()
    assert cli.main(["open-latest", "--out", str(out)]) == 0
    output = capsys.readouterr().out
    assert "Latest report directory:" in output
    assert f"Markdown: {latest_dir / 'agentledger-report.md'}" in output
    assert f"JSON: {latest_dir / 'agentledger-report.json'}" in output
    assert f"HTML: {latest_dir / 'agentledger-report.html'}" in output


def test_inspect_report_summarizes_command(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert (
        cli.main(
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
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

    assert cli.main(["inspect-report", str(run_dir)]) == 0
    output = capsys.readouterr().out
    assert "Command: python -m pytest --version" in output
    assert "Exit code: 0" in output
    assert "Test framework: pytest" in output
    assert "Diff stat:" in output
    assert "Changed files:" in output
    assert "Artifacts:" in output


def test_inspect_report_includes_integration_warnings_and_tokometer(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert (
        cli.main(
        [
            "snapshot",
            "--repo",
            str(repo),
            "--out",
            str(out),
            "--no-repomori",
            "--no-tokometer",
        ]
        )
        == 0
    )

    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    report_path = run_dir / "agentledger-report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))

    (run_dir / "tokometer-summary.json").write_text(
        json.dumps({"latest": {"total": 420, "active": 24}}, indent=2) + "\n",
        encoding="utf-8",
    )
    payload["artifacts"].append(
        {
            "name": "tokometer_summary",
            "ok": True,
            "command": [],
            "output_path": str(run_dir / "tokometer-summary.json"),
            "summary": "Imported Tokometer local usage summary.",
            "exit_code": 0,
        }
    )
    payload["artifacts"].append(
        {
            "name": "repomori_snapshot_before",
            "ok": False,
            "command": [],
            "output_path": str(run_dir / "repomori-before.json"),
            "summary": "RepoMori snapshot was not available.",
            "exit_code": 1,
        }
    )
    payload["artifacts"].append(
        {
            "name": "jester_diff",
            "ok": False,
            "command": [],
            "output_path": str(run_dir / "jester-diff.txt"),
            "summary": "Jester CLI was not found on PATH; skipped diff safety gate.",
            "exit_code": None,
        }
    )
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    assert cli.main(["inspect-report", str(run_dir)]) == 0
    output = capsys.readouterr().out
    assert "Tokometer: ok: total=420; active=24" in output
    assert "Warning: repomori_snapshot_before: RepoMori snapshot was not available." in output
    assert "Warning: jester_diff: Jester CLI was not found on PATH; skipped diff safety gate." in output


def test_changed_file_count_parsing() -> None:
    report = {"after": {"diff_stat": " 2 files changed, 5 insertions(+), 1 deletion(-)"}}
    assert cli._changed_file_count(report) == 2
