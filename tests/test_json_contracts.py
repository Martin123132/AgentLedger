from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentledger import __version__, cli
from agentledger.contracts import CONTRACTS_DOC, CONTRACTS_SCHEMA, JSON_CONTRACTS


SCHEMAS = {
    "contracts": "agentledger.contracts.v1",
    "demo": "agentledger.demo.v1",
    "try": "agentledger.demo.v1",
    "doctor": "agentledger.doctor.v1",
    "open_latest": "agentledger.open_latest.v1",
    "history": "agentledger.history.v1",
    "verify_chain": "agentledger.verify_chain.v1",
    "status": "agentledger.status.v1",
    "alpha_guide": "agentledger.alpha_guide.v1",
    "alpha": "agentledger.alpha_summary.v1",
    "alpha_summary": "agentledger.alpha_summary.v1",
    "alpha_handoff": "agentledger.alpha_handoff.v1",
    "pack_alpha": "agentledger.pack_alpha.v1",
    "open_packet": "agentledger.open_packet.v1",
    "support_packet": "agentledger.support_packet.v1",
    "feedback": "agentledger.feedback.v1",
    "feedback_summary": "agentledger.feedback_summary.v1",
    "feedback_export": "agentledger.feedback_export_result.v1",
    "inspect_report": "agentledger.inspect_report.v1",
    "check": "agentledger.check.v1",
    "review": "agentledger.review.v1",
    "signing_key": "agentledger.signing_key.v1",
    "sign_bundle": "agentledger.sign_bundle.v1",
    "inspect_bundle": "agentledger.inspect_bundle.v1",
    "verify_bundle": "agentledger.verify_bundle.v1",
    "compare": "agentledger.compare.v1",
}


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "agentledger-contract@example.local")
    _git(repo, "config", "user.name", "AgentLedger Contract Test")
    (repo / "README.md").write_text("# Contract repo\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


def _parse_json_output(output: str) -> dict:
    start = output.find("{")
    end = output.rfind("}")
    assert start != -1 and end != -1 and end >= start
    return json.loads(output[start : end + 1])


def _run_json(capsys: pytest.CaptureFixture[str], args: list[str], expected_exit: set[int] | None = None) -> dict:
    expected_exit = expected_exit or {0}
    exit_code = cli.main(args)
    assert exit_code in expected_exit
    return _parse_json_output(capsys.readouterr().out)


def _assert_keys(payload: dict, keys: set[str]) -> None:
    missing = keys - payload.keys()
    assert not missing, f"Missing JSON contract fields: {sorted(missing)}"


def _write_alpha_summary(path: Path, run_dir: Path) -> None:
    payload = {
        "schema_version": "agentledger.alpha_summary.v1",
        "ok": True,
        "summary_file": str(path),
        "started_at": "2026-06-15T00:00:00+00:00",
        "ended_at": "2026-06-15T00:01:00+00:00",
        "repo": str(path.parent / "repo"),
        "out": str(path.parent),
        "latest_run": str(run_dir),
        "bundle": f"{run_dir}.zip",
        "agentledger_version": "agentledger 0.1.8a0",
        "python_version": "Python 3.13.13",
        "git_version": "git version 2.54.0.windows.1",
        "doctor": "AgentLedger doctor: ready",
        "status": "warn",
        "status_summary": "2 warnings; review before accepting.",
        "status_exit_code": 0,
        "report_paths": {
            "markdown": str(run_dir / "agentledger-report.md"),
            "json": str(run_dir / "agentledger-report.json"),
            "html": str(run_dir / "agentledger-report.html"),
            "zip": f"{run_dir}.zip",
        },
        "feedback": {
            "total_entries": 0,
            "returned_entries": 0,
            "runs_with_feedback": 0,
            "latest_run_entries": 0,
            "categories": {},
            "severities": {},
            "errors": [],
        },
        "next_actions": ["Read the Markdown report before sharing evidence."],
        "fix_first": [],
        "errors": [],
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


@pytest.fixture
def json_payloads(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> dict[str, dict]:
    repo = _make_repo(tmp_path)
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
                "from pathlib import Path; Path('note.txt').write_text('one')",
            ]
        )
        == 0
    )
    first = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()

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
                "from pathlib import Path; Path('note.txt').write_text('two'); Path('second.txt').write_text('two')",
            ]
        )
        == 0
    )
    second = Path((out / "latest.txt").read_text(encoding="utf-8").strip())
    capsys.readouterr()
    alpha_summary = tmp_path / "alpha-summary.json"
    _write_alpha_summary(alpha_summary, second)
    alpha_out = tmp_path / "alpha-ledger"
    alpha_command_summary = tmp_path / "alpha-command-summary.json"
    signature_key = tmp_path / "agentledger-signing-key.txt"
    signature_key.write_text("contract-test-signing-key\n", encoding="utf-8")

    return {
        "contracts": _run_json(capsys, ["contracts", "--format", "json"]),
        "demo": _run_json(capsys, ["demo", "--format", "json", "--output-dir", str(tmp_path / "demo-workspace")]),
        "try": _run_json(capsys, ["try", "--format", "json", "--output-dir", str(tmp_path / "try-workspace")]),
        "doctor": _run_json(capsys, ["doctor", "--json"], {0, 2}),
        "open_latest": _run_json(capsys, ["open-latest", "--format", "json", "--repo", str(repo), "--out", str(out)]),
        "history": _run_json(capsys, ["history", "--format", "json", "--repo", str(repo), "--out", str(out)]),
        "verify_chain": _run_json(capsys, ["verify-chain", "--format", "json", "--repo", str(repo), "--out", str(out)]),
        "status": _run_json(capsys, ["status", "--format", "json", "--repo", str(repo), "--out", str(out), "--allow-warnings"]),
        "alpha_guide": _run_json(capsys, ["alpha-guide", "--format", "json", "--repo", str(repo), "--out", str(out)]),
        "alpha": _run_json(
            capsys,
            [
                "alpha",
                "--format",
                "json",
                "--repo",
                str(repo),
                "--out",
                str(alpha_out),
                "--json-output",
                str(alpha_command_summary),
                "--",
                sys.executable,
                "-c",
                "print('contract alpha')",
            ],
        ),
        "alpha_summary": _run_json(capsys, ["alpha-summary", "--format", "json", str(alpha_summary)]),
        "alpha_handoff": _run_json(
            capsys,
            [
                "alpha-handoff",
                "--format",
                "json",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--output-dir",
                str(tmp_path / "alpha-handoff"),
            ],
        ),
        "pack_alpha": _run_json(
            capsys,
            [
                "pack-alpha",
                "--format",
                "json",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--output-dir",
                str(tmp_path / "pack-alpha"),
            ],
        ),
        "open_packet": _run_json(capsys, ["open-packet", "--format", "json", "--repo", str(repo), "--out", str(out)]),
        "support_packet": _run_json(capsys, ["support-packet", "--format", "json", "--out", str(tmp_path / "private-ledger")]),
        "feedback": _run_json(
            capsys,
            [
                "feedback",
                "--format",
                "json",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--note",
                "The latest report path was easy to find.",
                "--category",
                "docs",
                "--severity",
                "low",
            ],
        ),
        "feedback_summary": _run_json(capsys, ["feedback-summary", "--format", "json", "--repo", str(repo), "--out", str(out)]),
        "feedback_export": _run_json(
            capsys,
            [
                "feedback-export",
                "--format",
                "json",
                "--output-format",
                "json",
                "--repo",
                str(repo),
                "--out",
                str(out),
                "--output",
                str(tmp_path / "feedback-export.json"),
            ],
        ),
        "inspect_report": _run_json(capsys, ["inspect-report", "--format", "json", str(second)]),
        "check": _run_json(capsys, ["check", "--format", "json", "--allow-warnings", str(second)]),
        "review": _run_json(capsys, ["review", "--format", "json", "--repo", str(repo), "--out", str(out), "--allow-warnings"]),
        "verify_bundle": _run_json(capsys, ["verify-bundle", "--format", "json", f"{second}.zip"]),
        "signing_key": _run_json(capsys, ["signing-key", "--format", "json", "--repo", str(repo), "--key-file", str(signature_key)]),
        "sign_bundle": _run_json(capsys, ["sign-bundle", "--format", "json", f"{second}.zip", "--key-file", str(signature_key)]),
        "inspect_bundle": _run_json(capsys, ["inspect-bundle", "--format", "json", f"{second}.zip"]),
        "compare": _run_json(capsys, ["compare", "--format", "json", str(first), str(second)]),
    }


def test_json_contract_doc_lists_all_schema_versions() -> None:
    doc = (Path(__file__).resolve().parents[1] / "docs" / "json-contracts.md").read_text(encoding="utf-8")

    for schema in SCHEMAS.values():
        assert schema in doc


def test_contracts_command_prints_human_summary(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["contracts"]) == 0
    output = capsys.readouterr().out
    assert f"AgentLedger JSON contracts ({__version__})" in output
    assert f"Schema: {CONTRACTS_SCHEMA}" in output
    assert f"Docs: {CONTRACTS_DOC}" in output
    for contract in JSON_CONTRACTS:
        assert f"- {contract['command']}: {contract['schema_version']}" in output


def test_contracts_json_lists_known_contract_metadata(json_payloads: dict[str, dict]) -> None:
    payload = json_payloads["contracts"]
    assert payload["schema_version"] == CONTRACTS_SCHEMA
    assert payload["agentledger_version"] == __version__
    assert payload["docs"] == CONTRACTS_DOC
    _assert_keys(payload["compatibility"], {"stability", "unknown_fields", "breaking_changes"})
    assert payload["contracts"] == JSON_CONTRACTS


def test_json_contract_payloads_use_documented_schemas(json_payloads: dict[str, dict]) -> None:
    for name, schema in SCHEMAS.items():
        assert json_payloads[name]["schema_version"] == schema


def test_json_contract_payloads_include_stable_top_level_fields(json_payloads: dict[str, dict]) -> None:
    expected_fields = {
        "contracts": {"schema_version", "agentledger_version", "docs", "compatibility", "contracts"},
        "demo": {
            "schema_version",
            "ok",
            "status",
            "entrypoint",
            "workspace",
            "repo",
            "out",
            "latest_run",
            "paths",
            "privacy_mode",
            "command",
            "command_exit_code",
            "summary_output",
            "summary_written",
            "packet",
            "try_next",
            "cleanup",
            "errors",
        },
        "try": {
            "schema_version",
            "ok",
            "status",
            "entrypoint",
            "workspace",
            "repo",
            "out",
            "latest_run",
            "paths",
            "privacy_mode",
            "command",
            "command_exit_code",
            "summary_output",
            "summary_written",
            "packet",
            "try_next",
            "cleanup",
            "errors",
        },
        "doctor": {"schema_version", "status", "required_ok", "optional", "checks"},
        "open_latest": {
            "schema_version",
            "ok",
            "repo",
            "out",
            "latest_run",
            "paths",
            "missing_reports",
            "errors",
        },
        "open_packet": {
            "schema_version",
            "ok",
            "repo",
            "out",
            "latest_packet",
            "output_dir",
            "status",
            "summary",
            "files",
            "missing_files",
            "raw_evidence_copied",
            "packet",
            "errors",
        },
        "support_packet": {
            "schema_version",
            "ok",
            "generated_at",
            "agentledger_version",
            "platform",
            "python_version",
            "shell",
            "out",
            "out_redacted",
            "local_paths_included",
            "raw_evidence_copied",
            "include",
            "review_files",
            "keep_private",
            "suggested_commands",
            "issue_template",
            "privacy_note",
            "errors",
        },
        "history": {"schema_version", "out", "runs"},
        "verify_chain": {
            "schema_version",
            "ok",
            "status",
            "out",
            "latest_run",
            "head_run_id",
            "head_sha256",
            "total_runs",
            "chained_runs",
            "legacy_runs",
            "roots",
            "runs",
            "warnings",
            "errors",
        },
        "status": {
            "schema_version",
            "ok",
            "status",
            "repo",
            "out",
            "latest_run",
            "paths",
            "missing_reports",
            "check",
            "feedback",
            "next_actions",
            "errors",
            "status_exit_code",
        },
        "alpha_guide": {
            "schema_version",
            "ok",
            "repo",
            "out",
            "doctor",
            "fix_first",
            "commands",
            "evidence",
            "troubleshooting",
            "send_back",
            "keep_private",
            "known_limitations",
            "errors",
        },
        "alpha": {
            "schema_version",
            "ok",
            "summary_file",
            "started_at",
            "ended_at",
            "repo",
            "out",
            "latest_run",
            "bundle",
            "agentledger_version",
            "python_version",
            "git_version",
            "doctor",
            "status",
            "status_summary",
            "status_exit_code",
            "report_paths",
            "feedback",
            "fix_first",
            "next_actions",
            "errors",
        },
        "alpha_summary": {
            "schema_version",
            "ok",
            "summary_file",
            "started_at",
            "ended_at",
            "repo",
            "out",
            "latest_run",
            "bundle",
            "agentledger_version",
            "python_version",
            "git_version",
            "doctor",
            "status",
            "status_summary",
            "status_exit_code",
            "report_paths",
            "feedback",
            "fix_first",
            "next_actions",
            "errors",
        },
        "alpha_handoff": {
            "schema_version",
            "ok",
            "status",
            "summary",
            "generated_at",
            "agentledger_version",
            "repo",
            "out",
            "latest_run",
            "output_dir",
            "files",
            "share_safe",
            "redactions",
            "sharing",
            "review",
            "status_payload",
            "feedback_summary",
            "alpha_summary",
            "public_summary",
            "handling",
            "next_actions",
            "errors",
        },
        "pack_alpha": {
            "schema_version",
            "ok",
            "status",
            "summary",
            "generated_at",
            "agentledger_version",
            "repo",
            "out",
            "output_dir",
            "latest_packet",
            "files",
            "sharing",
            "raw_evidence_copied",
            "handoff_exit_code",
            "handoff",
            "public_summary",
            "validation",
            "next_actions",
            "errors",
            "pointer_errors",
        },
        "feedback": {
            "schema_version",
            "ok",
            "action",
            "run_dir",
            "feedback_file",
            "entry",
            "entries",
            "errors",
        },
        "feedback_summary": {
            "schema_version",
            "ok",
            "out",
            "filters",
            "total_entries",
            "returned_entries",
            "run_count",
            "runs_with_feedback",
            "categories",
            "severities",
            "runs",
            "entries",
            "errors",
        },
        "feedback_export": {
            "schema_version",
            "ok",
            "out",
            "output",
            "output_format",
            "export_schema_version",
            "filters",
            "total_entries",
            "returned_entries",
            "run_count",
            "runs_with_feedback",
            "errors",
        },
        "inspect_report": {
            "schema_version",
            "run_dir",
            "command",
            "exit_code",
            "command_duration_seconds",
            "test_framework",
            "changed_files",
            "attributed_files",
            "change_attribution",
            "environment",
            "integrity",
            "artifacts",
            "tokometer",
            "privacy_mode",
        },
        "check": {
            "schema_version",
            "status",
            "ok",
            "run_dir",
            "report",
            "summary",
            "rule_counts",
            "warning_rules",
            "blocking_rules",
            "rules",
            "policy",
        },
        "review": {
            "schema_version",
            "status",
            "ok",
            "summary",
            "run_dir",
            "command_exit_code",
            "paths",
            "history",
            "comparison",
            "check",
            "output",
            "review_exit_code",
        },
        "signing_key": {
            "schema_version",
            "ok",
            "key_file",
            "repo",
            "git_root",
            "exists",
            "file",
            "size_bytes",
            "empty",
            "inside_repo",
            "ignored_by_git",
            "tracked_by_git",
            "warnings",
            "errors",
            "next_actions",
        },
        "sign_bundle": {
            "schema_version",
            "ok",
            "bundle",
            "signed_bundle",
            "signature",
            "errors",
        },
        "inspect_bundle": {
            "schema_version",
            "ok",
            "bundle",
            "readable",
            "manifest",
            "signature",
            "reports",
            "review",
            "errors",
            "next_actions",
        },
        "verify_bundle": {
            "schema_version",
            "ok",
            "bundle",
            "run_id",
            "manifest",
            "signature",
            "reports",
            "command",
            "changed_files",
            "artifacts",
            "errors",
        },
        "compare": {
            "schema_version",
            "changed_files",
            "exit_code",
            "artifacts",
            "command",
            "tokometer",
            "test_framework",
            "privacy_mode",
        },
    }

    for name, fields in expected_fields.items():
        _assert_keys(json_payloads[name], fields)


def test_json_contract_payloads_include_nested_summary_shapes(json_payloads: dict[str, dict]) -> None:
    contracts = json_payloads["contracts"]
    assert contracts["contracts"]
    _assert_keys(contracts["contracts"][0], {"command", "schema_version", "purpose", "stable_fields", "exit_codes"})

    demo = json_payloads["demo"]
    assert demo["ok"] is True
    assert demo["status"] == "pass"
    assert demo["entrypoint"] == "demo"
    _assert_keys(demo["paths"], {"markdown", "json", "html", "zip"})
    assert demo["packet"] is None
    assert demo["try_next"]
    assert demo["cleanup"]
    assert demo["errors"] == []

    safe_try = json_payloads["try"]
    assert safe_try["ok"] is True
    assert safe_try["status"] == "pass"
    assert safe_try["entrypoint"] == "try"
    assert safe_try["packet"]["ok"] is True
    assert safe_try["packet"]["raw_evidence_copied"] is False
    assert any("open-packet" in command for command in safe_try["try_next"])
    assert safe_try["errors"] == []

    doctor = json_payloads["doctor"]
    _assert_keys(doctor["optional"], {"configured", "total", "missing"})
    assert doctor["checks"]
    _assert_keys(doctor["checks"][0], {"name", "ok", "detail", "required", "hint"})

    open_latest = json_payloads["open_latest"]
    assert open_latest["ok"] is True
    _assert_keys(open_latest["paths"], {"markdown", "json", "html", "zip"})
    assert open_latest["errors"] == []

    history = json_payloads["history"]
    assert len(history["runs"]) >= 2
    _assert_keys(
        history["runs"][0],
        {
            "run_id",
            "run_dir",
            "started_at",
            "ended_at",
            "command",
            "exit_code",
            "changed_files",
            "test_framework",
            "privacy_mode",
            "artifacts",
            "integrity",
            "markdown",
            "json",
            "html",
            "zip",
        },
    )

    verify_chain = json_payloads["verify_chain"]
    assert verify_chain["ok"] is True
    assert verify_chain["status"] == "valid"
    assert verify_chain["total_runs"] >= 2
    assert verify_chain["chained_runs"] == verify_chain["total_runs"]
    assert verify_chain["legacy_runs"] == 0
    assert verify_chain["head_run_id"]
    assert len(verify_chain["head_sha256"]) == 64
    _assert_keys(
        verify_chain["runs"][0],
        {
            "run_id",
            "run_dir",
            "status",
            "report_sha256",
            "computed_sha256",
            "previous_run_id",
            "previous_report_sha256",
            "errors",
        },
    )

    status = json_payloads["status"]
    assert status["status"] in {"pass", "warn", "block"}
    _assert_keys(status["paths"], {"markdown", "json", "html", "zip"})
    assert status["check"]["schema_version"] == SCHEMAS["check"]
    _assert_keys(
        status["feedback"],
        {
            "total_entries",
            "returned_entries",
            "runs_with_feedback",
            "latest_run_entries",
            "categories",
            "severities",
            "errors",
        },
    )
    assert status["next_actions"]

    alpha_guide = json_payloads["alpha_guide"]
    assert alpha_guide["ok"] is True
    _assert_keys(
        alpha_guide["doctor"],
        {"schema_version", "status", "summary", "required_ok", "optional", "required_blockers", "checks"},
    )
    assert alpha_guide["doctor"]["status"] == "ready"
    assert alpha_guide["fix_first"] == []
    _assert_keys(alpha_guide["commands"], {"setup", "verify", "run", "inspect", "feedback"})
    assert alpha_guide["commands"]["verify"]
    _assert_keys(alpha_guide["evidence"], {"output_root", "latest_pointer", "run_folder_contains", "bundle"})
    assert [item["area"] for item in alpha_guide["troubleshooting"]] == [
        "install",
        "command",
        "packet",
        "reporting",
    ]
    for item in alpha_guide["troubleshooting"]:
        _assert_keys(item, {"area", "when", "check", "next"})
    assert alpha_guide["send_back"]
    assert alpha_guide["keep_private"]
    assert alpha_guide["known_limitations"]
    assert alpha_guide["errors"] == []

    alpha = json_payloads["alpha"]
    assert alpha["ok"] is True
    assert alpha["status"] in {"pass", "warn"}
    _assert_keys(alpha["report_paths"], {"markdown", "json", "html", "zip"})
    _assert_keys(
        alpha["feedback"],
        {
            "total_entries",
            "returned_entries",
            "runs_with_feedback",
            "latest_run_entries",
            "categories",
            "severities",
            "errors",
        },
    )
    assert alpha["next_actions"]
    assert alpha["fix_first"] == []

    alpha_summary = json_payloads["alpha_summary"]
    assert alpha_summary["ok"] is True
    assert alpha_summary["status"] == "warn"
    _assert_keys(alpha_summary["report_paths"], {"markdown", "json", "html", "zip"})
    _assert_keys(
        alpha_summary["feedback"],
        {
            "total_entries",
            "returned_entries",
            "runs_with_feedback",
            "latest_run_entries",
            "categories",
            "severities",
            "errors",
        },
    )
    assert alpha_summary["next_actions"]
    assert alpha_summary["fix_first"] == []

    alpha_handoff = json_payloads["alpha_handoff"]
    assert alpha_handoff["ok"] is True
    assert alpha_handoff["status"] in {"pass", "warn"}
    assert alpha_handoff["share_safe"] is False
    _assert_keys(alpha_handoff["redactions"], {"local_paths", "markers", "note"})
    assert alpha_handoff["redactions"]["local_paths"] is False
    _assert_keys(alpha_handoff["files"], {"markdown", "json"})
    _assert_keys(alpha_handoff["sharing"], {"review_required", "share_safe", "share_files", "keep_private", "note"})
    assert alpha_handoff["sharing"]["review_required"] is True
    assert alpha_handoff["sharing"]["share_safe"] is False
    _assert_keys(
        alpha_handoff["handling"],
        {"raw_evidence_copied", "copied_files", "share_safe", "local_paths_redacted", "omits", "do_not_commit"},
    )
    assert alpha_handoff["handling"]["raw_evidence_copied"] is False
    assert alpha_handoff["handling"]["copied_files"] == []
    assert alpha_handoff["handling"]["share_safe"] is False
    assert alpha_handoff["handling"]["local_paths_redacted"] is False
    assert alpha_handoff["review"]["schema_version"] == SCHEMAS["review"]
    assert alpha_handoff["status_payload"]["schema_version"] == SCHEMAS["status"]
    assert alpha_handoff["feedback_summary"]["schema_version"] == SCHEMAS["feedback_summary"]
    _assert_keys(alpha_handoff["alpha_summary"], {"available", "summary_file", "payload", "errors"})
    _assert_keys(
        alpha_handoff["public_summary"],
        {"share_safe", "local_paths_omitted", "raw_evidence_copied", "text", "text_limit", "markdown", "do_not_share"},
    )
    assert alpha_handoff["public_summary"]["local_paths_omitted"] is True
    assert len(alpha_handoff["public_summary"]["text"]) <= alpha_handoff["public_summary"]["text_limit"]
    assert alpha_handoff["next_actions"]

    pack_alpha = json_payloads["pack_alpha"]
    assert pack_alpha["ok"] is True
    assert pack_alpha["status"] in {"pass", "warn"}
    assert pack_alpha["raw_evidence_copied"] is False
    assert pack_alpha["handoff_exit_code"] == 0
    _assert_keys(pack_alpha["files"], {"issue", "markdown", "json"})
    _assert_keys(pack_alpha["sharing"], {"review_required", "share_safe", "share_files", "keep_private", "note"})
    assert pack_alpha["sharing"]["share_safe"] is True
    assert pack_alpha["sharing"]["share_files"][0] == pack_alpha["files"]["issue"]
    assert pack_alpha["handoff"]["schema_version"] == SCHEMAS["alpha_handoff"]
    assert pack_alpha["handoff"]["share_safe"] is True
    assert pack_alpha["public_summary"] == pack_alpha["handoff"]["public_summary"]
    assert pack_alpha["public_summary"]["share_safe"] is True
    _assert_keys(pack_alpha["validation"], {"ok", "checked_files", "checks", "errors"})
    _assert_keys(pack_alpha["validation"]["checked_files"], {"issue", "markdown", "json"})
    assert pack_alpha["validation"]["ok"] is True
    assert pack_alpha["validation"]["errors"] == []
    assert pack_alpha["next_actions"]
    assert pack_alpha["latest_packet"]
    assert pack_alpha["pointer_errors"] == []

    open_packet = json_payloads["open_packet"]
    assert open_packet["ok"] is True
    assert open_packet["packet"]["schema_version"] == SCHEMAS["pack_alpha"]
    assert open_packet["latest_packet"] == pack_alpha["latest_packet"]
    assert open_packet["files"] == pack_alpha["files"]
    assert open_packet["missing_files"] == []
    assert open_packet["raw_evidence_copied"] is False
    assert open_packet["errors"] == []

    support_packet = json_payloads["support_packet"]
    assert support_packet["ok"] is True
    assert support_packet["out"] == "<agentledger-output>"
    assert support_packet["out_redacted"] is True
    assert support_packet["local_paths_included"] is False
    assert support_packet["raw_evidence_copied"] is False
    assert support_packet["include"]
    assert support_packet["review_files"]
    assert any("private repo paths" in item for item in support_packet["keep_private"])
    _assert_keys(
        support_packet["suggested_commands"],
        {"safe_try", "inspect", "share_safe", "copy_ready", "machine_readable"},
    )
    assert support_packet["suggested_commands"]["copy_ready"] == [
        "python -m agentledger support-packet --format markdown"
    ]
    assert support_packet["suggested_commands"]["machine_readable"] == [
        "python -m agentledger support-packet --format json"
    ]
    assert support_packet["issue_template"][-1] == "Raw evidence kept private: yes"
    assert support_packet["errors"] == []

    feedback = json_payloads["feedback"]
    assert feedback["ok"] is True
    assert feedback["action"] == "record"
    assert feedback["errors"] == []
    assert feedback["entries"]
    _assert_keys(
        feedback["entry"],
        {
            "schema_version",
            "id",
            "created_at",
            "run_id",
            "run_dir",
            "category",
            "severity",
            "source",
            "note",
            "redacted",
        },
    )

    feedback_summary = json_payloads["feedback_summary"]
    assert feedback_summary["ok"] is True
    assert feedback_summary["total_entries"] >= 1
    assert feedback_summary["returned_entries"] >= 1
    _assert_keys(feedback_summary["filters"], {"category", "severity", "limit"})
    assert feedback_summary["runs"]
    _assert_keys(feedback_summary["runs"][0], {"run_id", "run_dir", "feedback_file", "entry_count"})
    assert feedback_summary["entries"]
    _assert_keys(
        feedback_summary["entries"][0],
        {
            "schema_version",
            "id",
            "created_at",
            "run_id",
            "run_dir",
            "category",
            "severity",
            "source",
            "note",
            "redacted",
        },
    )

    feedback_export = json_payloads["feedback_export"]
    assert feedback_export["ok"] is True
    assert feedback_export["output_format"] == "json"
    assert feedback_export["export_schema_version"] == "agentledger.feedback_export.v1"
    _assert_keys(feedback_export["filters"], {"category", "severity", "limit"})
    assert feedback_export["errors"] == []

    for name in ("inspect_report", "verify_bundle"):
        _assert_keys(json_payloads[name]["artifacts"], {"ok", "warn"})

    inspect_report = json_payloads["inspect_report"]
    assert inspect_report["attributed_files"] == 2
    assert inspect_report["command_duration_seconds"] >= 0
    _assert_keys(
        inspect_report["change_attribution"],
        {
            "available",
            "basis",
            "preexisting_dirty",
            "changed_during_run",
            "committed_during_run",
            "working_tree_during_run",
            "unchanged_preexisting",
            "head_changed",
            "limitations",
        },
    )
    _assert_keys(
        inspect_report["environment"],
        {
            "schema_version",
            "agentledger_version",
            "os",
            "python",
            "git_version",
            "base_commit",
            "dependency_locks",
            "dependency_lock_count",
            "dependency_lock_limit",
            "dependency_locks_truncated",
            "privacy",
        },
    )
    _assert_keys(inspect_report["environment"]["os"], {"system", "release", "machine"})
    _assert_keys(inspect_report["environment"]["python"], {"implementation", "version"})
    _assert_keys(
        inspect_report["environment"]["privacy"],
        {
            "environment_variables_included",
            "executable_paths_included",
            "hostnames_included",
            "file_contents_included",
        },
    )
    _assert_keys(
        inspect_report["integrity"],
        {
            "status",
            "schema_version",
            "algorithm",
            "canonicalization",
            "report_sha256",
            "computed_sha256",
            "previous_run_id",
            "previous_report_sha256",
            "errors",
        },
    )
    assert inspect_report["integrity"]["status"] == "valid"

    check = json_payloads["check"]
    assert check["status"] in {"pass", "warn", "block"}
    _assert_keys(check["rule_counts"], {"pass", "warn", "block", "total"})
    assert check["rules"]
    _assert_keys(check["rules"][0], {"id", "status", "message"})
    _assert_keys(check["policy"], {"require_tests", "dirty", "max_changed_files"})

    review = json_payloads["review"]
    _assert_keys(review["paths"], {"markdown", "json", "html", "zip"})
    _assert_keys(review["history"], {"out", "limit", "runs", "errors"})
    assert review["history"]["limit"] == 3
    assert review["history"]["runs"]
    _assert_keys(
        review["history"]["runs"][0],
        {
            "run_id",
            "run_dir",
            "started_at",
            "ended_at",
            "command",
            "exit_code",
            "changed_files",
            "test_framework",
            "privacy_mode",
            "artifacts",
            "markdown",
            "json",
            "html",
            "zip",
            "current",
        },
    )
    _assert_keys(review["comparison"], {"available", "current_run", "previous_run", "compare", "errors"})
    assert review["comparison"]["available"] is True
    assert review["comparison"]["errors"] == []
    _assert_keys(
        review["comparison"]["compare"],
        {
            "schema_version",
            "changed_files",
            "exit_code",
            "artifacts",
            "command",
            "tokometer",
            "test_framework",
            "privacy_mode",
        },
    )
    assert review["comparison"]["compare"]["schema_version"] == SCHEMAS["compare"]
    assert review["check"]["schema_version"] == SCHEMAS["check"]
    assert review["output"] is None

    signing_key = json_payloads["signing_key"]
    assert signing_key["ok"] is True
    assert signing_key["exists"] is True
    assert signing_key["file"] is True
    assert signing_key["empty"] is False
    assert signing_key["inside_repo"] is False
    assert signing_key["ignored_by_git"] is None
    assert signing_key["tracked_by_git"] is None
    assert signing_key["errors"] == []
    assert signing_key["next_actions"]

    sign_bundle = json_payloads["sign_bundle"]
    assert sign_bundle["ok"] is True
    assert sign_bundle["bundle"] == sign_bundle["signed_bundle"]
    _assert_keys(
        sign_bundle["signature"],
        {"member", "schema_version", "algorithm", "signed_member", "signed_sha256"},
    )
    assert sign_bundle["signature"]["schema_version"] == "agentledger.bundle.signature.v1"
    assert sign_bundle["signature"]["algorithm"] == "hmac-sha256"
    assert "signature" not in sign_bundle["signature"]
    assert sign_bundle["errors"] == []

    inspect_bundle = json_payloads["inspect_bundle"]
    assert inspect_bundle["readable"] is True
    _assert_keys(inspect_bundle["manifest"], {"member", "schema_version", "digest_algorithm", "file_count", "run_id", "valid", "errors"})
    _assert_keys(
        inspect_bundle["signature"],
        {"member", "status", "verified", "schema_version", "algorithm", "signed_member", "signed_sha256"},
    )
    assert inspect_bundle["signature"]["status"] in {"not_present", "present_unverified", "invalid", "multiple"}
    assert "signature" not in inspect_bundle["signature"]
    _assert_keys(inspect_bundle["reports"], {"json", "markdown", "html", "missing"})
    _assert_keys(
        inspect_bundle["review"],
        {
            "status",
            "ok",
            "summary",
            "blockers",
            "warnings",
            "run_id",
            "command",
            "exit_code",
            "changed_files",
            "test_framework",
            "privacy_mode",
            "artifacts",
        },
    )
    assert inspect_bundle["next_actions"]

    verify_bundle = json_payloads["verify_bundle"]
    assert verify_bundle["ok"] is True
    _assert_keys(verify_bundle["manifest"], {"member", "schema_version", "digest_algorithm", "file_count", "run_id"})
    _assert_keys(verify_bundle["signature"], {"required", "member", "status", "verified"})
    assert verify_bundle["signature"]["status"] in {"not_present", "present_unverified", "verified", "invalid"}
    _assert_keys(verify_bundle["reports"], {"json", "markdown", "html"})
    assert verify_bundle["errors"] == []

    compare = json_payloads["compare"]
    _assert_keys(compare["changed_files"], {"old", "new", "delta", "delta_text"})
    _assert_keys(compare["exit_code"], {"old", "new", "trend"})
    _assert_keys(compare["artifacts"], {"old", "new"})
    _assert_keys(compare["command"], {"old", "new"})
    _assert_keys(compare["test_framework"], {"old", "new"})
    _assert_keys(compare["privacy_mode"], {"old", "new"})
