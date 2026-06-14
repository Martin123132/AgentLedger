from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from agentledger import __version__, cli
from agentledger.contracts import CONTRACTS_DOC, CONTRACTS_SCHEMA, JSON_CONTRACTS


SCHEMAS = {
    "contracts": "agentledger.contracts.v1",
    "doctor": "agentledger.doctor.v1",
    "open_latest": "agentledger.open_latest.v1",
    "history": "agentledger.history.v1",
    "inspect_report": "agentledger.inspect_report.v1",
    "check": "agentledger.check.v1",
    "review": "agentledger.review.v1",
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

    return {
        "contracts": _run_json(capsys, ["contracts", "--format", "json"]),
        "doctor": _run_json(capsys, ["doctor", "--json"], {0, 2}),
        "open_latest": _run_json(capsys, ["open-latest", "--format", "json", "--out", str(out)]),
        "history": _run_json(capsys, ["history", "--format", "json", "--out", str(out)]),
        "inspect_report": _run_json(capsys, ["inspect-report", "--format", "json", str(second)]),
        "check": _run_json(capsys, ["check", "--format", "json", "--allow-warnings", str(second)]),
        "review": _run_json(capsys, ["review", "--format", "json", "--out", str(out), "--allow-warnings"]),
        "verify_bundle": _run_json(capsys, ["verify-bundle", "--format", "json", f"{second}.zip"]),
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
        "history": {"schema_version", "out", "runs"},
        "inspect_report": {
            "schema_version",
            "run_dir",
            "command",
            "exit_code",
            "test_framework",
            "changed_files",
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
            "check",
            "review_exit_code",
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

    doctor = json_payloads["doctor"]
    _assert_keys(doctor["optional"], {"configured", "total", "missing"})
    assert doctor["checks"]
    _assert_keys(doctor["checks"][0], {"name", "ok", "detail", "required"})

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
            "markdown",
            "json",
            "html",
            "zip",
        },
    )

    for name in ("inspect_report", "verify_bundle"):
        _assert_keys(json_payloads[name]["artifacts"], {"ok", "warn"})

    check = json_payloads["check"]
    assert check["status"] in {"pass", "warn", "block"}
    _assert_keys(check["rule_counts"], {"pass", "warn", "block", "total"})
    assert check["rules"]
    _assert_keys(check["rules"][0], {"id", "status", "message"})
    _assert_keys(check["policy"], {"require_tests", "dirty", "max_changed_files"})

    review = json_payloads["review"]
    _assert_keys(review["paths"], {"markdown", "json", "html", "zip"})
    assert review["check"]["schema_version"] == SCHEMAS["check"]

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
