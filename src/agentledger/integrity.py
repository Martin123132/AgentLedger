from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .model import LedgerReport, ReportIntegrity


REPORT_INTEGRITY_SCHEMA = "agentledger.report_integrity.v1"
VERIFY_CHAIN_SCHEMA = "agentledger.verify_chain.v1"
REPORT_DIGEST_ALGORITHM = "sha256"
REPORT_CANONICALIZATION = "json-sort-keys-v1"
REPORT_FILENAME = "agentledger-report.json"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PreviousReportLink:
    run_id: str
    report_sha256: str


def _canonical_payload(report: dict[str, Any]) -> dict[str, Any]:
    payload = dict(report)
    integrity = payload.get("integrity")
    if isinstance(integrity, dict):
        canonical_integrity = dict(integrity)
        canonical_integrity.pop("report_sha256", None)
        payload["integrity"] = canonical_integrity
    return payload


def canonical_report_bytes(report: dict[str, Any]) -> bytes:
    return json.dumps(
        _canonical_payload(report),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def report_sha256(report: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_report_bytes(report)).hexdigest()


def attach_report_integrity(report: LedgerReport, previous: PreviousReportLink | None) -> ReportIntegrity:
    integrity = ReportIntegrity(
        schema_version=REPORT_INTEGRITY_SCHEMA,
        algorithm=REPORT_DIGEST_ALGORITHM,
        canonicalization=REPORT_CANONICALIZATION,
        report_sha256="",
        previous_run_id=previous.run_id if previous else None,
        previous_report_sha256=previous.report_sha256 if previous else None,
    )
    report.integrity = integrity
    integrity.report_sha256 = report_sha256(report.to_dict())
    return integrity


def report_integrity_summary(report: dict[str, Any]) -> dict[str, Any]:
    computed = report_sha256(report)
    integrity = report.get("integrity")
    if integrity is None:
        return {
            "status": "legacy",
            "schema_version": None,
            "algorithm": None,
            "canonicalization": None,
            "report_sha256": None,
            "computed_sha256": computed,
            "previous_run_id": None,
            "previous_report_sha256": None,
            "errors": [],
        }
    if not isinstance(integrity, dict):
        return _invalid_summary(computed, None, ["Report integrity field is not an object."])

    errors: list[str] = []
    schema = integrity.get("schema_version")
    algorithm = integrity.get("algorithm")
    canonicalization = integrity.get("canonicalization")
    stored = integrity.get("report_sha256")
    previous_run_id = integrity.get("previous_run_id")
    previous_sha = integrity.get("previous_report_sha256")

    if schema != REPORT_INTEGRITY_SCHEMA:
        errors.append(f"Unexpected report integrity schema: {schema!r}.")
    if algorithm != REPORT_DIGEST_ALGORITHM:
        errors.append(f"Unexpected report digest algorithm: {algorithm!r}.")
    if canonicalization != REPORT_CANONICALIZATION:
        errors.append(f"Unexpected report canonicalization: {canonicalization!r}.")
    if not isinstance(stored, str) or not _SHA256_RE.fullmatch(stored):
        errors.append("Report integrity digest is not a lowercase SHA-256 value.")
    elif stored != computed:
        errors.append("Report SHA-256 does not match the canonical report payload.")
    if previous_run_id is not None and (not isinstance(previous_run_id, str) or not previous_run_id.strip()):
        errors.append("Previous run ID must be a non-empty string or null.")
    if previous_sha is not None and (not isinstance(previous_sha, str) or not _SHA256_RE.fullmatch(previous_sha)):
        errors.append("Previous report digest is not a lowercase SHA-256 value or null.")
    if (previous_run_id is None) != (previous_sha is None):
        errors.append("Previous run ID and previous report digest must both be set or both be null.")

    return {
        "status": "invalid" if errors else "valid",
        "schema_version": schema,
        "algorithm": algorithm,
        "canonicalization": canonicalization,
        "report_sha256": stored,
        "computed_sha256": computed,
        "previous_run_id": previous_run_id,
        "previous_report_sha256": previous_sha,
        "errors": errors,
    }


def _invalid_summary(computed: str, integrity: dict[str, Any] | None, errors: list[str]) -> dict[str, Any]:
    payload = integrity or {}
    return {
        "status": "invalid",
        "schema_version": payload.get("schema_version"),
        "algorithm": payload.get("algorithm"),
        "canonicalization": payload.get("canonicalization"),
        "report_sha256": payload.get("report_sha256"),
        "computed_sha256": computed,
        "previous_run_id": payload.get("previous_run_id"),
        "previous_report_sha256": payload.get("previous_report_sha256"),
        "errors": errors,
    }


def previous_report_link(out_root: Path) -> tuple[PreviousReportLink | None, list[str]]:
    latest = out_root / "latest.txt"
    if not latest.exists():
        return None, []
    try:
        value = latest.read_text(encoding="utf-8").strip()
    except OSError:
        return None, ["History integrity started a new root because latest.txt was unreadable."]
    if not value:
        return None, ["History integrity started a new root because latest.txt was empty."]

    run_dir = Path(value)
    if not run_dir.is_absolute():
        run_dir = out_root / run_dir
    try:
        payload = json.loads((run_dir / REPORT_FILENAME).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, ["History integrity started a new root because the latest report was unreadable."]
    if not isinstance(payload, dict):
        return None, ["History integrity started a new root because the latest report was invalid."]

    run_id = payload.get("run_id")
    if not isinstance(run_id, str) or not run_id.strip():
        return None, ["History integrity started a new root because the latest report had no run ID."]

    integrity = payload.get("integrity")
    if integrity is None:
        return PreviousReportLink(run_id=run_id, report_sha256=report_sha256(payload)), []
    if not isinstance(integrity, dict):
        return None, ["History integrity started a new root because the latest integrity record was invalid."]
    stored = integrity.get("report_sha256")
    if not isinstance(stored, str) or not _SHA256_RE.fullmatch(stored):
        return None, ["History integrity started a new root because the latest report digest was invalid."]

    warnings = []
    if report_sha256(payload) != stored:
        warnings.append("The previous report digest did not verify; the new run preserves its stored link for review.")
    return PreviousReportLink(run_id=run_id, report_sha256=stored), warnings


def verify_history_chain(out_root: Path) -> dict[str, Any]:
    out_root = out_root.resolve()
    result = {
        "schema_version": VERIFY_CHAIN_SCHEMA,
        "ok": False,
        "status": "empty",
        "out": str(out_root),
        "latest_run": None,
        "head_run_id": None,
        "head_sha256": None,
        "total_runs": 0,
        "chained_runs": 0,
        "legacy_runs": 0,
        "roots": [],
        "runs": [],
        "warnings": [],
        "errors": [],
    }
    if not out_root.exists():
        result["errors"].append(f"AgentLedger output directory not found: {out_root}")
        return result

    records: list[dict[str, Any]] = []
    for run_dir in sorted(out_root.iterdir(), key=lambda path: path.name, reverse=True):
        report_path = run_dir / REPORT_FILENAME
        if not run_dir.is_dir() or not report_path.exists():
            continue
        try:
            payload = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            entry = {
                "run_id": run_dir.name,
                "run_dir": str(run_dir.resolve()),
                "status": "invalid",
                "report_sha256": None,
                "computed_sha256": None,
                "previous_run_id": None,
                "previous_report_sha256": None,
                "errors": [f"Report is unreadable: {exc}"],
                "_report": None,
                "_has_integrity": False,
            }
        else:
            if not isinstance(payload, dict):
                entry = {
                    "run_id": run_dir.name,
                    "run_dir": str(run_dir.resolve()),
                    "status": "invalid",
                    "report_sha256": None,
                    "computed_sha256": None,
                    "previous_run_id": None,
                    "previous_report_sha256": None,
                    "errors": ["Report payload is not a JSON object."],
                    "_report": None,
                    "_has_integrity": False,
                }
            else:
                summary = report_integrity_summary(payload)
                entry = {
                    "run_id": str(payload.get("run_id") or run_dir.name),
                    "run_dir": str(run_dir.resolve()),
                    "status": summary["status"],
                    "report_sha256": summary["report_sha256"],
                    "computed_sha256": summary["computed_sha256"],
                    "previous_run_id": summary["previous_run_id"],
                    "previous_report_sha256": summary["previous_report_sha256"],
                    "errors": list(summary["errors"]),
                    "_report": payload,
                    "_has_integrity": payload.get("integrity") is not None,
                }
        records.append(entry)

    result["total_runs"] = len(records)
    if not records:
        result["errors"].append(f"No AgentLedger reports found in {out_root}")
        return result

    by_run_id: dict[str, dict[str, Any]] = {}
    for entry in records:
        run_id = entry["run_id"]
        if run_id in by_run_id:
            entry["errors"].append(f"Duplicate run ID: {run_id}")
            by_run_id[run_id]["errors"].append(f"Duplicate run ID: {run_id}")
        else:
            by_run_id[run_id] = entry

    linked_from: dict[str, list[str]] = {}
    for entry in records:
        previous_run_id = entry["previous_run_id"]
        if entry["status"] == "legacy":
            continue
        if previous_run_id is None:
            result["roots"].append(entry["run_id"])
            continue
        linked_from.setdefault(previous_run_id, []).append(entry["run_id"])
        previous = by_run_id.get(previous_run_id)
        if previous is None:
            entry["errors"].append(f"Previous run is missing: {previous_run_id}")
            continue
        if previous["status"] == "legacy":
            expected = previous["computed_sha256"]
        else:
            expected = previous["report_sha256"]
        if not expected:
            entry["errors"].append(f"Previous run has no usable digest: {previous_run_id}")
        elif entry["previous_report_sha256"] != expected:
            entry["errors"].append(f"Previous report digest does not match run {previous_run_id}.")

    for previous_run_id, children in linked_from.items():
        if len(children) > 1:
            message = f"History fork detected after {previous_run_id}: {', '.join(sorted(children))}"
            for child in children:
                by_run_id[child]["errors"].append(message)

    for entry in records:
        seen: set[str] = set()
        current = entry
        while current["previous_run_id"] is not None:
            run_id = current["run_id"]
            if run_id in seen:
                entry["errors"].append(f"History cycle detected at {run_id}.")
                break
            seen.add(run_id)
            previous = by_run_id.get(current["previous_run_id"])
            if previous is None or previous["status"] == "legacy":
                break
            current = previous

    latest_path = out_root / "latest.txt"
    if not latest_path.exists():
        result["errors"].append(f"Latest run pointer not found: {latest_path}")
    else:
        try:
            latest_value = latest_path.read_text(encoding="utf-8").strip()
            latest_dir = Path(latest_value)
            if not latest_dir.is_absolute():
                latest_dir = out_root / latest_dir
            latest_dir = latest_dir.resolve()
        except OSError as exc:
            result["errors"].append(f"Latest run pointer is unreadable: {exc}")
        else:
            result["latest_run"] = str(latest_dir)
            head = next((item for item in records if Path(item["run_dir"]) == latest_dir), None)
            if head is None:
                result["errors"].append("Latest run pointer does not identify a discovered report.")
            else:
                result["head_run_id"] = head["run_id"]
                result["head_sha256"] = head["report_sha256"] or head["computed_sha256"]
                if head["status"] == "legacy" and any(
                    item is not head and item["status"] != "legacy" for item in records
                ):
                    head["errors"].append(
                        "Latest report has no integrity record after chained history began."
                    )

    for entry in records:
        if entry["errors"]:
            entry["status"] = "invalid"
    result["chained_runs"] = sum(1 for entry in records if entry["_has_integrity"])
    result["legacy_runs"] = sum(
        1 for entry in records if entry["_report"] is not None and not entry["_has_integrity"]
    )
    invalid = [entry for entry in records if entry["status"] == "invalid"]
    if invalid:
        result["errors"].append(f"{len(invalid)} report(s) failed history integrity verification.")
    if result["legacy_runs"]:
        result["warnings"].append(
            f"{result['legacy_runs']} legacy report(s) have no stored self-digest; linked legacy reports are checked by canonical digest."
        )
    if len(result["roots"]) > 1:
        result["warnings"].append(f"History contains {len(result['roots'])} independent integrity roots.")

    public_runs = []
    for entry in records:
        public_runs.append({key: value for key, value in entry.items() if not key.startswith("_")})
    result["runs"] = public_runs
    if result["errors"]:
        result["status"] = "broken"
    elif result["warnings"]:
        result["ok"] = True
        result["status"] = "partial"
    else:
        result["ok"] = True
        result["status"] = "valid"
    return result
