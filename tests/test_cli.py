from __future__ import annotations

import json
from zipfile import ZipFile
import subprocess
import sys
from pathlib import Path

import pytest

from agentledger import __version__, cli
from agentledger.bundle import (
    BUNDLE_MANIFEST_NAME,
    BUNDLE_MANIFEST_SCHEMA,
    BUNDLE_SIGNATURE_NAME,
    BUNDLE_SIGNATURE_SCHEMA,
)
from agentledger.config import load_config
from agentledger.doctor import format_doctor, format_doctor_markdown, run_doctor
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


def _bundle_manifest(bundle: Path) -> tuple[str, dict]:
    with ZipFile(bundle) as archive:
        for name in archive.namelist():
            if name.endswith(f"/{BUNDLE_MANIFEST_NAME}"):
                return name, json.loads(archive.read(name).decode("utf-8"))
    raise AssertionError("Missing bundle manifest")


def _bundle_signature(bundle: Path) -> tuple[str, dict]:
    with ZipFile(bundle) as archive:
        for name in archive.namelist():
            if name.endswith(f"/{BUNDLE_SIGNATURE_NAME}"):
                return name, json.loads(archive.read(name).decode("utf-8"))
    raise AssertionError("Missing bundle signature")


def _rule_by_id(payload: dict, rule_id: str) -> dict:
    for rule in payload["rules"]:
        if rule["id"] == rule_id:
            return rule
    raise AssertionError(f"Missing rule: {rule_id}")


def _alpha_summary_payload(path: Path) -> dict:
    latest_run = path.parent / "2026-06-15T000000Z0000-alpha"
    latest_run.mkdir(parents=True, exist_ok=True)
    bundle = latest_run.with_suffix(".zip")
    bundle.write_bytes(b"placeholder")
    return {
        "schema_version": "agentledger.alpha_summary.v1",
        "ok": True,
        "summary_file": str(path),
        "started_at": "2026-06-15T00:00:00+00:00",
        "ended_at": "2026-06-15T00:01:00+00:00",
        "repo": str(path.parent / "repo"),
        "out": str(path.parent),
        "latest_run": str(latest_run),
        "bundle": str(bundle),
        "agentledger_version": "agentledger 0.1.8a0",
        "python_version": "Python 3.13.13",
        "git_version": "git version 2.54.0.windows.1",
        "doctor": "AgentLedger doctor: ready (required checks passed)",
        "status": "warn",
        "status_summary": "2 warnings; review before accepting.",
        "status_exit_code": 0,
        "report_paths": {
            "markdown": str(latest_run / "agentledger-report.md"),
            "json": str(latest_run / "agentledger-report.json"),
            "html": str(latest_run / "agentledger-report.html"),
            "zip": str(bundle),
        },
        "feedback": {
            "total_entries": 1,
            "returned_entries": 1,
            "runs_with_feedback": 1,
            "latest_run_entries": 1,
            "categories": {"docs": 1},
            "severities": {"low": 1},
            "errors": [],
        },
        "next_actions": ["Read the Markdown report before sharing evidence."],
        "errors": [],
    }


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


def test_repository_policy_config_parses() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    config = load_config(repo_root)

    assert config.path == repo_root / ".agentledger.toml"
    assert config.privacy_mode == "summary"
    assert config.out == ".agentledger"
    assert config.repomori is False
    assert config.jester is False
    assert config.tokometer is False
    assert config.zip is True
    assert config.check_require_tests is True
    assert config.check_dirty == "warn"
    assert config.check_max_changed_files == 25
    assert config.check_allow_warnings is True


def test_init_config_writes_starter_policy(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)

    assert cli.main(["init-config", "--repo", str(repo)]) == 0

    output = capsys.readouterr().out
    config_path = repo / ".agentledger.toml"
    assert f"Wrote AgentLedger config: {config_path.resolve()}" in output
    assert "Policy preset: solo" in output
    assert "Next: python -m agentledger receipt" in output
    config = load_config(repo)
    assert config.privacy_mode == "summary"
    assert config.out == ".agentledger"
    assert config.repomori is False
    assert config.jester is False
    assert config.tokometer is False
    assert config.zip is True
    assert config.check_require_tests is True
    assert config.check_dirty == "warn"
    assert config.check_max_changed_files == 25
    assert config.check_allow_warnings is True


def test_init_config_refuses_existing_file_without_force(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    config_path = repo / ".agentledger.toml"
    config_path.write_text('privacy_mode = "standard"\n', encoding="utf-8")

    assert cli.main(["init-config", "--repo", str(repo)]) == 2

    output = capsys.readouterr().out
    assert f"Config already exists: {config_path.resolve()}" in output
    assert "Use --force to overwrite it." in output
    assert config_path.read_text(encoding="utf-8") == 'privacy_mode = "standard"\n'


def test_init_config_force_overwrites_existing_file(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    config_path = repo / ".agentledger.toml"
    config_path.write_text('privacy_mode = "standard"\n', encoding="utf-8")

    assert cli.main(["init-config", "--repo", str(repo), "--force"]) == 0

    capsys.readouterr()
    config = load_config(repo)
    assert config.privacy_mode == "summary"
    assert config.check_require_tests is True


def test_init_config_writes_client_handoff_preset(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)

    assert cli.main(["init-config", "--repo", str(repo), "--preset", "client-handoff"]) == 0

    output = capsys.readouterr().out
    config = load_config(repo)
    assert "Policy preset: client-handoff" in output
    assert config.privacy_mode == "summary"
    assert config.check_require_tests is True
    assert config.check_dirty == "warn"
    assert config.check_max_changed_files == 10
    assert config.check_allow_warnings is False


def test_init_config_writes_team_strict_preset(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)

    assert cli.main(["init-config", "--repo", str(repo), "--preset", "team-strict"]) == 0

    capsys.readouterr()
    config = load_config(repo)
    assert config.check_dirty == "block"
    assert config.check_max_changed_files == 10
    assert config.check_allow_warnings is False


def test_demo_command_creates_isolated_report(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "demo-workspace"

    assert cli.main(["demo", "--output-dir", str(workspace)]) == 0

    output = capsys.readouterr().out
    repo = workspace / "demo-repo"
    out = workspace / "agentledger-output"
    latest = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    report = json.loads((latest / "agentledger-report.json").read_text(encoding="utf-8"))

    assert "AgentLedger demo: pass" in output
    assert f"Workspace: {workspace.resolve()}" in output
    assert f"Demo repo: {repo.resolve()}" in output
    assert f"Evidence output: {out.resolve()}" in output
    assert "What happened:" in output
    assert "- Created an isolated demo git repo." in output
    assert "- Captured command:" in output
    assert "- Privacy mode: summary" in output
    assert "python -m agentledger open-latest" in output
    assert "Read first:" in output
    assert "- Open the Markdown report for the human summary." in output
    assert "- Run status when you want the pass/warn/block verdict." in output
    assert "Next real repo:" in output
    assert "- python -m agentledger alpha-guide --repo . --out .agentledger" in output
    assert "JSON report:" in output
    assert "Cleanup:" in output
    assert repo.exists()
    assert out.exists()
    assert (latest / "agentledger-report.md").exists()
    assert (latest / "agentledger-report.html").exists()
    assert latest.with_suffix(".zip").exists()
    assert report["target_repo"] == str(repo.resolve())
    assert report["privacy_mode"] == "summary"
    assert report["command"]["test_detected"] is True
    assert report["command"]["test_framework"] == "unittest"
    assert "?? demo-result.txt" in report["after"]["status"]


def test_demo_command_json_output_lists_evidence_paths(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "demo-workspace"

    assert cli.main(["demo", "--format", "json", "--output-dir", str(workspace)]) == 0

    payload = _parse_json_output(capsys.readouterr().out)
    repo = workspace / "demo-repo"
    out = workspace / "agentledger-output"
    latest = Path((out / "latest.txt").read_text(encoding="utf-8").strip())

    assert payload["schema_version"] == "agentledger.demo.v1"
    assert payload["ok"] is True
    assert payload["status"] == "pass"
    assert payload["workspace"] == str(workspace.resolve())
    assert payload["repo"] == str(repo.resolve())
    assert payload["out"] == str(out.resolve())
    assert payload["latest_run"] == str(latest)
    assert payload["paths"]["markdown"] == str(latest / "agentledger-report.md")
    assert payload["paths"]["json"] == str(latest / "agentledger-report.json")
    assert payload["paths"]["html"] == str(latest / "agentledger-report.html")
    assert payload["paths"]["zip"] == str(latest.with_suffix(".zip"))
    assert payload["privacy_mode"] == "summary"
    assert payload["command"][-2:] == ["unittest", "test_demo.py"]
    assert payload["command_exit_code"] == 0
    assert payload["summary_output"] is None
    assert payload["summary_written"] is False
    assert payload["packet"] is None
    assert len(payload["try_next"]) == 5
    assert payload["cleanup"]
    assert payload["errors"] == []


def test_demo_command_packet_prints_open_packet_paths(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "demo-workspace"

    assert cli.main(["demo", "--packet", "--output-dir", str(workspace)]) == 0

    output = capsys.readouterr().out
    repo = workspace / "demo-repo"
    out = workspace / "agentledger-output"
    packet_dir = workspace / "agentledger-alpha-packet"

    assert "Alpha packet:" in output
    assert "- Wrote a share-safe alpha packet for review." in output
    assert f"Latest alpha packet: {packet_dir.resolve()}" in output
    assert f"Packet pointer: {(out / 'latest-alpha-packet.json').resolve()}" in output
    assert "Raw evidence copied: no" in output
    assert "Review/share after reading:" in output
    assert f"- Issue/comment draft: {packet_dir / 'agentledger-alpha-issue.md'}" in output
    assert f"- Markdown packet: {packet_dir / 'agentledger-alpha-handoff.md'}" in output
    assert f"- JSON packet: {packet_dir / 'agentledger-alpha-handoff.json'}" in output
    assert "Keep local:" in output
    assert f"- Demo workspace: {workspace.resolve()}" in output
    assert f"- Raw evidence output: {out.resolve()}" in output
    assert "- Raw AgentLedger evidence unless someone explicitly asks for it." in output
    assert "- Do not attach raw .agentledger evidence." in output
    assert "Feedback to include:" in output
    assert "- Platform, shell, Python version, and AgentLedger version." in output
    assert "- Redacted error text or the first confusing message, with secrets and private source removed." in output
    assert f"python -m agentledger open-packet --repo {repo.resolve()} --out {out.resolve()}" in output
    assert (out / "latest-alpha-packet.json").exists()
    assert (packet_dir / "agentledger-alpha-issue.md").exists()
    assert (packet_dir / "agentledger-alpha-handoff.md").exists()
    assert (packet_dir / "agentledger-alpha-handoff.json").exists()


def test_try_command_runs_packet_demo(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "try-workspace"

    assert cli.main(["try", "--output-dir", str(workspace)]) == 0

    output = capsys.readouterr().out
    out = workspace / "agentledger-output"
    packet_dir = workspace / "agentledger-alpha-packet"

    assert "AgentLedger try: pass" in output
    assert "- Used the one-command safe try path: isolated demo plus packet handoff." in output
    assert "Alpha packet:" in output
    assert f"Latest alpha packet: {packet_dir.resolve()}" in output
    assert "Review/share after reading:" in output
    assert "Keep local:" in output
    assert "Feedback to include:" in output
    assert "Generated review/share files from the alpha packet after you have reviewed them." in output
    assert f"- Raw evidence output: {out.resolve()}" in output
    assert (out / "latest-alpha-packet.json").exists()
    assert (packet_dir / "agentledger-alpha-issue.md").exists()
    assert (packet_dir / "agentledger-alpha-handoff.md").exists()
    assert (packet_dir / "agentledger-alpha-handoff.json").exists()


def test_demo_command_packet_json_output(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "demo-workspace"

    assert cli.main(["demo", "--packet", "--format", "json", "--output-dir", str(workspace)]) == 0

    payload = _parse_json_output(capsys.readouterr().out)
    out = workspace / "agentledger-output"
    packet_dir = workspace / "agentledger-alpha-packet"
    packet = payload["packet"]

    assert packet["requested"] is True
    assert packet["ok"] is True
    assert packet["output_dir"] == str(packet_dir.resolve())
    assert packet["latest_packet"] == str((out / "latest-alpha-packet.json").resolve())
    assert packet["files"]["issue"] == str(packet_dir / "agentledger-alpha-issue.md")
    assert packet["files"]["markdown"] == str(packet_dir / "agentledger-alpha-handoff.md")
    assert packet["files"]["json"] == str(packet_dir / "agentledger-alpha-handoff.json")
    assert packet["raw_evidence_copied"] is False
    assert packet["pack_exit_code"] == 0
    assert packet["open_exit_code"] == 0
    assert packet["errors"] == []
    assert any("open-packet" in command for command in payload["try_next"])
    assert payload["errors"] == []


def test_support_packet_prints_privacy_safe_checklist(capsys) -> None:
    assert cli.main(["support-packet"]) == 0

    output = capsys.readouterr().out

    assert "AgentLedger support packet checklist" in output
    assert "Raw evidence copied: no" in output
    assert "Local paths included: no" in output
    assert "Include in the report:" in output
    assert "Command used, such as python -m agentledger try" in output
    assert "Review/share only after reading:" in output
    assert "agentledger-alpha-issue.md" in output
    assert "Keep private by default:" in output
    assert "private repo paths, private URLs, non-public source, credentials, tokens, and secrets" in output
    assert "python -m agentledger pack-alpha --out .agentledger" in output
    assert "python -m agentledger support-packet --format markdown" in output
    assert "python -m agentledger support-packet --format json" in output


def test_support_packet_json_redacts_absolute_out_path(tmp_path: Path, capsys) -> None:
    private_out = tmp_path / "ledger"

    assert cli.main(["support-packet", "--format", "json", "--out", str(private_out)]) == 0

    output = capsys.readouterr().out
    payload = _parse_json_output(output)

    assert payload["schema_version"] == "agentledger.support_packet.v1"
    assert payload["ok"] is True
    assert payload["out"] == "<agentledger-output>"
    assert payload["out_redacted"] is True
    assert payload["local_paths_included"] is False
    assert payload["raw_evidence_copied"] is False
    assert payload["include"][0].startswith("Command used")
    assert payload["review_files"]
    assert any("private repo paths" in item for item in payload["keep_private"])
    assert payload["suggested_commands"]["machine_readable"] == [
        "python -m agentledger support-packet --format json"
    ]
    assert payload["suggested_commands"]["copy_ready"] == [
        "python -m agentledger support-packet --format markdown"
    ]
    assert payload["issue_template"][-1] == "Raw evidence kept private: yes"
    assert payload["errors"] == []
    assert str(private_out) not in output


def test_support_packet_markdown_is_copy_ready_and_path_redacted(tmp_path: Path, capsys) -> None:
    private_out = tmp_path / "private-ledger"

    assert cli.main(["support-packet", "--format", "markdown", "--out", str(private_out)]) == 0

    output = capsys.readouterr().out

    assert output.startswith("## AgentLedger alpha support report")
    assert "### Command used" in output
    assert "### Generated review/share files reviewed" in output
    assert "### Redacted error text or first confusing message" in output
    assert "### Keep private by default" in output
    assert "- Raw evidence copied: no" in output
    assert "- Local paths included: no" in output
    assert "- Raw evidence kept private: yes" in output
    assert "`python -m agentledger support-packet --format markdown`" in output
    assert "`python -m agentledger support-packet --format json`" in output
    assert "private repo paths, private URLs, non-public source, credentials, tokens, and secrets" in output
    assert "<agentledger-output>" in output
    assert str(private_out) not in output


def test_demo_command_writes_public_safe_summary(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "demo-workspace"
    summary = tmp_path / "demo-summary.md"

    assert cli.main(["demo", "--output-dir", str(workspace), "--summary-output", str(summary)]) == 0

    output = capsys.readouterr().out
    content = summary.read_text(encoding="utf-8")

    assert f"Public summary: {summary.resolve()}" in output
    assert "# AgentLedger Demo Summary" in content
    assert "- Result: pass" in content
    assert f"- AgentLedger: agentledger {__version__}" in content
    assert "- Captured command: python -B -m unittest test_demo.py" in content
    assert "- Evidence produced: Markdown report, HTML report, JSON report, zip bundle" in content
    assert "- Privacy mode: summary" in content
    assert "- Local paths: omitted from this summary" in content
    assert "- Raw evidence copied: no" in content
    assert "- python -m agentledger alpha-guide --repo . --out .agentledger" in content
    assert str(workspace.resolve()) not in content
    assert str(summary.resolve()) not in content


def test_demo_command_packet_summary_stays_path_free(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "demo-workspace"
    summary = tmp_path / "demo-summary.md"

    assert cli.main(["demo", "--packet", "--output-dir", str(workspace), "--summary-output", str(summary)]) == 0

    capsys.readouterr()
    content = summary.read_text(encoding="utf-8")

    assert "share-safe alpha packet" in content
    assert "- Review the alpha packet locally before sharing the listed files." in content
    assert str(workspace.resolve()) not in content
    assert str(summary.resolve()) not in content


def test_demo_command_json_output_reports_setup_errors(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "demo-workspace"
    workspace.mkdir()
    (workspace / "existing.txt").write_text("keep me\n", encoding="utf-8")

    assert cli.main(["demo", "--format", "json", "--output-dir", str(workspace)]) == 2

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.demo.v1"
    assert payload["ok"] is False
    assert payload["status"] == "failed"
    assert payload["workspace"] is None
    assert payload["paths"] == {}
    assert payload["try_next"] == []
    assert payload["cleanup"] is None
    assert payload["errors"] == [f"Output directory is not empty: {workspace.resolve()}"]


def test_demo_command_refuses_non_empty_output_dir(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "demo-workspace"
    workspace.mkdir()
    (workspace / "existing.txt").write_text("keep me\n", encoding="utf-8")

    assert cli.main(["demo", "--output-dir", str(workspace)]) == 2

    output = capsys.readouterr().out
    assert "AgentLedger demo: failed" in output
    assert f"Output directory is not empty: {workspace.resolve()}" in output
    assert not (workspace / "demo-repo").exists()


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
    assert "## Review Notes" in markdown
    assert "No recognized test command detected; run a verification command before accepting the work." in markdown
    assert "Review 1 changed file in the diff/status output." in markdown
    assert "## Evidence Files" in markdown
    assert f"- Markdown report: `{latest / 'agentledger-report.md'}`" in markdown
    assert f"- JSON report: `{latest / 'agentledger-report.json'}`" in markdown
    assert "## Human Review Checklist" in markdown
    assert "Confirm the command matches the intended task." in markdown
    assert '<span class="badge ok">command passed</span>' in html
    assert "<h2>Review Notes</h2>" in html
    assert "No recognized test command detected; run a verification command before accepting the work." in html
    assert "<h2>Evidence Files</h2>" in html
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
    assert "Summary privacy mode omits command transcript content and full diffs from reports." in combined
    assert "Privacy mode summary skipped RepoMori snapshots." in report["warnings"]
    assert "Privacy mode summary skipped Jester diff gate." in report["warnings"]
    assert "Privacy mode summary skipped Tokometer path evidence." in report["warnings"]


def test_privacy_summary_note_does_not_create_warning_status(tmp_path: Path, capsys) -> None:
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
                "--privacy-mode",
                "summary",
                "--no-repomori",
                "--no-jester",
                "--no-tokometer",
                "--",
                sys.executable,
                "-m",
                "pytest",
                "--version",
            ]
        )
        == 0
    )
    latest = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    report = json.loads((latest / "agentledger-report.json").read_text(encoding="utf-8"))
    markdown = (latest / "agentledger-report.md").read_text(encoding="utf-8")
    capsys.readouterr()

    assert report["privacy_mode"] == "summary"
    assert report["warnings"] == []
    assert "Summary privacy mode omits command transcript content and full diffs from reports." in markdown
    assert "report-level warning" not in markdown

    assert cli.main(["check", "--format", "json", str(latest)]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["status"] == "pass"
    assert payload["summary"] == "All 9 checks passed."
    assert _rule_by_id(payload, "report_warnings")["status"] == "pass"


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
    assert all("hint" in check for check in report["checks"])
    assert all(check["hint"] == "No action needed." for check in report["checks"] if check["ok"])


def test_doctor_reports_missing_repo_without_raising(tmp_path: Path) -> None:
    report = run_doctor(tmp_path / "missing-repo")

    assert report["schema_version"] == "agentledger.doctor.v1"
    assert report["status"] == "blocked"
    target_repo = next(check for check in report["checks"] if check["name"] == "target_git_repo")
    assert target_repo["ok"] is False
    assert target_repo["required"] is True
    assert target_repo["detail"]
    assert target_repo["hint"] == "Run from a git checkout or pass --repo <path> to an existing git repo."


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
                "hint": "Optional: install RepoMori, or keep using --no-repomori / repomori = false.",
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
    assert "Hint: Optional: install RepoMori" in output
    assert "- npx: available (optional)" in output


def test_doctor_formats_markdown_without_private_paths() -> None:
    report = {
        "schema_version": "agentledger.doctor.v1",
        "status": "blocked",
        "required_ok": False,
        "optional": {
            "configured": 0,
            "total": 1,
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
                "name": "target_git_repo",
                "ok": False,
                "detail": "fatal: cannot change to '/tmp/pytest/private/missing-repo'",
                "required": True,
                "hint": "Run from a git checkout or pass --repo <path> to an existing git repo.",
            },
            {
                "name": "repomori",
                "ok": False,
                "detail": "/opt/hostedtoolcache/Python/3.12.13/x64/bin/python: No module named repomori",
                "required": False,
                "hint": "Optional: install RepoMori, or keep using --no-repomori / repomori = false.",
            },
            {
                "name": "jester",
                "ok": False,
                "detail": "fatal: cannot change to 'D:\\Private\\CustomerRepo'",
                "required": False,
                "hint": "Optional: install Jester, or keep using --no-jester / jester = false.",
            },
        ],
    }

    output = format_doctor_markdown(report)

    assert output.startswith("## AgentLedger doctor report")
    assert "### Required checks" in output
    assert "### Optional integrations" in output
    assert "### What to try next" in output
    assert "- Local paths included: no" in output
    assert "- Raw evidence copied: no" in output
    assert "- [x] `git`: ok - <local path redacted>" in output
    assert "- [ ] `target_git_repo`: missing - <local path redacted>" in output
    assert "python -m agentledger support-packet --format markdown" in output
    assert "C:\\Git" not in output
    assert "D:\\Private" not in output
    assert "/tmp/pytest" not in output
    assert "/opt/hostedtoolcache" not in output


def test_doctor_markdown_cli_blocks_without_leaking_repo_path(tmp_path: Path, capsys) -> None:
    missing_repo = tmp_path / "missing-repo"

    assert cli.main(["doctor", "--repo", str(missing_repo), "--format", "markdown"]) == 2

    output = capsys.readouterr().out
    assert output.startswith("## AgentLedger doctor report")
    assert "- Status: blocked - required setup needs attention" in output
    assert "`target_git_repo`" in output
    assert "### Troubleshooting map" in output
    assert "python -m agentledger doctor --repo . --format markdown" in output
    assert str(missing_repo) not in output


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


def test_open_latest_json_output(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"]) == 0
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["open-latest", "--format", "json", "--out", str(out)]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.open_latest.v1"
    assert payload["ok"] is True
    assert payload["out"] == str(out.resolve())
    assert payload["latest_run"] == str(latest_dir)
    assert payload["paths"]["markdown"] == str(latest_dir / "agentledger-report.md")
    assert payload["paths"]["json"] == str(latest_dir / "agentledger-report.json")
    assert payload["paths"]["html"] == str(latest_dir / "agentledger-report.html")
    assert payload["paths"]["zip"] == str(latest_dir.with_suffix(".zip"))
    assert payload["missing_reports"] == []
    assert payload["errors"] == []


def test_open_latest_missing_pointer_prints_hint(tmp_path: Path, capsys) -> None:
    out = tmp_path / "ledger"
    out.mkdir()

    assert cli.main(["open-latest", "--out", str(out)]) == 2
    output = capsys.readouterr().out
    assert "No latest run pointer found:" in output
    assert "Run a capture first:" in output


def test_open_latest_json_missing_pointer(tmp_path: Path, capsys) -> None:
    out = tmp_path / "ledger"
    out.mkdir()

    assert cli.main(["open-latest", "--format", "json", "--out", str(out)]) == 2
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.open_latest.v1"
    assert payload["ok"] is False
    assert payload["out"] == str(out.resolve())
    assert payload["latest_run"] is None
    assert payload["missing_reports"] == []
    assert "No latest run pointer found:" in payload["errors"][0]
    assert "Run a capture first:" in payload["errors"][1]


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
    assert payload["schema_version"] == "agentledger.history.v1"
    assert payload["out"] == str(out.resolve())
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["command"] == "No command executed"
    assert payload["runs"][0]["exit_code"] is None
    assert payload["runs"][0]["changed_files"] == 0


def test_status_summarizes_latest_run_and_feedback(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert (
        cli.main(
            [
                "feedback",
                "--out",
                str(out),
                "--category",
                "friction",
                "--severity",
                "low",
                "--note",
                "Latest status should show feedback counts.",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert cli.main(["status", "--repo", str(repo), "--out", str(out), "--allow-warnings"]) == 0
    output = capsys.readouterr().out
    assert "AgentLedger status: warn" in output
    assert "Summary: 2 warnings; review before accepting." in output
    assert f"Latest run: {latest_dir}" in output
    assert "Feedback: 1 total entries across 1 runs; latest run has 1" in output
    assert f"Markdown report: {latest_dir / 'agentledger-report.md'}" in output
    assert "Read first:" in output
    assert f"- Markdown report: {latest_dir / 'agentledger-report.md'}" in output
    assert "- Status verdict: warn (2 warnings; review before accepting.)" in output
    assert "- Review warning rules before accepting the run." in output
    assert "- Keep raw .agentledger evidence, zip bundles, and transcripts private by default." in output
    assert "Use feedback-summary or feedback-export before sharing alpha notes." in output

    assert cli.main(["status", "--repo", str(repo), "--out", str(out), "--format", "json", "--allow-warnings"]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.status.v1"
    assert payload["status"] == "warn"
    assert payload["ok"] is False
    assert payload["repo"] == str(repo.resolve())
    assert payload["out"] == str(out.resolve())
    assert payload["latest_run"] == str(latest_dir)
    assert payload["paths"]["markdown"] == str(latest_dir / "agentledger-report.md")
    assert payload["paths"]["zip"] == str(latest_dir.with_suffix(".zip"))
    assert payload["missing_reports"] == []
    assert payload["check"]["schema_version"] == "agentledger.check.v1"
    assert payload["check"]["status"] == "warn"
    assert payload["feedback"]["total_entries"] == 1
    assert payload["feedback"]["latest_run_entries"] == 1
    assert payload["feedback"]["categories"] == {"friction": 1}
    assert payload["errors"] == []
    assert payload["status_exit_code"] == 0


def test_status_out_inherits_repo_warning_policy(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "cli-ledger"
    (repo / ".agentledger.toml").write_text(
        "\n".join(
            [
                'out = "ledger-from-config"',
                "check_allow_warnings = true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["status", "--repo", str(repo), "--out", str(out)]) == 0
    output = capsys.readouterr().out
    assert "AgentLedger status: warn" in output
    assert f"Latest run: {latest_dir}" in output

    assert cli.main(["status", "--repo", str(repo), "--out", str(out), "--format", "json"]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["status"] == "warn"
    assert payload["out"] == str(out.resolve())
    assert payload["status_exit_code"] == 0
    assert payload["check"]["policy"]["dirty"] == "warn"
    assert not (repo / "ledger-from-config").exists()


def test_status_missing_latest_json(tmp_path: Path, capsys) -> None:
    out = tmp_path / "ledger"
    out.mkdir()

    assert cli.main(["status", "--out", str(out), "--format", "json"]) == 2
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.status.v1"
    assert payload["ok"] is False
    assert payload["status"] == "unknown"
    assert payload["out"] == str(out.resolve())
    assert payload["latest_run"] is None
    assert payload["paths"] == {}
    assert payload["check"] is None
    assert payload["feedback"]["total_entries"] == 0
    assert "No latest run pointer found:" in payload["errors"][0]
    assert "Run a capture first:" in payload["errors"][1]
    assert payload["status_exit_code"] == 2


def test_alpha_guide_prints_first_run_loop(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(["alpha-guide", "--repo", str(repo), "--out", str(out)]) == 0

    output = capsys.readouterr().out
    assert "AgentLedger alpha guide" in output
    assert f"Repo: {repo.resolve()}" in output
    assert f"Output: {out.resolve()}" in output
    assert "Doctor: AgentLedger doctor: ready" in output
    assert "Optional integrations:" in output
    assert "Fast path:" in output
    assert "- Safe demo: python -m agentledger try" in output
    assert f"- First alpha pass: python -m agentledger alpha --repo {repo} --out {out}" in output
    assert f"- Inspect latest status: python -m agentledger status --out {out} --allow-warnings" in output
    assert "- Read status first, then open the Markdown report from open-latest." in output
    assert "Verify:" in output
    assert 'python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.27-alpha"' in output
    assert "python -m agentledger try" in output
    assert "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-source-check.ps1" in output
    assert "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-check.ps1" in output
    assert f"python -m agentledger alpha --repo {repo} --out {out}" in output
    assert f"python -m agentledger alpha-summary --out {out}" in output
    assert f"python -m agentledger pack-alpha --out {out}" in output
    assert f"python -m agentledger open-packet --out {out}" in output
    assert "Troubleshooting:" in output
    assert "install: when agentledger is not found" in output
    assert f"python -m agentledger doctor --repo {repo}" in output
    assert "command: when agentledger alpha, run, or the captured command fails" in output
    assert f"python -m agentledger status --out {out} --allow-warnings" in output
    assert f"packet: when the packet paths or share files are confusing, run python -m agentledger open-packet --out {out}" in output
    assert "reporting: when you need to open a feedback issue or send notes" in output
    assert f"- Output root: {out.resolve()}" in output
    assert f"- Latest pointer: {out.resolve() / 'latest.txt'}" in output
    assert "Send back:" in output
    assert "- The first command or message that felt confusing." in output
    assert "Keep private:" in output
    assert "- Do not commit .agentledger folders." in output

    assert cli.main(["alpha-guide", "--repo", str(repo), "--out", str(out), "--format", "json"]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.alpha_guide.v1"
    assert payload["ok"] is True
    assert payload["repo"] == str(repo.resolve())
    assert payload["out"] == str(out.resolve())
    assert payload["commands"]["setup"] == [
        'python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.27-alpha"',
        'python -m pip install -e ".[dev]"',
        "python -m agentledger --version",
        f"python -m agentledger doctor --repo {repo}",
    ]
    assert payload["commands"]["verify"] == [
        "python -m agentledger try",
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-source-check.ps1",
        "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-check.ps1",
    ]
    assert payload["commands"]["run"][0] == f"python -m agentledger alpha --repo {repo} --out {out}"
    assert payload["commands"]["feedback"][-2] == f"python -m agentledger pack-alpha --out {out}"
    assert payload["commands"]["feedback"][-1] == f"python -m agentledger open-packet --out {out}"
    assert [item["area"] for item in payload["troubleshooting"]] == [
        "install",
        "command",
        "packet",
        "reporting",
    ]
    assert f"python -m agentledger doctor --repo {repo}" in payload["troubleshooting"][0]["check"]
    assert f"python -m agentledger status --out {out} --allow-warnings" in payload["troubleshooting"][1]["check"]
    assert f"python -m agentledger open-packet --out {out}" == payload["troubleshooting"][2]["check"]
    assert f"python -m agentledger pack-alpha --out {out}" == payload["troubleshooting"][3]["check"]
    assert payload["evidence"]["latest_pointer"] == str(out.resolve() / "latest.txt")
    assert payload["doctor"]["schema_version"] == "agentledger.doctor.v1"
    assert payload["doctor"]["status"] == "ready"
    assert payload["doctor"]["required_ok"] is True
    assert payload["doctor"]["optional"]["total"] >= 1
    assert payload["doctor"]["required_blockers"] == []
    assert payload["fix_first"] == []
    assert payload["send_back"]
    assert payload["keep_private"]
    assert payload["known_limitations"]
    assert payload["errors"] == []


def test_alpha_guide_reports_blocked_doctor_with_fix_first(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "missing-repo"
    out = tmp_path / "ledger"

    assert cli.main(["alpha-guide", "--repo", str(repo), "--out", str(out)]) == 0

    output = capsys.readouterr().out
    assert "Doctor: AgentLedger doctor: blocked (required setup needs attention)" in output
    assert "Fast path:" in output
    assert "Fix first:" in output
    assert "- Fix required setup checks shown below, then run agentledger alpha again." in output
    assert "- Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo." in output
    assert f"python -m agentledger alpha --repo {repo} --out {out}" in output

    assert cli.main(["alpha-guide", "--repo", str(repo), "--out", str(out), "--format", "json"]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.alpha_guide.v1"
    assert payload["ok"] is True
    assert payload["doctor"]["status"] == "blocked"
    assert payload["doctor"]["required_ok"] is False
    assert payload["doctor"]["required_blockers"][0]["name"] == "target_git_repo"
    assert payload["fix_first"] == [
        "Fix required setup checks shown below, then run agentledger alpha again.",
        "Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo.",
        "After fixing required setup, run agentledger alpha again.",
    ]
    assert payload["errors"] == []


def test_alpha_command_runs_core_flow_and_writes_summary(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    summary_file = tmp_path / "alpha-summary.json"

    assert (
        cli.main(
            [
                "alpha",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--json-output",
                str(summary_file),
                "--format",
                "json",
                "--",
                sys.executable,
                "-c",
                "print('alpha cli ok')",
            ]
        )
        == 0
    )

    payload = _parse_json_output(capsys.readouterr().out)
    saved = json.loads(summary_file.read_text(encoding="utf-8"))
    assert saved == payload
    assert payload["schema_version"] == "agentledger.alpha_summary.v1"
    assert payload["ok"] is True
    assert payload["summary_file"] == str(summary_file.resolve())
    assert payload["repo"] == str(repo.resolve())
    assert payload["out"] == str(out.resolve())
    assert Path(payload["latest_run"]).exists()
    assert Path(payload["bundle"]).exists()
    assert Path(payload["report_paths"]["markdown"]).exists()
    assert Path(payload["report_paths"]["json"]).exists()
    assert Path(payload["report_paths"]["html"]).exists()
    assert payload["status"] in {"pass", "warn"}
    assert payload["status_exit_code"] == 0
    assert payload["errors"] == []
    assert payload["fix_first"] == []
    assert payload["next_actions"]

    assert cli.main(["alpha-summary", "--format", "json", str(summary_file)]) == 0
    summary_payload = _parse_json_output(capsys.readouterr().out)
    assert summary_payload == payload


def test_alpha_command_reports_unwritable_json_output_without_traceback(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    summary_file = tmp_path / "summary-dir"
    summary_file.mkdir()

    assert (
        cli.main(
            [
                "alpha",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--json-output",
                str(summary_file),
                "--format",
                "json",
                "--",
                sys.executable,
                "-c",
                "print('alpha cli ok')",
            ]
        )
        == 2
    )

    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert "Traceback" not in output
    assert summary_file.is_dir()
    assert payload["schema_version"] == "agentledger.alpha_summary.v1"
    assert payload["ok"] is False
    assert payload["summary_file"] == str(summary_file.resolve())
    assert payload["out"] == str(out.resolve())
    assert Path(payload["latest_run"]).exists()
    assert Path(payload["bundle"]).exists()
    assert any("Unable to write alpha summary" in error for error in payload["errors"])
    assert payload["status_exit_code"] == 2
    assert "Choose a writable alpha summary path" in payload["fix_first"][-1]
    assert "Choose a writable alpha summary path" in payload["next_actions"][-1]


def test_alpha_command_reports_failed_capture(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert (
        cli.main(
            [
                "alpha",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--format",
                "json",
                "--",
                sys.executable,
                "-c",
                "raise SystemExit(7)",
            ]
        )
        == 2
    )

    payload = _parse_json_output(capsys.readouterr().out)
    summary_file = out / "alpha-summary.json"
    assert json.loads(summary_file.read_text(encoding="utf-8")) == payload
    assert payload["schema_version"] == "agentledger.alpha_summary.v1"
    assert payload["ok"] is False
    assert payload["summary_file"] == str(summary_file.resolve())
    assert "Captured command exited 7." in payload["errors"]
    assert payload["status"] == "block"
    assert payload["status_exit_code"] == 2
    assert payload["fix_first"][0] == "Fix the captured command failure, then run agentledger alpha again."
    assert Path(payload["latest_run"]).exists()
    assert Path(payload["bundle"]).exists()


def test_alpha_command_reports_non_git_repo_without_traceback(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "not-a-repo"
    repo.mkdir()
    out = tmp_path / "ledger"

    assert cli.main(["alpha", "--repo", str(repo), "--out", str(out), "--format", "json"]) == 2

    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    summary_file = out / "alpha-summary.json"
    assert json.loads(summary_file.read_text(encoding="utf-8")) == payload
    assert "Traceback" not in output
    assert payload["schema_version"] == "agentledger.alpha_summary.v1"
    assert payload["ok"] is False
    assert payload["status"] == "block"
    assert payload["latest_run"] is None
    assert payload["bundle"] is None
    assert payload["report_paths"] == {}
    assert payload["summary_file"] == str(summary_file.resolve())
    assert any("Required doctor check failed: target_git_repo" in error for error in payload["errors"])
    assert payload["next_actions"] == [
        "Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo.",
        "After fixing required setup, run agentledger alpha again.",
    ]
    assert payload["fix_first"] == [
        "Fix required setup checks shown below, then run agentledger alpha again.",
        "Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo.",
        "After fixing required setup, run agentledger alpha again.",
    ]


def test_alpha_command_reports_missing_repo_without_traceback(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "missing-repo"
    out = tmp_path / "ledger"

    assert cli.main(["alpha", "--repo", str(repo), "--out", str(out), "--format", "json"]) == 2

    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    summary_file = out / "alpha-summary.json"
    assert json.loads(summary_file.read_text(encoding="utf-8")) == payload
    assert "Traceback" not in output
    assert payload["ok"] is False
    assert payload["status"] == "block"
    assert payload["latest_run"] is None
    assert payload["summary_file"] == str(summary_file.resolve())
    assert any("Required doctor check failed: target_git_repo" in error for error in payload["errors"])
    assert payload["next_actions"] == [
        "Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo.",
        "After fixing required setup, run agentledger alpha again.",
    ]
    assert payload["fix_first"] == [
        "Fix required setup checks shown below, then run agentledger alpha again.",
        "Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo.",
        "After fixing required setup, run agentledger alpha again.",
    ]


def test_alpha_command_config_error_writes_summary_with_out(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    config = tmp_path / "bad-agentledger.toml"
    config.write_text("unknown = true\n", encoding="utf-8")

    assert cli.main(["alpha", "--repo", str(repo), "--config", str(config), "--out", str(out), "--format", "json"]) == 2

    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    summary_file = out / "alpha-summary.json"
    assert json.loads(summary_file.read_text(encoding="utf-8")) == payload
    assert "Traceback" not in output
    assert payload["schema_version"] == "agentledger.alpha_summary.v1"
    assert payload["ok"] is False
    assert payload["summary_file"] == str(summary_file.resolve())
    assert payload["out"] == str(out.resolve())
    assert payload["latest_run"] is None
    assert payload["doctor"] == "AgentLedger doctor: not run (config error)"
    assert payload["status"] == "block"
    assert payload["status_summary"] == "Config error blocked alpha before setup checks."
    assert payload["status_exit_code"] == 2
    assert payload["report_paths"] == {}
    assert payload["next_actions"] == ["Fix the config error, then run agentledger alpha again."]
    assert payload["fix_first"] == [
        "Fix the config error shown below, then run agentledger alpha again.",
        "Fix the config error, then run agentledger alpha again.",
    ]
    assert "Config error:" in payload["errors"][0]


def test_alpha_command_config_error_honors_json_output(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    config = tmp_path / "bad-agentledger.toml"
    summary_file = tmp_path / "config-error-summary.json"
    config.write_text("unknown = true\n", encoding="utf-8")

    assert (
        cli.main(
            [
                "alpha",
                "--repo",
                str(repo),
                "--config",
                str(config),
                "--json-output",
                str(summary_file),
                "--format",
                "json",
            ]
        )
        == 2
    )

    payload = _parse_json_output(capsys.readouterr().out)
    assert json.loads(summary_file.read_text(encoding="utf-8")) == payload
    assert payload["ok"] is False
    assert payload["summary_file"] == str(summary_file.resolve())
    assert payload["out"] == str(Path(".agentledger").resolve())
    assert "Config error:" in payload["errors"][0]


def test_alpha_command_config_error_reports_unwritable_summary_without_traceback(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    config = tmp_path / "bad-agentledger.toml"
    summary_file = tmp_path / "config-error-summary-dir"
    config.write_text("unknown = true\n", encoding="utf-8")
    summary_file.mkdir()

    assert (
        cli.main(
            [
                "alpha",
                "--repo",
                str(repo),
                "--config",
                str(config),
                "--out",
                str(out),
                "--json-output",
                str(summary_file),
                "--format",
                "json",
            ]
        )
        == 2
    )

    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert "Traceback" not in output
    assert summary_file.is_dir()
    assert payload["schema_version"] == "agentledger.alpha_summary.v1"
    assert payload["ok"] is False
    assert payload["summary_file"] == str(summary_file.resolve())
    assert payload["out"] == str(out.resolve())
    assert "Config error:" in payload["errors"][0]
    assert any("Unable to write alpha summary" in error for error in payload["errors"])
    assert payload["status_exit_code"] == 2
    assert "Fix the config error shown below, then run agentledger alpha again." in payload["fix_first"]
    assert any("Choose a writable alpha summary path" in action for action in payload["fix_first"])
    assert "Choose a writable alpha summary path" in payload["next_actions"][-1]


def test_alpha_command_config_error_without_output_hint_is_full_json(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    config = tmp_path / "bad-agentledger.toml"
    config.write_text("unknown = true\n", encoding="utf-8")

    assert cli.main(["alpha", "--repo", str(repo), "--config", str(config), "--format", "json"]) == 2

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.alpha_summary.v1"
    assert payload["ok"] is False
    assert payload["summary_file"] is None
    assert payload["out"] is None
    assert payload["doctor"] == "AgentLedger doctor: not run (config error)"
    assert payload["status"] == "block"
    assert payload["errors"]
    assert payload["fix_first"][0] == "Fix the config error shown below, then run agentledger alpha again."


def test_alpha_summary_reads_direct_path(tmp_path: Path, capsys) -> None:
    summary_file = tmp_path / "alpha-summary.json"
    payload = _alpha_summary_payload(summary_file)
    summary_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    assert cli.main(["alpha-summary", str(summary_file)]) == 0

    output = capsys.readouterr().out
    assert "AgentLedger alpha summary: warn" in output
    assert "Summary: 2 warnings; review before accepting." in output
    assert f"Summary file: {summary_file.resolve()}" in output
    assert f"Latest run: {payload['latest_run']}" in output
    assert f"Bundle: {payload['bundle']}" in output
    assert "Feedback: 1 total entries across 1 runs; latest run has 1" in output
    assert "- Read the Markdown report before sharing evidence." in output
    assert "Send back:" in output
    assert "- This summary text, plus the first command or message that felt confusing." in output
    assert "- A reviewed feedback export or pack-alpha packet only if requested." in output
    assert "Keep private:" in output
    assert "- Do not send .agentledger folders, zip bundles, signing keys, or full reports unless requested." in output


def test_alpha_summary_json_output(tmp_path: Path, capsys) -> None:
    summary_file = tmp_path / "alpha-summary.json"
    payload = _alpha_summary_payload(summary_file)
    summary_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    assert cli.main(["alpha-summary", "--format", "json", str(summary_file)]) == 0

    result = _parse_json_output(capsys.readouterr().out)
    assert result["schema_version"] == "agentledger.alpha_summary.v1"
    assert result["summary_file"] == str(summary_file)
    assert result["status"] == "warn"
    assert result["feedback"]["total_entries"] == 1
    assert result["fix_first"] == []


def test_alpha_summary_adds_fix_first_for_legacy_blocked_summary(tmp_path: Path, capsys) -> None:
    summary_file = tmp_path / "alpha-summary.json"
    payload = _alpha_summary_payload(summary_file)
    payload["ok"] = False
    payload["status"] = "block"
    payload["status_summary"] = "Required setup is blocked; fix doctor errors before running alpha again."
    payload["errors"] = ["Required doctor check failed: target_git_repo - not a git repository"]
    payload["next_actions"] = [
        "Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo.",
        "After fixing required setup, run agentledger alpha again.",
    ]
    payload.pop("fix_first", None)
    summary_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    assert cli.main(["alpha-summary", str(summary_file)]) == 2

    output = capsys.readouterr().out
    assert "Fix first:" in output
    assert "- Fix required setup checks shown below, then run agentledger alpha again." in output
    assert "- Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo." in output

    assert cli.main(["alpha-summary", "--format", "json", str(summary_file)]) == 2
    result = _parse_json_output(capsys.readouterr().out)
    assert result["fix_first"] == [
        "Fix required setup checks shown below, then run agentledger alpha again.",
        "Fix target_git_repo: Run from a git checkout or pass --repo <path> to an existing git repo.",
        "After fixing required setup, run agentledger alpha again.",
    ]


def test_alpha_summary_defaults_to_output_directory(tmp_path: Path, capsys) -> None:
    out = tmp_path / "ledger"
    out.mkdir()
    summary_file = out / "alpha-summary.json"
    summary_file.write_text(json.dumps(_alpha_summary_payload(summary_file)) + "\n", encoding="utf-8")

    assert cli.main(["alpha-summary", "--out", str(out)]) == 0

    output = capsys.readouterr().out
    assert f"Summary file: {summary_file.resolve()}" in output


def test_alpha_summary_reports_missing_file(tmp_path: Path, capsys) -> None:
    missing = tmp_path / "missing-alpha-summary.json"

    assert cli.main(["alpha-summary", "--format", "json", str(missing)]) == 2

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.alpha_summary.v1"
    assert payload["ok"] is False
    assert payload["summary_file"] == str(missing.resolve())
    assert "Alpha summary file not found:" in payload["errors"][0]


def test_alpha_summary_rejects_invalid_schema(tmp_path: Path, capsys) -> None:
    summary_file = tmp_path / "alpha-summary.json"
    payload = _alpha_summary_payload(summary_file)
    payload["schema_version"] = "agentledger.old_alpha_summary.v1"
    summary_file.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    assert cli.main(["alpha-summary", str(summary_file)]) == 2

    output = capsys.readouterr().out
    assert "Expected schema_version agentledger.alpha_summary.v1" in output


def test_alpha_handoff_writes_reviewed_packet(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert (
        cli.main(
            [
                "feedback",
                "--out",
                str(out),
                "--category",
                "friction",
                "--severity",
                "low",
                "--note",
                "Handoff packet should mention feedback.",
            ]
        )
        == 0
    )
    capsys.readouterr()

    output_dir = tmp_path / "handoff"
    assert (
        cli.main(
            [
                "alpha-handoff",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--output-dir",
                str(output_dir),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = _parse_json_output(capsys.readouterr().out)
    markdown_path = output_dir / "agentledger-alpha-handoff.md"
    json_path = output_dir / "agentledger-alpha-handoff.json"
    assert json.loads(json_path.read_text(encoding="utf-8")) == payload
    assert set(output_dir.iterdir()) == {markdown_path, json_path}
    assert payload["schema_version"] == "agentledger.alpha_handoff.v1"
    assert payload["ok"] is True
    assert payload["status"] == "warn"
    assert payload["repo"] == str(repo.resolve())
    assert payload["out"] == str(out.resolve())
    assert payload["latest_run"] == str(latest_dir)
    assert payload["files"] == {
        "markdown": str(markdown_path),
        "json": str(json_path),
    }
    assert payload["sharing"]["review_required"] is True
    assert payload["sharing"]["share_safe"] is False
    assert payload["sharing"]["share_files"] == [str(markdown_path), str(json_path)]
    assert ".agentledger/ run folders" in payload["sharing"]["keep_private"]
    assert payload["review"]["schema_version"] == "agentledger.review.v1"
    assert payload["status_payload"]["schema_version"] == "agentledger.status.v1"
    assert payload["feedback_summary"]["schema_version"] == "agentledger.feedback_summary.v1"
    assert payload["feedback_summary"]["total_entries"] == 1
    assert payload["alpha_summary"]["available"] is False
    assert payload["public_summary"]["share_safe"] is False
    assert payload["public_summary"]["local_paths_omitted"] is True
    assert payload["public_summary"]["raw_evidence_copied"] is False
    assert "AgentLedger alpha check: warn." in payload["public_summary"]["text"]
    assert payload["public_summary"]["text_limit"] == 280
    assert len(payload["public_summary"]["text"]) <= payload["public_summary"]["text_limit"]
    assert "### AgentLedger alpha check" in payload["public_summary"]["markdown"]
    assert ".agentledger/ run folders" in payload["public_summary"]["do_not_share"]
    assert payload["share_safe"] is False
    assert payload["redactions"]["local_paths"] is False
    assert payload["handling"]["raw_evidence_copied"] is False
    assert payload["handling"]["local_paths_redacted"] is False
    assert payload["handling"]["copied_files"] == []
    assert payload["errors"] == []

    markdown = markdown_path.read_text(encoding="utf-8")
    assert "# AgentLedger Alpha Handoff" in markdown
    assert "## Sharing" in markdown
    assert "## Public Summary" in markdown
    assert "AgentLedger alpha check: warn." in markdown
    assert "### AgentLedger alpha check" in markdown
    assert "- Packet files to review/share:" in markdown
    assert "- Keep private:" in markdown
    assert "Handoff packet should mention feedback." in markdown
    assert "Raw evidence copied: no" in markdown
    assert str(latest_dir / "agentledger-report.md") in markdown


def test_alpha_handoff_share_safe_redacts_local_paths(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert (
        cli.main(
            [
                "feedback",
                "--out",
                str(out),
                "--note",
                "Tester saw C:\\Users\\ollet\\secret.txt and D:\\Temp\\alpha.log.",
            ]
        )
        == 0
    )
    capsys.readouterr()

    output_dir = tmp_path / "handoff"
    assert (
        cli.main(
            [
                "alpha-handoff",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--output-dir",
                str(output_dir),
                "--share-safe",
                "--format",
                "json",
            ]
        )
        == 0
    )

    stdout = capsys.readouterr().out
    payload = _parse_json_output(stdout)
    markdown_path = output_dir / "agentledger-alpha-handoff.md"
    json_path = output_dir / "agentledger-alpha-handoff.json"
    json_text = json_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    combined = "\n".join([stdout, json_text, markdown, json.dumps(payload, sort_keys=True)])

    assert payload["share_safe"] is True
    assert payload["redactions"]["local_paths"] is True
    assert payload["handling"]["local_paths_redacted"] is True
    assert payload["repo"] == "[repo]"
    assert payload["out"] == "[agentledger-output]"
    assert payload["latest_run"] == "[latest-run]"
    assert payload["output_dir"] == "[handoff-output]"
    assert payload["files"]["markdown"].startswith("[handoff-output]")
    assert payload["sharing"]["share_safe"] is True
    assert payload["sharing"]["share_files"][0].startswith("[handoff-output]")
    assert ".agentledger/ run folders" in payload["sharing"]["keep_private"]
    assert payload["public_summary"]["share_safe"] is True
    assert payload["public_summary"]["local_paths_omitted"] is True
    assert payload["public_summary"]["raw_evidence_copied"] is False
    assert "Raw evidence kept private." in payload["public_summary"]["text"]
    assert len(payload["public_summary"]["text"]) <= payload["public_summary"]["text_limit"]
    assert "Local paths omitted: yes" in payload["public_summary"]["markdown"]
    assert payload["review"]["paths"]["markdown"].startswith("[latest-run]")
    assert "[redacted-local-path]" in combined
    assert "## Public Summary" in markdown
    assert "[repo]" in markdown
    assert "[latest-run]" in markdown
    assert json.loads(json_text) == payload

    for path in (tmp_path, repo, out, latest_dir, output_dir):
        raw = str(path.resolve())
        assert raw not in combined
        assert raw.replace("\\", "/") not in combined
    for raw in ("C:\\Users", "C:/Users", "D:\\Temp", "D:/Temp", "C:\\\\Users", "D:\\\\Temp"):
        assert raw not in combined


def test_pack_alpha_writes_validated_share_safe_packet(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert (
        cli.main(
            [
                "feedback",
                "--out",
                str(out),
                "--note",
                "Please do not leak C:\\Users\\ollet\\alpha.txt or D:\\Temp\\handoff.log.",
            ]
        )
        == 0
    )
    capsys.readouterr()

    output_dir = tmp_path / "pack-alpha"
    assert (
        cli.main(
            [
                "pack-alpha",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--output-dir",
                str(output_dir),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = _parse_json_output(capsys.readouterr().out)
    issue_path = output_dir / "agentledger-alpha-issue.md"
    markdown_path = output_dir / "agentledger-alpha-handoff.md"
    json_path = output_dir / "agentledger-alpha-handoff.json"
    latest_packet_path = out / "latest-alpha-packet.json"
    issue_markdown = issue_path.read_text(encoding="utf-8")
    packet_json = json_path.read_text(encoding="utf-8")
    packet_markdown = markdown_path.read_text(encoding="utf-8")
    packet_text = "\n".join([issue_markdown, packet_json, packet_markdown])

    assert payload["schema_version"] == "agentledger.pack_alpha.v1"
    assert payload["ok"] is True
    assert payload["status"] == "warn"
    assert payload["out"] == str(out.resolve())
    assert payload["latest_packet"] == str(latest_packet_path.resolve())
    assert payload["pointer_errors"] == []
    assert payload["files"] == {"issue": str(issue_path), "markdown": str(markdown_path), "json": str(json_path)}
    assert payload["sharing"]["review_required"] is True
    assert payload["sharing"]["share_safe"] is True
    assert payload["sharing"]["share_files"] == [str(issue_path), str(markdown_path), str(json_path)]
    assert "Command used" in payload["sharing"]["feedback_fields"][0]
    assert "Platform, shell, Python version" in payload["sharing"]["feedback_fields"][1]
    assert "zip evidence bundles" in payload["sharing"]["keep_private"]
    assert payload["raw_evidence_copied"] is False
    assert payload["handoff_exit_code"] == 0
    assert payload["validation"]["ok"] is True
    assert payload["validation"]["checked_files"] == {
        "issue": str(issue_path),
        "markdown": str(markdown_path),
        "json": str(json_path),
    }
    assert payload["validation"]["errors"] == []
    assert payload["handoff"]["schema_version"] == "agentledger.alpha_handoff.v1"
    assert payload["handoff"]["share_safe"] is True
    assert payload["handoff"]["handling"]["local_paths_redacted"] is True
    assert payload["public_summary"] == payload["handoff"]["public_summary"]
    assert payload["public_summary"]["share_safe"] is True
    assert "AgentLedger alpha check: warn." in payload["public_summary"]["text"]
    assert json.loads(latest_packet_path.read_text(encoding="utf-8")) == payload
    assert "### AgentLedger alpha check" in issue_markdown
    assert "## Feedback checklist" in issue_markdown
    assert "Platform, shell, Python version, and AgentLedger version." in issue_markdown
    assert "## Privacy check" in issue_markdown
    assert "Do not attach raw .agentledger folders" in issue_markdown
    assert "Reviewed public summary only." in issue_markdown
    assert json.loads(packet_json) == payload["handoff"]
    assert "[latest-run]" in packet_markdown
    assert "## Public Summary" in packet_markdown
    assert "[redacted-local-path]" in packet_text

    for path in (repo, out, latest_dir, output_dir):
        raw = str(path.resolve())
        assert raw not in packet_text
        assert raw.replace("\\", "/") not in packet_text
    for raw in ("C:\\Users", "C:/Users", "D:\\Temp", "D:/Temp", "C:\\\\Users", "D:\\\\Temp"):
        assert raw not in packet_text


def test_pack_alpha_defaults_to_isolated_temp_packet_dir(tmp_path: Path, capsys, monkeypatch) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    capsys.readouterr()
    default_output_dir = tmp_path / "agentledger-alpha-packet-default"

    def fake_mkdtemp(prefix: str) -> str:
        assert prefix == "agentledger-alpha-packet-"
        return str(default_output_dir)

    monkeypatch.setattr(cli.tempfile, "mkdtemp", fake_mkdtemp)

    assert (
        cli.main(
            [
                "pack-alpha",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--format",
                "json",
            ]
        )
        == 0
    )

    payload = _parse_json_output(capsys.readouterr().out)
    issue_path = default_output_dir / "agentledger-alpha-issue.md"
    markdown_path = default_output_dir / "agentledger-alpha-handoff.md"
    json_path = default_output_dir / "agentledger-alpha-handoff.json"

    assert payload["schema_version"] == "agentledger.pack_alpha.v1"
    assert payload["ok"] is True
    assert payload["output_dir"] == str(default_output_dir.resolve())
    assert payload["latest_packet"] == str((out / "latest-alpha-packet.json").resolve())
    assert payload["pointer_errors"] == []
    assert payload["files"] == {"issue": str(issue_path), "markdown": str(markdown_path), "json": str(json_path)}
    assert issue_path.exists()
    assert markdown_path.exists()
    assert json_path.exists()
    assert payload["validation"]["ok"] is True
    assert payload["raw_evidence_copied"] is False


def test_open_packet_prints_latest_alpha_packet_paths(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    output_dir = tmp_path / "pack-alpha"

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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        cli.main(
            [
                "pack-alpha",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert cli.main(["open-packet", "--repo", str(repo), "--out", str(out)]) == 0
    output = capsys.readouterr().out
    assert f"Latest alpha packet: {output_dir.resolve()}" in output
    assert f"Pointer: {(out / 'latest-alpha-packet.json').resolve()}" in output
    assert f"Issue/comment draft: {output_dir / 'agentledger-alpha-issue.md'}" in output
    assert f"Markdown to share: {output_dir / 'agentledger-alpha-handoff.md'}" in output
    assert f"JSON to share: {output_dir / 'agentledger-alpha-handoff.json'}" in output
    assert "Raw evidence copied: no" in output


def test_open_packet_json_output(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    output_dir = tmp_path / "pack-alpha"

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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert (
        cli.main(
            [
                "pack-alpha",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--output-dir",
                str(output_dir),
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert cli.main(["open-packet", "--format", "json", "--repo", str(repo), "--out", str(out)]) == 0
    payload = _parse_json_output(capsys.readouterr().out)

    assert payload["schema_version"] == "agentledger.open_packet.v1"
    assert payload["ok"] is True
    assert payload["out"] == str(out.resolve())
    assert payload["latest_packet"] == str((out / "latest-alpha-packet.json").resolve())
    assert payload["output_dir"] == str(output_dir.resolve())
    assert payload["files"]["issue"] == str(output_dir / "agentledger-alpha-issue.md")
    assert payload["missing_files"] == []
    assert payload["raw_evidence_copied"] is False
    assert payload["packet"]["schema_version"] == "agentledger.pack_alpha.v1"
    assert payload["errors"] == []


def test_open_packet_missing_pointer_prints_hint(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    out.mkdir()

    assert cli.main(["open-packet", "--format", "json", "--repo", str(repo), "--out", str(out)]) == 2
    payload = _parse_json_output(capsys.readouterr().out)

    assert payload["schema_version"] == "agentledger.open_packet.v1"
    assert payload["ok"] is False
    assert payload["latest_packet"] == str((out / "latest-alpha-packet.json").resolve())
    assert payload["packet"] is None
    assert "No latest alpha packet pointer found:" in payload["errors"][0]
    assert "python -m agentledger pack-alpha" in payload["errors"][1]


def test_pack_alpha_fails_when_packet_validation_finds_local_path(tmp_path: Path, capsys, monkeypatch) -> None:
    repo = make_repo(tmp_path)
    output_dir = tmp_path / "pack-alpha"

    def fake_handoff(args) -> int:
        output = Path(args.output_dir)
        output.mkdir(parents=True)
        leaked_path = str(repo.resolve())
        (output / "agentledger-alpha-handoff.md").write_text(f"# Leak\n\n{leaked_path}\n", encoding="utf-8")
        packet = {
            "schema_version": "agentledger.alpha_handoff.v1",
            "ok": True,
            "status": "pass",
            "summary": "Fake handoff.",
            "share_safe": True,
            "errors": [],
        }
        (output / "agentledger-alpha-handoff.json").write_text(json.dumps(packet), encoding="utf-8")
        print(json.dumps(packet))
        return 0

    monkeypatch.setattr(cli, "_handle_alpha_handoff", fake_handoff)

    assert (
        cli.main(
            [
                "pack-alpha",
                "--repo",
                str(repo),
                "--out",
                str(tmp_path / "ledger"),
                "--output-dir",
                str(output_dir),
                "--format",
                "json",
            ]
        )
        == 2
    )

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.pack_alpha.v1"
    assert payload["ok"] is False
    assert payload["handoff_exit_code"] == 0
    assert payload["validation"]["ok"] is False
    assert any("Packet leaks local repo path" in error for error in payload["validation"]["errors"])


def test_alpha_handoff_strict_returns_nonzero_for_warning_status(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    capsys.readouterr()

    output_dir = tmp_path / "strict-handoff"
    assert (
        cli.main(
            [
                "alpha-handoff",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--output-dir",
                str(output_dir),
                "--strict",
                "--format",
                "json",
            ]
        )
        == 2
    )

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.alpha_handoff.v1"
    assert payload["ok"] is False
    assert payload["status"] == "warn"
    assert payload["status_payload"]["status_exit_code"] == 1
    assert payload["review"]["review_exit_code"] == 1
    assert any("Resolve warnings" in action for action in payload["next_actions"])
    assert (output_dir / "agentledger-alpha-handoff.md").exists()
    assert (output_dir / "agentledger-alpha-handoff.json").exists()


def test_alpha_handoff_missing_latest_json(tmp_path: Path, capsys) -> None:
    out = tmp_path / "ledger"
    out.mkdir()
    output_dir = tmp_path / "handoff"

    assert (
        cli.main(
            [
                "alpha-handoff",
                "--out",
                str(out),
                "--output-dir",
                str(output_dir),
                "--format",
                "json",
            ]
        )
        == 2
    )

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.alpha_handoff.v1"
    assert payload["ok"] is False
    assert payload["files"] == {}
    assert "No latest run pointer found:" in payload["errors"][0]
    assert not output_dir.exists()


def test_feedback_records_and_lists_latest_run(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    secret = "feedback-password-12345"

    assert cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"]) == 0
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert (
        cli.main(
            [
                "feedback",
                "--out",
                str(out),
                "--format",
                "json",
                "--category",
                "docs",
                "--severity",
                "high",
                "--source",
                "alpha-tester",
                "--note",
                f"Could not find the HTML report. password={secret}",
            ]
        )
        == 0
    )
    payload = _parse_json_output(capsys.readouterr().out)
    feedback_path = latest_dir / "alpha-feedback.jsonl"
    assert payload["schema_version"] == "agentledger.feedback.v1"
    assert payload["ok"] is True
    assert payload["action"] == "record"
    assert payload["run_dir"] == str(latest_dir)
    assert payload["feedback_file"] == str(feedback_path)
    assert payload["errors"] == []
    assert payload["entry"]["category"] == "docs"
    assert payload["entry"]["severity"] == "high"
    assert payload["entry"]["source"] == "alpha-tester"
    assert payload["entry"]["redacted"] is True
    assert secret not in payload["entry"]["note"]
    assert "password=[REDACTED]" in payload["entry"]["note"]

    entries = [json.loads(line) for line in feedback_path.read_text(encoding="utf-8").splitlines()]
    assert entries == [payload["entry"]]

    assert cli.main(["feedback", "--out", str(out), "--list"]) == 0
    output = capsys.readouterr().out
    assert f"AgentLedger feedback for {latest_dir}:" in output
    assert "high | docs | alpha-tester:" in output
    assert secret not in output
    assert "password=[REDACTED]" in output

    assert cli.main(["feedback", str(latest_dir), "--list", "--format", "json"]) == 0
    listed = _parse_json_output(capsys.readouterr().out)
    assert listed["action"] == "list"
    assert listed["entry"] is None
    assert listed["entries"] == entries


def test_feedback_missing_latest_prints_hint(tmp_path: Path, capsys) -> None:
    out = tmp_path / "ledger"
    out.mkdir()

    assert cli.main(["feedback", "--out", str(out), "--note", "Could not find the latest run.", "--format", "json"]) == 2

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.feedback.v1"
    assert payload["ok"] is False
    assert payload["action"] == "record"
    assert payload["run_dir"] is None
    assert payload["feedback_file"] is None
    assert "No latest run pointer found:" in payload["errors"][0]
    assert "Run a capture first:" in payload["errors"][1]


def test_feedback_summary_collects_filters_and_limits_entries(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"]) == 0
    first = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()
    assert (
        cli.main(
            [
                "feedback",
                str(first),
                "--category",
                "bug",
                "--severity",
                "high",
                "--source",
                "tester-a",
                "--note",
                "Bundle path was hard to spot.",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"]) == 0
    second = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()
    assert (
        cli.main(
            [
                "feedback",
                str(second),
                "--category",
                "docs",
                "--severity",
                "low",
                "--source",
                "tester-b",
                "--note",
                "The review command was clear.",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert cli.main(["feedback-summary", "--out", str(out), "--format", "json"]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.feedback_summary.v1"
    assert payload["ok"] is True
    assert payload["out"] == str(out.resolve())
    assert payload["total_entries"] == 2
    assert payload["returned_entries"] == 2
    assert payload["run_count"] == 2
    assert payload["runs_with_feedback"] == 2
    assert payload["categories"] == {"bug": 1, "docs": 1}
    assert payload["severities"] == {"high": 1, "low": 1}
    assert {entry["note"] for entry in payload["entries"]} == {
        "Bundle path was hard to spot.",
        "The review command was clear.",
    }
    assert {item["entry_count"] for item in payload["runs"]} == {1}

    assert cli.main(["feedback-summary", "--out", str(out), "--category", "bug", "--format", "json"]) == 0
    filtered = _parse_json_output(capsys.readouterr().out)
    assert filtered["filters"]["category"] == "bug"
    assert filtered["total_entries"] == 1
    assert filtered["categories"] == {"bug": 1}
    assert filtered["entries"][0]["source"] == "tester-a"

    assert cli.main(["feedback-summary", "--out", str(out), "--limit", "1", "--format", "json"]) == 0
    limited = _parse_json_output(capsys.readouterr().out)
    assert limited["total_entries"] == 2
    assert limited["returned_entries"] == 1
    assert len(limited["entries"]) == 1

    assert cli.main(["feedback-summary", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "AgentLedger feedback summary in" in text
    assert "Entries: 2 shown / 2 total across 2 runs" in text
    assert "Categories: bug=1, docs=1" in text
    assert "Recent feedback:" in text


def test_feedback_export_writes_reviewed_files_without_local_paths(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"

    assert cli.main(["snapshot", "--repo", str(repo), "--out", str(out), "--no-repomori", "--no-tokometer"]) == 0
    latest_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert (
        cli.main(
            [
                "feedback",
                "--out",
                str(out),
                "--category",
                "docs",
                "--severity",
                "low",
                "--source",
                "tester-a",
                "--note",
                "Review flow was clear.",
            ]
        )
        == 0
    )
    capsys.readouterr()

    markdown_export = tmp_path / "agentledger-feedback.md"
    assert cli.main(["feedback-export", "--out", str(out), "--output", str(markdown_export)]) == 0
    output = capsys.readouterr().out
    assert f"Feedback export written: {markdown_export.resolve()}" in output
    assert "Entries: 1 shown / 1 total across 1 runs" in output

    markdown = markdown_export.read_text(encoding="utf-8")
    assert "# AgentLedger Feedback Export" in markdown
    assert "Review flow was clear." in markdown
    assert latest_dir.name in markdown
    assert str(latest_dir) not in markdown
    assert "alpha-feedback.jsonl" not in markdown

    json_export = tmp_path / "agentledger-feedback.json"
    assert (
        cli.main(
            [
                "feedback-export",
                "--out",
                str(out),
                "--output",
                str(json_export),
                "--output-format",
                "json",
                "--format",
                "json",
            ]
        )
        == 0
    )
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.feedback_export_result.v1"
    assert payload["ok"] is True
    assert payload["out"] == str(out.resolve())
    assert payload["output"] == str(json_export.resolve())
    assert payload["output_format"] == "json"
    assert payload["export_schema_version"] == "agentledger.feedback_export.v1"
    assert payload["total_entries"] == 1
    assert payload["returned_entries"] == 1
    assert payload["errors"] == []

    exported = json.loads(json_export.read_text(encoding="utf-8"))
    assert exported["schema_version"] == "agentledger.feedback_export.v1"
    assert exported["review"]["omits_local_paths"] is True
    assert exported["entries"][0]["note"] == "Review flow was clear."
    assert "run_dir" not in exported["entries"][0]
    assert "feedback_file" not in exported["entries"][0]
    assert "run_dir" not in exported["runs"][0]
    assert "feedback_file" not in exported["runs"][0]


def test_feedback_summary_missing_output_json(tmp_path: Path, capsys) -> None:
    out = tmp_path / "missing-ledger"

    assert cli.main(["feedback-summary", "--out", str(out), "--format", "json"]) == 2

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.feedback_summary.v1"
    assert payload["ok"] is False
    assert payload["out"] == str(out.resolve())
    assert payload["entries"] == []
    assert "No AgentLedger output directory found:" in payload["errors"][0]


def test_review_latest_summarizes_check_status(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["review", "--out", str(out)]) == 1
    output = capsys.readouterr().out
    assert "AgentLedger review: warn" in output
    assert "Summary: 2 warnings; review before accepting." in output
    assert f"Run: {run_dir}" in output
    assert f"Markdown report: {run_dir / 'agentledger-report.md'}" in output
    assert f"JSON report: {run_dir / 'agentledger-report.json'}" in output
    assert f"HTML report: {run_dir / 'agentledger-report.html'}" in output
    assert f"Zip bundle: {run_dir}.zip" in output
    assert "Recent runs:" in output
    assert f"* {run_dir.name} | exit=0 | changed=1" in output
    assert "Previous comparison:" not in output
    assert "Warnings:" in output
    assert "- test_evidence: Command was not recognized as a test or verification command." in output
    assert "- repo_state: Repository had 1 changed file after the run." in output
    assert "Next:" in output
    assert "- Do not commit .agentledger folders or zip bundles." in output

    assert cli.main(["review", "--out", str(out), "--allow-warnings"]) == 0
    capsys.readouterr()
    assert cli.main(["review", "--out", str(out), "--allow-warnings", "--history-limit", "0"]) == 0
    output = capsys.readouterr().out
    assert "Recent runs:" not in output

    review_markdown = tmp_path / "handoff" / "agentledger-review.md"
    assert (
        cli.main(
            [
                "review",
                "--format",
                "markdown",
                "--out",
                str(out),
                "--allow-warnings",
                "--output",
                str(review_markdown),
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    assert review_markdown.read_text(encoding="utf-8") == output
    assert output.startswith("# AgentLedger Review\n")
    assert "- Status: warn" in output
    assert "## Evidence" in output
    assert f"- Markdown report: `{run_dir / 'agentledger-report.md'}`" in output
    assert "## Recent Runs" in output
    assert "## Warnings" in output
    assert "- Do not commit .agentledger folders or zip bundles." in output


def test_review_json_output(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-m",
                "pytest",
                "--version",
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["review", "--format", "json", "--out", str(out)]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.review.v1"
    assert payload["status"] == "pass"
    assert payload["ok"] is True
    assert payload["summary"] == "All 9 checks passed."
    assert payload["run_dir"] == str(run_dir.resolve())
    assert payload["paths"]["markdown"] == str(run_dir / "agentledger-report.md")
    assert payload["paths"]["zip"] == f"{run_dir}.zip"
    assert payload["history"]["out"] == str(out.resolve())
    assert payload["history"]["limit"] == 3
    assert payload["history"]["errors"] == []
    assert len(payload["history"]["runs"]) == 1
    assert payload["history"]["runs"][0]["run_dir"] == str(run_dir)
    assert payload["history"]["runs"][0]["current"] is True
    assert payload["history"]["runs"][0]["test_framework"] == "pytest"
    assert payload["comparison"]["available"] is False
    assert payload["comparison"]["current_run"] == str(run_dir.resolve())
    assert payload["comparison"]["previous_run"] is None
    assert payload["comparison"]["compare"] is None
    assert payload["comparison"]["errors"] == []
    assert payload["check"]["schema_version"] == "agentledger.check.v1"
    assert payload["check"]["command"].startswith(str(sys.executable))
    assert payload["command_exit_code"] == 0
    assert payload["output"] is None
    assert payload["review_exit_code"] == 0

    review_json = tmp_path / "handoff" / "agentledger-review.json"
    assert cli.main(["review", "--format", "json", "--out", str(out), "--output", str(review_json)]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["output"] == str(review_json.resolve())
    assert json.loads(review_json.read_text(encoding="utf-8")) == payload


def test_review_compares_latest_with_previous_run(tmp_path: Path, capsys) -> None:
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
                sys.executable,
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('new'); Path('README.md').write_text('hello two')",
            ]
        )
        == 0
    )
    second = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["review", "--out", str(out), "--allow-warnings"]) == 0
    output = capsys.readouterr().out
    assert "Previous comparison:" in output
    assert f"Previous run: {first.resolve()}" in output
    assert "Changed files: 1 -> 2 (+1)" in output
    assert "Exit code: 0 -> 0 (unchanged)" in output
    assert "Test framework: n/a -> n/a" in output

    assert cli.main(["review", "--format", "json", "--out", str(out), "--allow-warnings"]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["comparison"]["available"] is True
    assert payload["comparison"]["previous_run"] == str(first.resolve())
    assert payload["comparison"]["current_run"] == str(second.resolve())
    assert payload["comparison"]["errors"] == []
    assert payload["comparison"]["compare"]["schema_version"] == "agentledger.compare.v1"
    assert payload["comparison"]["compare"]["changed_files"] == {
        "old": 1,
        "new": 2,
        "delta": 1,
        "delta_text": "+1",
    }
    assert payload["comparison"]["compare"]["exit_code"]["trend"] == "unchanged"


def test_review_rejects_negative_history_limit(tmp_path: Path, capsys) -> None:
    out = tmp_path / "ledger"

    assert cli.main(["review", "--out", str(out), "--history-limit", "-1"]) == 2

    output = capsys.readouterr().out
    assert "--history-limit must be zero or greater." in output


def test_review_missing_latest_prints_hint(tmp_path: Path, capsys) -> None:
    out = tmp_path / "ledger"
    out.mkdir()

    assert cli.main(["review", "--out", str(out)]) == 2
    output = capsys.readouterr().out
    assert "No latest run pointer found:" in output
    assert "Run a capture first:" in output


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


def test_check_passes_test_run(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-m",
                "pytest",
                "--version",
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["check", str(run_dir)]) == 0
    output = capsys.readouterr().out
    assert "AgentLedger check: pass" in output
    assert "[PASS] command_exit: Captured command exited 0." in output
    assert "[PASS] test_evidence: Verification command detected: pytest." in output

    assert cli.main(["check", "--format", "json", str(run_dir)]) == 0
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["ok"] is True
    assert payload["summary"] == "All 9 checks passed."
    assert payload["rule_counts"] == {"pass": 9, "warn": 0, "block": 0, "total": 9}
    assert payload["warning_rules"] == []
    assert payload["blocking_rules"] == []


def test_check_warns_for_non_test_dirty_run(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["check", "--format", "json", str(run_dir)]) == 1
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["status"] == "warn"
    assert payload["ok"] is False
    assert payload["summary"] == "2 warnings; review before accepting."
    assert payload["rule_counts"] == {"pass": 7, "warn": 2, "block": 0, "total": 9}
    assert [rule["id"] for rule in payload["warning_rules"]] == ["test_evidence", "repo_state"]
    assert payload["blocking_rules"] == []
    assert _rule_by_id(payload, "command_exit")["status"] == "pass"
    assert _rule_by_id(payload, "test_evidence")["status"] == "warn"
    assert _rule_by_id(payload, "repo_state")["status"] == "warn"

    assert cli.main(["check", str(run_dir), "--allow-warnings"]) == 0


def test_check_blocks_failed_command(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "import sys; sys.exit(7)",
            ]
        )
        == 7
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["check", "--format", "json", str(run_dir)]) == 2
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["status"] == "block"
    assert payload["ok"] is False
    assert payload["summary"] == "1 blocker; do not accept until resolved."
    assert payload["rule_counts"]["block"] == 1
    assert [rule["id"] for rule in payload["blocking_rules"]] == ["command_exit"]
    assert payload["exit_code"] == 7
    assert _rule_by_id(payload, "command_exit")["status"] == "block"


def test_check_config_requires_tests(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "print('not a test')",
            ]
        )
        == 0
    )
    (repo / ".agentledger.toml").write_text("check_require_tests = true\n", encoding="utf-8")
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["check", "--format", "json", str(run_dir)]) == 2
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["status"] == "block"
    assert payload["policy"]["require_tests"] is True
    assert _rule_by_id(payload, "test_evidence")["status"] == "block"


def test_check_config_can_allow_dirty_and_warnings(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    (repo / ".agentledger.toml").write_text(
        "\n".join(
            [
                'check_dirty = "pass"',
                "check_allow_warnings = true",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["check", "--format", "json", str(run_dir)]) == 0
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["status"] == "warn"
    assert payload["policy"]["dirty"] == "pass"
    assert _rule_by_id(payload, "repo_state")["status"] == "pass"
    assert _rule_by_id(payload, "test_evidence")["status"] == "warn"


def test_check_config_max_changed_files_blocks(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-c",
                "from pathlib import Path; Path('note.txt').write_text('hello')",
            ]
        )
        == 0
    )
    (repo / ".agentledger.toml").write_text(
        'check_dirty = "pass"\ncheck_max_changed_files = 0\n',
        encoding="utf-8",
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["check", "--format", "json", str(run_dir)]) == 2
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["status"] == "block"
    assert payload["policy"]["max_changed_files"] == 0
    assert _rule_by_id(payload, "repo_state")["status"] == "block"


def test_check_config_errors_are_clear(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-m",
                "pytest",
                "--version",
            ]
        )
        == 0
    )
    (repo / ".agentledger.toml").write_text('check_dirty = "loud"\n', encoding="utf-8")
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

    assert cli.main(["check", str(run_dir)]) == 2
    output = capsys.readouterr().out
    assert "Config error:" in output
    assert "check_dirty must be 'pass', 'warn', or 'block'" in output


def test_check_warns_for_failed_optional_artifact(tmp_path: Path, capsys) -> None:
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
                sys.executable,
                "-m",
                "pytest",
                "--version",
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    report_path = run_dir / "agentledger-report.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    payload["artifacts"].append(
        {
            "name": "repomori_snapshot_before",
            "ok": False,
            "command": [],
            "output_path": str(run_dir / "repomori-before.json"),
            "summary": "RepoMori snapshot failed or RepoMori is not installed.",
            "exit_code": 1,
        }
    )
    report_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    capsys.readouterr()

    assert cli.main(["check", "--format", "json", str(run_dir)]) == 1
    output = capsys.readouterr().out
    result = _parse_json_output(output)
    assert result["status"] == "warn"
    assert _rule_by_id(result, "command_exit")["status"] == "pass"
    assert _rule_by_id(result, "artifact_status")["status"] == "warn"


def test_check_blocks_missing_report(tmp_path: Path, capsys) -> None:
    run_dir = tmp_path / "missing-report"
    run_dir.mkdir()

    assert cli.main(["check", "--format", "json", str(run_dir)]) == 2
    output = capsys.readouterr().out
    payload = _parse_json_output(output)
    assert payload["status"] == "block"
    assert payload["ok"] is False
    assert payload["rule_counts"] == {"pass": 0, "warn": 0, "block": 1, "total": 1}
    assert [rule["id"] for rule in payload["blocking_rules"]] == ["report_loaded"]
    assert _rule_by_id(payload, "report_loaded")["status"] == "block"


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
    manifest_member, manifest = _bundle_manifest(bundle)
    manifest_paths = {item["path"] for item in manifest["files"]}

    assert manifest_member == f"{run_dir.name}/{BUNDLE_MANIFEST_NAME}"
    assert manifest["schema_version"] == BUNDLE_MANIFEST_SCHEMA
    assert manifest["digest_algorithm"] == "sha256"
    assert manifest["bundle_root"] == run_dir.name
    assert manifest["run_id"] == run_dir.name
    assert manifest["file_count"] == len(manifest["files"])
    assert f"{run_dir.name}/agentledger-report.json" in manifest_paths
    assert all(item["sha256"] for item in manifest["files"])

    assert cli.main(["verify-bundle", str(bundle)]) == 0
    output = capsys.readouterr().out
    assert f"Bundle OK: {bundle}" in output
    assert f"Manifest: {manifest_member}" in output
    assert f"Files checked: {manifest['file_count']}" in output
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


def test_verify_bundle_json_output(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    key_file = tmp_path / "agentledger-signing-key.txt"
    key_file.write_text("shared-test-key\n", encoding="utf-8")

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
    manifest_member, manifest = _bundle_manifest(bundle)
    capsys.readouterr()

    assert cli.main(["verify-bundle", str(bundle), "--format", "json"]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.verify_bundle.v1"
    assert payload["ok"] is True
    assert payload["bundle"] == str(bundle)
    assert payload["run_id"] == run_dir.name
    assert payload["manifest"]["member"] == manifest_member
    assert payload["manifest"]["file_count"] == manifest["file_count"]
    assert payload["signature"]["status"] == "not_present"
    assert payload["signature"]["verified"] is False
    assert payload["reports"]["json"].endswith("agentledger-report.json")
    assert payload["reports"]["markdown"].endswith("agentledger-report.md")
    assert payload["reports"]["html"].endswith("agentledger-report.html")
    assert payload["artifacts"]["warn"] == 0
    assert payload["errors"] == []

    assert cli.main(["sign-bundle", str(bundle), "--key-file", str(key_file)]) == 0
    signature_member, _signature = _bundle_signature(bundle)
    capsys.readouterr()

    assert cli.main(["verify-bundle", str(bundle), "--format", "json", "--signature-key-file", str(key_file)]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["signature"]["member"] == signature_member
    assert payload["signature"]["status"] == "verified"
    assert payload["signature"]["verified"] is True


def test_inspect_bundle_json_output(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    key_file = tmp_path / "agentledger-signing-key.txt"
    key_file.write_text("shared-test-key-for-inspect-bundle\n", encoding="utf-8")

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
                sys.executable,
                "-m",
                "pytest",
                "--version",
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    bundle = run_dir.with_suffix(".zip")
    manifest_member, manifest = _bundle_manifest(bundle)
    capsys.readouterr()

    assert cli.main(["sign-bundle", str(bundle), "--key-file", str(key_file)]) == 0
    signature_member, _signature = _bundle_signature(bundle)
    capsys.readouterr()

    assert cli.main(["inspect-bundle", "--format", "json", str(bundle)]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.inspect_bundle.v1"
    assert payload["ok"] is True
    assert payload["bundle"] == str(bundle.resolve())
    assert payload["readable"] is True
    assert payload["manifest"]["member"] == manifest_member
    assert payload["manifest"]["valid"] is True
    assert payload["manifest"]["file_count"] == manifest["file_count"]
    assert payload["signature"]["member"] == signature_member
    assert payload["signature"]["status"] == "present_unverified"
    assert payload["signature"]["verified"] is False
    assert "signature" not in payload["signature"]
    assert payload["reports"]["json"].endswith("agentledger-report.json")
    assert payload["reports"]["markdown"].endswith("agentledger-report.md")
    assert payload["reports"]["html"].endswith("agentledger-report.html")
    assert payload["reports"]["missing"] == []
    assert payload["review"]["status"] == "pass"
    assert payload["review"]["exit_code"] == 0
    assert payload["review"]["test_framework"] == "pytest"
    assert payload["review"]["artifacts"] == {"ok": 0, "warn": 0}
    assert payload["errors"] == []
    assert any("--signature-key-file" in action for action in payload["next_actions"])


def test_inspect_bundle_reports_missing_json_report(tmp_path: Path, capsys) -> None:
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
    broken = out / "missing-report.zip"
    with ZipFile(bundle) as src, ZipFile(broken, "w") as dst:
        for name in src.namelist():
            if name.endswith("agentledger-report.json"):
                continue
            dst.writestr(name, src.read(name))
    capsys.readouterr()

    assert cli.main(["inspect-bundle", "--format", "json", str(broken)]) == 2
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.inspect_bundle.v1"
    assert payload["ok"] is False
    assert payload["readable"] is True
    assert payload["review"]["status"] == "block"
    assert any("Missing JSON report" in error for error in payload["errors"])
    assert "agentledger-report.json" not in str(payload["review"]["command"])


def test_inspect_bundle_reports_signature_digest_mismatch(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    key_file = tmp_path / "agentledger-signing-key.txt"
    key_file.write_text("shared-test-key-for-digest-mismatch\n", encoding="utf-8")

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
                sys.executable,
                "-m",
                "pytest",
                "--version",
            ]
        )
        == 0
    )
    run_dir = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    bundle = run_dir.with_suffix(".zip")
    assert cli.main(["sign-bundle", str(bundle), "--key-file", str(key_file)]) == 0
    signature_member, signature = _bundle_signature(bundle)
    capsys.readouterr()

    signature["signed_sha256"] = "0" * 64
    tampered = out / "tampered-signature-digest.zip"
    with ZipFile(bundle) as src, ZipFile(tampered, "w") as dst:
        for item in src.infolist():
            if item.filename == signature_member:
                dst.writestr(item, json.dumps(signature))
            else:
                dst.writestr(item, src.read(item.filename))

    assert cli.main(["inspect-bundle", "--format", "json", str(tampered)]) == 0
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.inspect_bundle.v1"
    assert payload["ok"] is False
    assert payload["signature"]["status"] == "invalid"
    assert payload["review"]["status"] == "warn"
    assert any("Signed manifest digest mismatch" in warning for warning in payload["review"]["warnings"])
    assert payload["errors"] == []


def test_verify_bundle_requires_manifest(tmp_path: Path, capsys) -> None:
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

    missing_manifest = out / "missing-manifest.zip"
    with ZipFile(bundle) as src, ZipFile(missing_manifest, "w") as dst:
        for name in src.namelist():
            if name.endswith(BUNDLE_MANIFEST_NAME):
                continue
            dst.writestr(name, src.read(name))

    assert cli.main(["verify-bundle", str(missing_manifest)]) == 2
    output = capsys.readouterr().out
    assert f"Missing {BUNDLE_MANIFEST_NAME} in bundle." in output


def test_signing_key_reports_ready_for_ignored_repo_key(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    (repo / ".gitignore").write_text(".agentledger-signing-key*\n", encoding="utf-8")
    key_file = repo / ".agentledger-signing-key"
    key_file.write_text("0123456789abcdef0123456789abcdef\n", encoding="utf-8")

    assert cli.main(["signing-key", "--repo", str(repo), "--key-file", str(key_file)]) == 0

    output = capsys.readouterr().out
    assert "AgentLedger signing key: ready" in output
    assert f"Key file: {key_file.resolve()}" in output
    assert "Inside repo: yes" in output
    assert "Git ignored: yes" in output
    assert "Git tracked: no" in output
    assert "0123456789abcdef" not in output


def test_signing_key_json_blocks_unignored_repo_key(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    key_file = repo / "local-signing-key.txt"
    key_file.write_text("0123456789abcdef0123456789abcdef\n", encoding="utf-8")

    assert cli.main(["signing-key", "--repo", str(repo), "--key-file", str(key_file), "--format", "json"]) == 2

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.signing_key.v1"
    assert payload["ok"] is False
    assert payload["key_file"] == str(key_file.resolve())
    assert payload["repo"] == str(repo.resolve())
    assert payload["exists"] is True
    assert payload["file"] is True
    assert payload["size_bytes"] == 32
    assert payload["empty"] is False
    assert payload["inside_repo"] is True
    assert payload["ignored_by_git"] is False
    assert payload["tracked_by_git"] is False
    assert any("not ignored by git" in error for error in payload["errors"])
    assert payload["next_actions"]
    assert "0123456789abcdef" not in json.dumps(payload)


def test_signing_key_json_blocks_missing_key(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    key_file = tmp_path / "missing-signing-key.txt"

    assert cli.main(["signing-key", "--repo", str(repo), "--key-file", str(key_file), "--format", "json"]) == 2

    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.signing_key.v1"
    assert payload["ok"] is False
    assert payload["exists"] is False
    assert payload["file"] is False
    assert payload["size_bytes"] is None
    assert payload["empty"] is None
    assert any("Key file not found" in error for error in payload["errors"])


def test_sign_bundle_adds_and_verifies_hmac_signature(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    key_file = tmp_path / "agentledger-signing-key.txt"
    key_file.write_text("shared-test-key\n", encoding="utf-8")

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
    manifest_member, manifest = _bundle_manifest(bundle)
    capsys.readouterr()

    assert cli.main(["sign-bundle", str(bundle), "--key-file", str(key_file)]) == 0
    output = capsys.readouterr().out
    signature_member, signature = _bundle_signature(bundle)
    assert f"Signed bundle: {bundle}" in output
    assert f"Signature: {signature_member}" in output
    assert f"Signed manifest: {manifest_member}" in output
    assert signature_member == f"{run_dir.name}/{BUNDLE_SIGNATURE_NAME}"
    assert signature["schema_version"] == BUNDLE_SIGNATURE_SCHEMA
    assert signature["algorithm"] == "hmac-sha256"
    assert signature["signed_member"] == manifest_member
    assert signature["signed_sha256"]
    assert signature["signature"]

    assert cli.main(["verify-bundle", str(bundle), "--signature-key-file", str(key_file)]) == 0
    output = capsys.readouterr().out
    assert f"Manifest: {manifest_member}" in output
    assert f"Files checked: {manifest['file_count']}" in output
    assert f"Signature: {signature_member} verified" in output


def test_sign_bundle_json_output(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    key_file = tmp_path / "agentledger-signing-key.txt"
    key_file.write_text("shared-test-key\n", encoding="utf-8")

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
    signed_bundle = tmp_path / "signed-agentledger.zip"
    capsys.readouterr()

    assert (
        cli.main(
            [
                "sign-bundle",
                str(bundle),
                "--key-file",
                str(key_file),
                "--output",
                str(signed_bundle),
                "--format",
                "json",
            ]
        )
        == 0
    )
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.sign_bundle.v1"
    assert payload["ok"] is True
    assert payload["bundle"] == str(bundle.resolve())
    assert payload["signed_bundle"] == str(signed_bundle.resolve())
    assert payload["signature"]["schema_version"] == BUNDLE_SIGNATURE_SCHEMA
    assert payload["signature"]["algorithm"] == "hmac-sha256"
    assert payload["signature"]["member"].endswith(f"/{BUNDLE_SIGNATURE_NAME}")
    assert payload["signature"]["signed_member"].endswith(f"/{BUNDLE_MANIFEST_NAME}")
    assert payload["signature"]["signed_sha256"]
    assert "signature" not in payload["signature"]
    assert payload["errors"] == []

    assert cli.main(["verify-bundle", str(signed_bundle), "--signature-key-file", str(key_file)]) == 0
    assert "verified" in capsys.readouterr().out


def test_sign_bundle_json_reports_key_error(tmp_path: Path, capsys) -> None:
    bundle = tmp_path / "missing.zip"
    key_file = tmp_path / "missing-key.txt"

    assert (
        cli.main(
            [
                "sign-bundle",
                str(bundle),
                "--key-file",
                str(key_file),
                "--format",
                "json",
            ]
        )
        == 2
    )
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.sign_bundle.v1"
    assert payload["ok"] is False
    assert payload["bundle"] == str(bundle.resolve())
    assert payload["signed_bundle"] == str(bundle.resolve())
    assert payload["signature"] is None
    assert any("Key file not found" in error for error in payload["errors"])


def test_sign_bundle_replaces_existing_signature(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    first_key = tmp_path / "first-key.txt"
    second_key = tmp_path / "second-key.txt"
    first_key.write_text("first-key\n", encoding="utf-8")
    second_key.write_text("second-key\n", encoding="utf-8")

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
    capsys.readouterr()

    assert cli.main(["sign-bundle", str(bundle), "--key-file", str(first_key)]) == 0
    assert cli.main(["sign-bundle", str(bundle), "--key-file", str(second_key)]) == 0
    capsys.readouterr()

    with ZipFile(bundle) as archive:
        signature_members = [name for name in archive.namelist() if name.endswith(f"/{BUNDLE_SIGNATURE_NAME}")]
    assert signature_members == [f"{run_dir.name}/{BUNDLE_SIGNATURE_NAME}"]

    assert cli.main(["verify-bundle", str(bundle), "--signature-key-file", str(second_key)]) == 0
    assert "verified" in capsys.readouterr().out
    assert cli.main(["verify-bundle", str(bundle), "--signature-key-file", str(first_key)]) == 2
    assert "Signature mismatch" in capsys.readouterr().out

    assert cli.main(["verify-bundle", str(bundle), "--format", "json", "--signature-key-file", str(first_key)]) == 2
    payload = _parse_json_output(capsys.readouterr().out)
    assert payload["schema_version"] == "agentledger.verify_bundle.v1"
    assert payload["ok"] is False
    assert payload["signature"]["status"] == "invalid"
    assert payload["signature"]["verified"] is False
    assert any("Signature mismatch" in error for error in payload["errors"])


def test_verify_bundle_requires_signature_with_key(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    key_file = tmp_path / "agentledger-signing-key.txt"
    key_file.write_text("shared-test-key\n", encoding="utf-8")

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
    capsys.readouterr()

    assert cli.main(["verify-bundle", str(bundle), "--require-signature"]) == 2
    output = capsys.readouterr().out
    assert "--require-signature requires --signature-key-file." in output

    assert cli.main(["verify-bundle", str(bundle), "--signature-key-file", str(key_file), "--require-signature"]) == 2
    output = capsys.readouterr().out
    assert f"Missing {BUNDLE_SIGNATURE_NAME} in bundle." in output


def test_verify_bundle_reports_unverified_signature_without_key(tmp_path: Path, capsys) -> None:
    repo = make_repo(tmp_path)
    out = tmp_path / "ledger"
    key_file = tmp_path / "agentledger-signing-key.txt"
    key_file.write_text("shared-test-key\n", encoding="utf-8")

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
    assert cli.main(["sign-bundle", str(bundle), "--key-file", str(key_file)]) == 0
    capsys.readouterr()

    assert cli.main(["verify-bundle", str(bundle)]) == 0
    output = capsys.readouterr().out
    assert "present (not verified; pass --signature-key-file to verify)" in output


def test_verify_bundle_rejects_checksum_mismatch(tmp_path: Path, capsys) -> None:
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

    tampered = out / "tampered.zip"
    with ZipFile(bundle) as src, ZipFile(tampered, "w") as dst:
        for name in src.namelist():
            if name.endswith("agentledger-report.md"):
                dst.writestr(name, "# tampered\n")
            else:
                dst.writestr(name, src.read(name))

    assert cli.main(["verify-bundle", str(tampered)]) == 2
    output = capsys.readouterr().out
    assert "Checksum mismatch for bundle member:" in output
    assert "agentledger-report.md" in output


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
    assert payload["schema_version"] == "agentledger.inspect_report.v1"
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
    assert payload["schema_version"] == "agentledger.compare.v1"
    assert payload["changed_files"]["old"] == 1
    assert payload["changed_files"]["new"] == 2
    assert payload["exit_code"]["old"] == 0
    assert payload["exit_code"]["new"] == 0
    assert payload["exit_code"]["trend"] in {"unchanged", "improved", "regressed", "still failing", "not comparable"}
