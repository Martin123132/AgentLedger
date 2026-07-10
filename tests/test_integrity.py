from __future__ import annotations

import json
from pathlib import Path

from agentledger.integrity import (
    canonical_report_bytes,
    report_integrity_summary,
    report_sha256,
    verify_history_chain,
)


def _write_report(
    out: Path,
    run_id: str,
    *,
    previous_run_id: str | None,
    previous_report_sha256: str | None,
) -> dict:
    report = {
        "schema_version": "agentledger.report.v1",
        "run_id": run_id,
        "integrity": {
            "schema_version": "agentledger.report_integrity.v1",
            "algorithm": "sha256",
            "canonicalization": "json-sort-keys-v1",
            "report_sha256": "",
            "previous_run_id": previous_run_id,
            "previous_report_sha256": previous_report_sha256,
        },
    }
    report["integrity"]["report_sha256"] = report_sha256(report)
    run_dir = out / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "agentledger-report.json").write_text(json.dumps(report) + "\n", encoding="utf-8")
    return report


def test_report_digest_is_canonical_and_excludes_only_its_own_digest() -> None:
    first = {
        "schema_version": "agentledger.report.v1",
        "run_id": "run-1",
        "value": {"b": 2, "a": 1},
        "integrity": {
            "schema_version": "agentledger.report_integrity.v1",
            "algorithm": "sha256",
            "canonicalization": "json-sort-keys-v1",
            "report_sha256": "0" * 64,
            "previous_run_id": None,
            "previous_report_sha256": None,
        },
    }
    reordered = {
        "integrity": {
            "previous_report_sha256": None,
            "report_sha256": "f" * 64,
            "previous_run_id": None,
            "canonicalization": "json-sort-keys-v1",
            "algorithm": "sha256",
            "schema_version": "agentledger.report_integrity.v1",
        },
        "value": {"a": 1, "b": 2},
        "run_id": "run-1",
        "schema_version": "agentledger.report.v1",
    }

    assert canonical_report_bytes(first) == canonical_report_bytes(reordered)
    assert report_sha256(first) == report_sha256(reordered)

    reordered["value"]["a"] = 99
    assert report_sha256(first) != report_sha256(reordered)


def test_report_integrity_summary_marks_legacy_and_digest_mismatch() -> None:
    legacy = {"schema_version": "agentledger.report.v1", "run_id": "legacy"}
    legacy_summary = report_integrity_summary(legacy)
    assert legacy_summary["status"] == "legacy"
    assert legacy_summary["computed_sha256"] == report_sha256(legacy)

    report = {
        **legacy,
        "integrity": {
            "schema_version": "agentledger.report_integrity.v1",
            "algorithm": "sha256",
            "canonicalization": "json-sort-keys-v1",
            "report_sha256": "0" * 64,
            "previous_run_id": None,
            "previous_report_sha256": None,
        },
    }
    summary = report_integrity_summary(report)
    assert summary["status"] == "invalid"
    assert "Report SHA-256 does not match" in " ".join(summary["errors"])


def test_verify_history_chain_detects_fork(tmp_path: Path) -> None:
    out = tmp_path / "ledger"
    root = _write_report(out, "run-1", previous_run_id=None, previous_report_sha256=None)
    _write_report(
        out,
        "run-2",
        previous_run_id="run-1",
        previous_report_sha256=root["integrity"]["report_sha256"],
    )
    _write_report(
        out,
        "run-3",
        previous_run_id="run-1",
        previous_report_sha256=root["integrity"]["report_sha256"],
    )
    (out / "latest.txt").write_text(str(out / "run-3"), encoding="utf-8")

    result = verify_history_chain(out)

    assert result["ok"] is False
    assert result["status"] == "broken"
    assert "History fork detected" in " ".join(
        error for run in result["runs"] for error in run["errors"]
    )


def test_verify_history_chain_detects_cycle(tmp_path: Path) -> None:
    out = tmp_path / "ledger"
    first = _write_report(
        out,
        "run-1",
        previous_run_id="run-2",
        previous_report_sha256="1" * 64,
    )
    second = _write_report(
        out,
        "run-2",
        previous_run_id="run-1",
        previous_report_sha256=first["integrity"]["report_sha256"],
    )
    first["integrity"]["previous_report_sha256"] = second["integrity"]["report_sha256"]
    first["integrity"]["report_sha256"] = report_sha256(first)
    (out / "run-1" / "agentledger-report.json").write_text(json.dumps(first) + "\n", encoding="utf-8")
    (out / "latest.txt").write_text(str(out / "run-2"), encoding="utf-8")

    result = verify_history_chain(out)

    assert result["ok"] is False
    assert result["status"] == "broken"
    assert "History cycle detected" in " ".join(
        error for run in result["runs"] for error in run["errors"]
    )
