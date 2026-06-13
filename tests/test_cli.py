from __future__ import annotations

import json
from zipfile import ZipFile
import subprocess
import sys
from pathlib import Path

import pytest

from agentledger import __version__, cli
from agentledger.doctor import format_doctor, run_doctor
from agentledger import report_reader


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _parse_json_output(output: str) -> dict:
    start = output.find("{")
    end = output.rfind("}")
    assert start != -1 and end != -1 and end >= start
    return json.loads(output[start : end + 1])


def _bundle_text(bundle: Path) -> str:
    chunks = []
    with ZipFile(bundle) as archive:
        for name in archive.namelist():
            if name.endswith((".json", ".md", ".html", ".txt")):
                chunks.append(archive.read(name).decode("utf-8", errors="replace"))
    return "\n".join(chunks)


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
    markdown = (latest / "agentledger-report.md").read_text(encoding="utf-8")
    html = (latest / "agentledger-report.html").read_text(encoding="utf-8")
    assert "## Review Summary" in markdown
    assert "- Outcome: `command passed`" in markdown
    assert "- Changed files: `1`" in markdown
    assert "## Human Review Checklist" in markdown
    assert "Confirm the command matches the intended task." in markdown
    assert '<span class="badge ok">command passed</span>' in html
    assert "Human Review Checklist" in html
    assert "Review focus:" in html


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


def test_run_redacts_obvious_secrets_from_reports_and_bundle(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    output_secret = "super-secret-output-12345"
    bearer_secret = "abcdefghijklmnop123456"
    flag_secret = "flag-password-12345"

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
            sys.executable,
            "-c",
            (
                "import sys; "
                f"print('API_KEY={output_secret}'); "
                f"print('Authorization: Bearer {bearer_secret}', file=sys.stderr)"
            ),
            "--password",
            flag_secret,
        ]
    )

    assert code == 0
    latest = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    report_json = (latest / "agentledger-report.json").read_text(encoding="utf-8")
    markdown = (latest / "agentledger-report.md").read_text(encoding="utf-8")
    html = (latest / "agentledger-report.html").read_text(encoding="utf-8")
    stdout = (latest / "artifacts" / "command" / "stdout.txt").read_text(encoding="utf-8")
    stderr = (latest / "artifacts" / "command" / "stderr.txt").read_text(encoding="utf-8")
    bundle_text = _bundle_text(latest.with_suffix(".zip"))
    combined = "\n".join([report_json, markdown, html, stdout, stderr, bundle_text])

    assert output_secret not in combined
    assert bearer_secret not in combined
    assert flag_secret not in combined
    assert "API_KEY=[REDACTED]" in combined
    assert "Bearer [REDACTED]" in combined
    report = json.loads(report_json)
    assert report["command"]["command"][-1] == "[REDACTED]"


def test_snapshot_redacts_obvious_secrets_from_git_diff(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    password_secret = "diff-password-12345"
    openai_secret = "sk-" + "abcdefghijklmnopqrstuvwxyz123456"
    (repo / "README.md").write_text(
        f"# Demo\nPASSWORD={password_secret}\nOPENAI_API_KEY={openai_secret}\n",
        encoding="utf-8",
    )

    code = cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"])

    assert code == 0
    latest = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    report_json = (latest / "agentledger-report.json").read_text(encoding="utf-8")
    markdown = (latest / "agentledger-report.md").read_text(encoding="utf-8")
    html = (latest / "agentledger-report.html").read_text(encoding="utf-8")
    bundle_text = _bundle_text(latest.with_suffix(".zip"))
    combined = "\n".join([report_json, markdown, html, bundle_text])

    assert password_secret not in combined
    assert openai_secret not in combined
    assert "PASSWORD=[REDACTED]" in combined
    assert "OPENAI_API_KEY=[REDACTED]" in combined


def test_run_privacy_summary_omits_transcripts_and_full_diff(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    stdout_detail = "summary-stdout-detail-12345"
    diff_detail = "summary-diff-detail-12345"
    (repo / "emit.py").write_text(
        (
            "from pathlib import Path\n"
            f"print('{stdout_detail}')\n"
            f"Path('README.md').write_text('# Demo\\n{diff_detail}\\n', encoding='utf-8')\n"
        ),
        encoding="utf-8",
    )
    git(repo, "add", "emit.py")
    git(repo, "commit", "-m", "add emitter")

    code = cli.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out",
            str(out),
            "--privacy-mode",
            "summary",
            "--",
            sys.executable,
            "emit.py",
        ]
    )

    assert code == 0
    latest = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    report_json = (latest / "agentledger-report.json").read_text(encoding="utf-8")
    markdown = (latest / "agentledger-report.md").read_text(encoding="utf-8")
    html = (latest / "agentledger-report.html").read_text(encoding="utf-8")
    stdout = (latest / "artifacts" / "command" / "stdout.txt").read_text(encoding="utf-8")
    bundle_text = _bundle_text(latest.with_suffix(".zip"))
    combined = "\n".join([report_json, markdown, html, stdout, bundle_text])
    report = json.loads(report_json)

    assert report["privacy_mode"] == "summary"
    assert report["after"]["diff"] == ""
    assert report["command"]["stdout_tail"] == ""
    assert stdout_detail not in combined
    assert diff_detail not in combined
    assert "Command stdout [omitted by privacy-mode summary]." in combined
    assert "Full diff omitted by privacy-mode summary." in combined
    assert "Privacy mode summary skipped RepoMori snapshots." in report["warnings"]
    assert "Privacy mode summary skipped Jester diff gate." in report["warnings"]
    assert "Privacy mode summary skipped Tokometer path evidence." in report["warnings"]


def test_config_file_sets_run_defaults(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    config_out = repo / "ledger-from-config"
    (repo / ".agentledger.toml").write_text(
        "\n".join(
            [
                'privacy_mode = "summary"',
                'out = "ledger-from-config"',
                "repomori = false",
                "jester = false",
                "tokometer = false",
                "zip = false",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (repo / "emit.py").write_text(
        (
            "from pathlib import Path\n"
            "print('config-policy-output-detail')\n"
            "Path('README.md').write_text('# Demo\\nconfig-policy-diff-detail\\n', encoding='utf-8')\n"
        ),
        encoding="utf-8",
    )
    git(repo, "add", "emit.py")
    git(repo, "commit", "-m", "add emitter")

    code = cli.main(["run", "--repo", str(repo), "--", sys.executable, "emit.py"])

    assert code == 0
    output = capsys.readouterr().out
    latest = Path((config_out / "latest.txt").read_text(encoding="utf-8").strip())
    report = json.loads((latest / "agentledger-report.json").read_text(encoding="utf-8"))
    combined = "\n".join(
        [
            (latest / "agentledger-report.json").read_text(encoding="utf-8"),
            (latest / "agentledger-report.md").read_text(encoding="utf-8"),
            (latest / "agentledger-report.html").read_text(encoding="utf-8"),
            (latest / "artifacts" / "command" / "stdout.txt").read_text(encoding="utf-8"),
        ]
    )

    assert report["privacy_mode"] == "summary"
    assert report["after"]["diff"] == ""
    assert report["command"]["stdout_tail"] == ""
    assert "config-policy-output-detail" not in combined
    assert "config-policy-diff-detail" not in combined
    assert "Privacy mode summary skipped RepoMori snapshots." not in report["warnings"]
    assert "Privacy mode summary skipped Jester diff gate." not in report["warnings"]
    assert "Privacy mode summary skipped Tokometer path evidence." not in report["warnings"]
    assert "AgentLedger bundle:" not in output
    assert not latest.with_suffix(".zip").exists()

    assert cli.main(["open-latest", "--repo", str(repo)]) == 0
    open_output = capsys.readouterr().out
    assert str(config_out) in open_output

    assert cli.main(["history", "--repo", str(repo), "--format", "json"]) == 0
    history_output = capsys.readouterr().out
    history_payload = _parse_json_output(history_output)
    assert history_payload["out"] == str(config_out.resolve())


def test_cli_out_and_privacy_mode_override_config(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    cli_out = tmp_path / "cli-ledger"
    (repo / ".agentledger.toml").write_text(
        "\n".join(
            [
                'privacy_mode = "summary"',
                'out = "ledger-from-config"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    code = cli.main(
        [
            "run",
            "--repo",
            str(repo),
            "--out",
            str(cli_out),
            "--privacy-mode",
            "standard",
            "--no-repomori",
            "--no-jester",
            "--no-tokometer",
            "--",
            sys.executable,
            "-c",
            "print('cli-override-output-detail')",
        ]
    )

    assert code == 0
    latest = Path((cli_out / "latest.txt").read_text(encoding="utf-8").strip())
    report = json.loads((latest / "agentledger-report.json").read_text(encoding="utf-8"))
    assert report["privacy_mode"] == "standard"
    assert "cli-override-output-detail" in report["command"]["stdout_tail"]
    assert latest.with_suffix(".zip").exists()
    assert not (repo / "ledger-from-config").exists()


def test_invalid_config_prints_clear_error(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    (repo / ".agentledger.toml").write_text('privacy_mode = "loud"\n', encoding="utf-8")

    code = cli.main(["snapshot", "--repo", str(repo)])

    assert code == 2
    output = capsys.readouterr().out
    assert "Config error:" in output
    assert "privacy_mode must be 'standard' or 'summary'" in output


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
    assert report["status"] in {"ready", "blocked"}
    assert "required_ok" in report
    assert "optional" in report
    assert report["checks"]


def test_doctor_formats_missing_optional_as_ready() -> None:
    report = {
        "schema_version": "agentledger.doctor.v1",
        "status": "ready",
        "required_ok": True,
        "optional": {
            "configured": 1,
            "total": 2,
            "missing": ["repomori"],
        },
        "checks": [
            {
                "name": "git",
                "ok": True,
                "detail": "C:\\Git\\cmd\\git.exe",
                "required": True,
            },
            {
                "name": "repomori",
                "ok": False,
                "detail": "No module named repomori",
                "required": False,
            },
            {
                "name": "npx",
                "ok": True,
                "detail": "C:\\nodejs\\npx.cmd",
                "required": False,
            },
        ],
    }

    output = format_doctor(report)

    assert "AgentLedger doctor: ready (required checks passed; optional integrations missing)" in output
    assert "Optional integrations: 1/2 configured" in output
    assert "- git: ok (required)" in output
    assert "- repomori: not configured (optional)" in output
    assert "- npx: available (optional)" in output


def test_cli_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    output = capsys.readouterr().out
    assert f"agentledger {__version__}" in output


def test_open_latest_prints_report_paths(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"]) == 0
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

    assert latest_dir.exists()
    assert cli.main(["open-latest", "--out", str(out)]) == 0
    output = capsys.readouterr().out
    assert "Latest run:" in output
    assert f"Markdown report: {latest_dir / 'agentledger-report.md'}" in output
    assert f"JSON report: {latest_dir / 'agentledger-report.json'}" in output
    assert f"HTML report: {latest_dir / 'agentledger-report.html'}" in output


def test_open_latest_missing_pointer_prints_hint(tmp_path: Path, capsys) -> None:
    out = tmp_path / "ledger"
    out.mkdir()

    assert cli.main(["open-latest", "--out", str(out)]) == 2
    output = capsys.readouterr().out
    assert "No latest run pointer found:" in output
    assert "Run a capture first:" in output


def test_history_lists_recent_runs(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"]) == 0
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["history", "--out", str(out)]) == 0
    output = capsys.readouterr().out
    assert "AgentLedger runs in" in output
    assert latest_dir.name in output
    assert "exit=n/a" in output
    assert "command=No command executed" in output
    assert f"report={latest_dir / 'agentledger-report.md'}" in output


def test_history_json_output(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"]) == 0
    capsys.readouterr()

    assert cli.main(["history", "--format", "json", "--out", str(out)]) == 0
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["out"] == str(out.resolve())
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["command"] == "No command executed"
    assert payload["runs"][0]["exit_code"] is None
    assert payload["runs"][0]["changed_files"] == 0


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


def test_inspect_report_counts_status_files(tmp_path: Path, capsys) -> None:
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
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

    assert cli.main(["inspect-report", str(run_dir)]) == 0
    output = capsys.readouterr().out
    assert "Changed files: 1" in output


def test_changed_file_count_uses_status_untracked() -> None:
    report = {
        "after": {
            "diff_stat": "",
            "status": " M README.md\n?? note.txt\n D old.txt\n R  src/a.txt -> src/b.txt\nA  src/new.txt",
        }
    }
    assert report_reader.changed_file_count(report) == 5


def test_changed_file_count_uses_status_only() -> None:
    report = {
        "after": {
            "diff_stat": "",
            "status": "M  README.md\nA  new.txt\nR  old.txt -> renamed.txt\n D deleted.txt",
        }
    }
    assert report_reader.changed_file_count(report) == 4


def test_changed_file_count_uses_untracked_only() -> None:
    report = {
        "after": {
            "diff_stat": "",
            "status": "?? note.txt\n?? another.txt\n",
        }
    }
    assert report_reader.changed_file_count(report) == 2


def test_changed_file_count_diff_stat_with_untracked() -> None:
    report = {
        "after": {
            "diff_stat": "2 files changed, 9 insertions(+), 0 deletions(-)",
            "status": "?? note.txt\n",
        }
    }
    assert report_reader.changed_file_count(report) == 3


def test_changed_file_count_uses_status_and_diff_overlap() -> None:
    report = {
        "after": {
            "diff_stat": "1 file changed, 1 insertion(+)",
            "status": " M README.md\nA  staged.txt",
        }
    }
    assert report_reader.changed_file_count(report) == 2


def test_changed_file_count_handles_renamed_deleted_and_added_status_lines() -> None:
    report = {
        "after": {
            "diff_stat": "",
            "status": "R  src/old.txt -> src/new.txt\n D gone.txt\nA  added.txt\n?? untracked.txt",
        }
    }
    assert report_reader.changed_file_count(report) == 4


def test_command_exit_trend() -> None:
    assert report_reader.command_exit_trend(None, 0) == "not comparable"
    assert report_reader.command_exit_trend(0, 0) == "unchanged"
    assert report_reader.command_exit_trend(1, 0) == "improved"
    assert report_reader.command_exit_trend(0, 1) == "regressed"
    assert report_reader.command_exit_trend(2, 1) == "still failing"


def test_compare_reports(tmp_path: Path, capsys) -> None:
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
                "-c",
                "from pathlib import Path; Path('README.md').write_text('hello one')",
            ]
        )
        == 0
    )
    first = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

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
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('new'); Path('README.md').write_text('hello two')",
            ]
        )
        == 0
    )
    second = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

    first_report = json.loads((first / "agentledger-report.json").read_text(encoding="utf-8"))
    second_report = json.loads((second / "agentledger-report.json").read_text(encoding="utf-8"))
    first_summary = {"latest": {"total": 500, "active": 25}}
    second_summary = {"latest": {"total": 600, "active": 30}}
    (first / "tokometer-summary.json").write_text(json.dumps(first_summary) + "\n", encoding="utf-8")
    (second / "tokometer-summary.json").write_text(json.dumps(second_summary) + "\n", encoding="utf-8")
    first_report["artifacts"].append(
        {
            "name": "tokometer_summary",
            "ok": True,
            "command": [],
            "output_path": str(first / "tokometer-summary.json"),
            "summary": "Tokometer",
            "exit_code": 0,
        }
    )
    second_report["artifacts"].append(
        {
            "name": "tokometer_summary",
            "ok": True,
            "command": [],
            "output_path": str(second / "tokometer-summary.json"),
            "summary": "Tokometer",
            "exit_code": 0,
        }
    )
    (first / "agentledger-report.json").write_text(json.dumps(first_report) + "\n", encoding="utf-8")
    (second / "agentledger-report.json").write_text(json.dumps(second_report) + "\n", encoding="utf-8")

    assert cli.main(["compare", str(first), str(second)]) == 0
    output = capsys.readouterr().out
    assert "Comparing reports:" in output
    assert "Old command:" in output
    assert "New command:" in output
    assert "Changed files: 1 -> 2 (+1)" in output
    assert "Artifacts:" in output
    assert "Tokometer: ok: total=500; active=25 -> ok: total=600; active=30" in output


def test_verify_bundle_command(tmp_path: Path, capsys) -> None:
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
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    bundle = run_dir.with_suffix(".zip")

    assert cli.main(["verify-bundle", str(bundle)]) == 0
    output = capsys.readouterr().out
    assert f"Bundle OK: {bundle}" in output
    assert "Report:" in output

    broken = out / "broken.zip"
    with ZipFile(bundle) as src, ZipFile(broken, "w") as dst:
        for name in src.namelist():
            if name.endswith("agentledger-report.json"):
                continue
            dst.writestr(name, src.read(name))

    assert cli.main(["verify-bundle", str(broken)]) == 2
    output = capsys.readouterr().out
    assert "Missing agentledger-report.json" in output


def test_verify_bundle_requires_markdown_and_html(tmp_path: Path, capsys) -> None:
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
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    bundle = run_dir.with_suffix(".zip")

    missing_markdown = out / "missing-markdown.zip"
    with ZipFile(bundle) as src, ZipFile(missing_markdown, "w") as dst:
        for name in src.namelist():
            if name.endswith("agentledger-report.md"):
                continue
            dst.writestr(name, src.read(name))

    assert cli.main(["verify-bundle", str(missing_markdown)]) == 2
    output = capsys.readouterr().out
    assert "Bundle OK" not in output
    assert "Missing markdown report in bundle." in output


def test_verify_bundle_requires_html(tmp_path: Path, capsys) -> None:
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
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    bundle = run_dir.with_suffix(".zip")

    missing_html = out / "missing-html.zip"
    with ZipFile(bundle) as src, ZipFile(missing_html, "w") as dst:
        for name in src.namelist():
            if name.endswith("agentledger-report.html"):
                continue
            dst.writestr(name, src.read(name))

    assert cli.main(["verify-bundle", str(missing_html)]) == 2
    output = capsys.readouterr().out
    assert "Bundle OK" not in output
    assert "Missing HTML report in bundle." in output


def test_verify_bundle_rejects_invalid_json_bytes(tmp_path: Path, capsys) -> None:
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
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    bundle = run_dir.with_suffix(".zip")

    bad = out / "bad-json.zip"
    with ZipFile(bundle) as src, ZipFile(bad, "w") as dst:
        for name in src.namelist():
            if name.endswith("agentledger-report.json"):
                dst.writestr(name, b"\xff\xfe\xfd")
            else:
                dst.writestr(name, src.read(name))

    assert cli.main(["verify-bundle", str(bad)]) == 2
    output = capsys.readouterr().out
    assert "Invalid JSON in" in output


def test_verify_bundle_rejects_wrong_schema(tmp_path: Path, capsys) -> None:
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
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    bundle = run_dir.with_suffix(".zip")

    wrong_schema = out / "wrong-schema.zip"
    with ZipFile(bundle) as src, ZipFile(wrong_schema, "w") as dst:
        for name in src.namelist():
            if name.endswith("agentledger-report.json"):
                payload = json.loads(src.read(name).decode("utf-8"))
                payload["schema_version"] = "not.agentledger.report"
                dst.writestr(name, json.dumps(payload))
            else:
                dst.writestr(name, src.read(name))

    assert cli.main(["verify-bundle", str(wrong_schema)]) == 2
    output = capsys.readouterr().out
    assert "Unexpected report schema" in output


def test_inspect_report_json_output(tmp_path: Path, capsys) -> None:
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
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

    assert cli.main(["inspect-report", "--format", "json", str(run_dir)]) == 0
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["command"] == "python -c from pathlib import Path; Path('note.txt').write_text('hello')"
    assert payload["exit_code"] == 0
    assert payload["changed_files"] == 1
    assert payload["artifacts"]["ok"] == 0
    assert payload["test_framework"] == "n/a"


def test_compare_json_output(tmp_path: Path, capsys) -> None:
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
                "-c",
                "from pathlib import Path; Path('README.md').write_text('hello one')",
            ]
        )
        == 0
    )
    first = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

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
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello two')",
            ]
        )
        == 0
    )
    second = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

    assert cli.main(["compare", "--format", "json", str(first), str(second)]) == 0
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["changed_files"]["old"] == 1
    assert payload["changed_files"]["new"] == 2
    assert payload["exit_code"]["old"] == 0
    assert payload["exit_code"]["new"] == 0
    assert payload["exit_code"]["trend"] in {"unchanged", "improved", "regressed", "still failing", "not comparable"}
