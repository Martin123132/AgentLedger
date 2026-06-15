from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "release_rehearsal_receipt.py"

spec = importlib.util.spec_from_file_location("release_rehearsal_receipt", SCRIPT)
assert spec is not None
release_rehearsal_receipt = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release_rehearsal_receipt
assert spec.loader is not None
spec.loader.exec_module(release_rehearsal_receipt)


def _write_artifact(output_dir: Path, relative: str, kind: str, body: str) -> dict:
    path = output_dir / relative
    path.write_text(body, encoding="utf-8")
    return {
        "kind": kind,
        "file": relative,
        "bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "handling": "local-release-rehearsal-output",
    }


def write_receipt_manifest(tmp_path: Path) -> Path:
    output_dir = tmp_path / "rehearsal"
    output_dir.mkdir()
    artifacts = [
        _write_artifact(
            output_dir,
            "agentledger-0.1.8-alpha-release.md",
            "draft-release-notes",
            "# v0.1.8-alpha\n",
        ),
        _write_artifact(
            output_dir,
            "release-command-index.md",
            "release-command-index-markdown",
            "# AgentLedger Release Command Index\n",
        ),
        _write_artifact(
            output_dir,
            "release-rehearsal-summary.md",
            "release-rehearsal-summary-markdown",
            "# AgentLedger Release Rehearsal\n",
        ),
        _write_artifact(
            output_dir,
            "release-metadata.json",
            "release-metadata-json",
            '{"schema_version":"agentledger.release_metadata_check.v1"}\n',
        ),
    ]
    manifest = output_dir / "release-rehearsal-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "agentledger.release_rehearsal_manifest.v1",
                "ok": True,
                "status": "ready",
                "generated_at": "2026-06-15T00:00:00+00:00",
                "repo": "D:\\Projects\\AgentLedger",
                "branch": "master",
                "head": "abcdef1",
                "package_version": "0.1.8a0",
                "release_version": "0.1.8-alpha",
                "release_date": "2026-06-15",
                "output_dir": str(output_dir),
                "manifest_json": str(manifest),
                "artifact_count": len(artifacts),
                "artifacts": artifacts,
                "handling": {
                    "store_outside_repo": True,
                    "manifest_includes_private_evidence": False,
                    "manifest_includes_file_hashes": True,
                    "manifest_hashes_itself": False,
                    "do_not_commit": [".agentledger/", "*.zip", ".agentledger-signing-key"],
                },
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_build_release_rehearsal_receipt_reports_ready(tmp_path: Path) -> None:
    manifest = write_receipt_manifest(tmp_path)

    result = release_rehearsal_receipt.build_release_rehearsal_receipt(manifest)

    assert result["schema_version"] == "agentledger.release_rehearsal_receipt.v1"
    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["verification"]["schema_version"] == "agentledger.release_rehearsal_manifest_verify.v1"
    assert result["doctor"]["schema_version"] == "agentledger.release_artifact_doctor.v1"
    assert result["verified_artifacts"] == 4
    assert [artifact["kind"] for artifact in result["key_artifacts"]] == [
        "draft-release-notes",
        "release-command-index-markdown",
        "release-rehearsal-summary-markdown",
        "release-metadata-json",
    ]
    assert result["next_commands"] == [
        (
            "python scripts/prepare_release.py --version 0.1.8a0 --date 2026-06-15 "
            f"--release-notes-output {manifest.parent}\\agentledger-0.1.8-alpha-release.md --dry-run"
        ),
        (
            "python scripts/prepare_release.py --version 0.1.8a0 --date 2026-06-15 "
            f"--release-notes-output {manifest.parent}\\agentledger-0.1.8-alpha-release.md"
        ),
    ]
    assert result["handling"]["do_not_commit"] == [".agentledger/", "*.zip", ".agentledger-signing-key"]


def test_build_release_rehearsal_receipt_blocks_hash_drift(tmp_path: Path) -> None:
    manifest = write_receipt_manifest(tmp_path)
    metadata = manifest.parent / "release-metadata.json"
    contents = bytearray(metadata.read_bytes())
    contents[-3] = ord("X") if contents[-3] != ord("X") else ord("Y")
    metadata.write_bytes(contents)

    result = release_rehearsal_receipt.build_release_rehearsal_receipt(manifest)

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["next_commands"] == []
    assert any("hash drifted" in error for error in result["errors"])
    assert any("rehearse_release.py" in action for action in result["next_actions"])


def test_main_writes_markdown_receipt(tmp_path: Path, capsys) -> None:
    manifest = write_receipt_manifest(tmp_path)
    output = tmp_path / "release-rehearsal-receipt.md"

    exit_code = release_rehearsal_receipt.main(
        [
            str(manifest),
            "--format",
            "markdown",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out == f"Release rehearsal receipt written: {output}\n"
    markdown = output.read_text(encoding="utf-8")
    assert markdown.startswith("# AgentLedger Release Rehearsal Receipt\n")
    assert "- Verification: ready" in markdown
    assert "- Doctor: ready" in markdown
    assert "## Next Commands" in markdown
    assert "python scripts/prepare_release.py --version 0.1.8a0" in markdown
