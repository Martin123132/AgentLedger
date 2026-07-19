from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


SCHEMA_VERSION = "agentledger.desktop_package.v1"


def _artifact(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {
        "file": path.name,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def _release_label(version: str) -> str:
    match = re.fullmatch(r"(\d+\.\d+\.\d+)a\d+", version)
    return f"v{match.group(1)}-alpha" if match else f"v{version}"


def build_manifest(
    *,
    version: str,
    executable: Path,
    installer: Path | None,
    portable: Path | None,
    source_commit: str | None,
) -> dict[str, object]:
    artifacts: dict[str, object] = {"executable": _artifact(executable)}
    if installer is not None:
        artifacts["installer"] = {"kind": "inno-setup", **_artifact(installer)}
    if portable is not None:
        artifacts["portable"] = {"kind": "zip", **_artifact(portable)}
    return {
        "schema_version": SCHEMA_VERSION,
        "app_id": "agentledger",
        "name": "AgentLedger",
        "version": version,
        "release_label": _release_label(version),
        "channel": "alpha" if "a" in version else "stable",
        "platform": "windows",
        "architecture": "x86_64",
        "install_scope": "per_user",
        "entrypoint": "AgentLedger.exe",
        "publisher": "Martin Ollett",
        "homepage": "https://github.com/Martin123132/AgentLedger",
        "source_commit": source_commit,
        "license": {
            "name": "PolyForm Noncommercial License 1.0.0",
            "commercial_use_requires_permission": True,
            "contact": "glyn@twohandsnetwork.co.uk",
        },
        "privacy": {
            "evidence_local_by_default": True,
            "raw_evidence_uploaded_by_default": False,
        },
        "artifacts": artifacts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a hashed AgentLedger desktop package manifest.")
    parser.add_argument("--version", required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--installer", type=Path)
    parser.add_argument("--portable", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    for path in (args.executable, args.installer, args.portable):
        if path is not None and not path.is_file():
            parser.error(f"artifact not found: {path}")
    payload = build_manifest(
        version=args.version,
        executable=args.executable,
        installer=args.installer,
        portable=args.portable,
        source_commit=args.source_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Desktop manifest written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
