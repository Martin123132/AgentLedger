from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from . import __version__
from .model import utc_now_iso
from .report_reader import (
    artifact_status_counts,
    changed_file_count,
    command_exit_code,
    command_test_framework,
    report_command_text,
    tokometer_summary,
)


RECEIPT_SCHEMA = "agentledger.receipt.v1"
RECEIPT_JSON = "agentledger-receipt.json"
RECEIPT_MARKDOWN = "agentledger-receipt.md"
RECEIPT_HTML = "agentledger-receipt.html"


def receipt_paths(run_dir: Path) -> dict[str, str]:
    return {
        "markdown": str(run_dir / RECEIPT_MARKDOWN),
        "json": str(run_dir / RECEIPT_JSON),
        "html": str(run_dir / RECEIPT_HTML),
    }


def build_receipt_payload(
    *,
    repo: Path,
    out_root: Path,
    run_dir: Path,
    report: dict[str, Any],
    check: dict[str, Any],
    capture_exit_code: int,
    command: list[str],
    privacy_mode: str,
    paths: dict[str, str | None],
    strict: bool,
    signature_requested: bool,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    errors = errors or []
    check_status = str(check.get("status") or "unknown")
    blocking = check.get("blocking_rules") if isinstance(check.get("blocking_rules"), list) else []
    warnings = check.get("warning_rules") if isinstance(check.get("warning_rules"), list) else []
    artifacts = [artifact for artifact in report.get("artifacts") or [] if isinstance(artifact, dict)]
    artifact_ok, artifact_warn = artifact_status_counts(artifacts)
    exit_code = command_exit_code(report)
    changed_files = changed_file_count(report)
    receipt_file_paths = receipt_paths(run_dir)
    verification_state = "pending"
    if signature_requested:
        verification_state = "pending_signature"
    acceptance = _acceptance_status(check_status, strict, capture_exit_code, errors)
    return {
        "schema_version": RECEIPT_SCHEMA,
        "ok": acceptance == "ready",
        "acceptance": acceptance,
        "generated_at": utc_now_iso(),
        "agentledger_version": f"agentledger {__version__}",
        "repo": str(repo),
        "out": str(out_root),
        "run_dir": str(run_dir),
        "command": {
            "requested": command,
            "captured": report_command_text(report),
            "exit_code": exit_code,
            "capture_exit_code": capture_exit_code,
            "test_detected": command_test_framework(report) != "n/a",
            "test_framework": command_test_framework(report),
        },
        "privacy_mode": privacy_mode,
        "review": {
            "status": check_status,
            "summary": str(check.get("summary") or ""),
            "strict": strict,
            "blocking_rules": blocking,
            "warning_rules": warnings,
            "changed_files": changed_files,
            "artifact_counts": {"ok": artifact_ok, "warn": artifact_warn},
            "tokometer": tokometer_summary(report),
        },
        "evidence": {
            "markdown_report": paths.get("markdown"),
            "json_report": paths.get("json"),
            "html_report": paths.get("html"),
            "bundle": paths.get("zip"),
            "receipt": receipt_file_paths,
            "bundle_verification": verification_state,
            "signature_requested": signature_requested,
        },
        "integrations": [
            {
                "name": str(artifact.get("name") or "unnamed"),
                "ok": bool(artifact.get("ok")),
                "summary": str(artifact.get("summary") or ""),
                "output_path": artifact.get("output_path"),
            }
            for artifact in artifacts
        ],
        "next_actions": _next_actions(
            acceptance=acceptance,
            check_status=check_status,
            warnings=warnings,
            blocking=blocking,
            signature_requested=signature_requested,
        ),
        "handling": [
            "Review the receipt and Markdown evidence report before accepting the run.",
            "Keep raw .agentledger evidence, command transcripts, zip bundles, signing keys, private paths, and source-private details local unless explicitly approved for sharing.",
            "Share the receipt Markdown/HTML first; share the zip bundle only when the reviewer needs raw evidence.",
        ],
        "errors": errors,
    }


def write_receipt_files(payload: dict[str, Any], run_dir: Path) -> dict[str, str]:
    paths = receipt_paths(run_dir)
    markdown_path = Path(paths["markdown"])
    json_path = Path(paths["json"])
    html_path = Path(paths["html"])
    markdown_path.write_text(format_receipt_markdown(payload), encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(format_receipt_html(payload), encoding="utf-8")
    return paths


def format_receipt_markdown(payload: dict[str, Any]) -> str:
    review = payload.get("review") if isinstance(payload.get("review"), dict) else {}
    command = payload.get("command") if isinstance(payload.get("command"), dict) else {}
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    artifacts = payload.get("integrations") if isinstance(payload.get("integrations"), list) else []
    next_actions = payload.get("next_actions") if isinstance(payload.get("next_actions"), list) else []
    handling = payload.get("handling") if isinstance(payload.get("handling"), list) else []
    errors = payload.get("errors") if isinstance(payload.get("errors"), list) else []
    lines = [
        "# AgentLedger Run Receipt",
        "",
        "## Decision",
        "",
        f"- Acceptance: `{payload.get('acceptance') or 'unknown'}`",
        f"- Review status: `{review.get('status') or 'unknown'}`",
        f"- Summary: {review.get('summary') or 'No summary available.'}",
        f"- Strict mode: `{review.get('strict')}`",
        "",
        "## What Happened",
        "",
        f"- Requested command: `{_command_text(command.get('requested'))}`",
        f"- Captured command: `{command.get('captured') or 'n/a'}`",
        f"- Command exit code: `{_value(command.get('exit_code'))}`",
        f"- Capture exit code: `{_value(command.get('capture_exit_code'))}`",
        f"- Test evidence: `{command.get('test_framework') or 'n/a'}`",
        f"- Changed files: `{_value(review.get('changed_files'))}`",
        f"- Privacy mode: `{payload.get('privacy_mode') or 'n/a'}`",
        "",
        "## Evidence",
        "",
        f"- Markdown report: `{evidence.get('markdown_report') or 'missing'}`",
        f"- JSON report: `{evidence.get('json_report') or 'missing'}`",
        f"- HTML report: `{evidence.get('html_report') or 'missing'}`",
        f"- Zip bundle: `{evidence.get('bundle') or 'missing'}`",
        f"- Bundle verification: `{evidence.get('bundle_verification') or 'unknown'}`",
        f"- Signature requested: `{evidence.get('signature_requested')}`",
        "",
        "## Receipt Files",
        "",
    ]
    receipt = evidence.get("receipt") if isinstance(evidence.get("receipt"), dict) else {}
    for label in ("markdown", "json", "html"):
        lines.append(f"- {label}: `{receipt.get(label) or 'missing'}`")
    lines.extend(["", "## Integrations", ""])
    if artifacts:
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            state = "ok" if artifact.get("ok") else "warn"
            lines.append(f"- `{artifact.get('name') or 'unnamed'}`: {state}. {artifact.get('summary') or ''}")
            if artifact.get("output_path"):
                lines.append(f"  Output: `{artifact['output_path']}`")
    else:
        lines.append("- No optional integration artifacts were recorded.")
    lines.extend(["", "## Next Actions", ""])
    lines.extend([f"- {item}" for item in next_actions] or ["- Review the Markdown report before accepting the run."])
    lines.extend(["", "## Handling", ""])
    lines.extend([f"- {item}" for item in handling])
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend([f"- {item}" for item in errors])
    return "\n".join(lines) + "\n"


def format_receipt_html(payload: dict[str, Any]) -> str:
    markdown = format_receipt_markdown(payload)
    blocks = []
    in_list = False
    in_code = False
    for line in markdown.splitlines():
        if line.startswith("# "):
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<h1>{escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<h2>{escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{_inline_code_html(line[2:])}</li>")
        elif line.startswith("  Output:"):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append(f"<li>{_inline_code_html(line.strip())}</li>")
        elif line.startswith("```"):
            in_code = not in_code
        elif line.strip():
            tag = "pre" if in_code else "p"
            blocks.append(f"<{tag}>{escape(line)}</{tag}>")
    if in_list:
        blocks.append("</ul>")
    status = str(payload.get("acceptance") or "unknown")
    badge_class = "ok" if status == "ready" else "warn" if status == "review" else "block"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentLedger Run Receipt</title>
  <style>
    :root {{
      --ink: #182234;
      --muted: #5c6878;
      --line: #d8dee8;
      --panel: #f8fafc;
      --ok: #176b49;
      --warn: #9d5a09;
      --block: #9b241f;
      --accent: #245d8f;
    }}
    body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 2rem; color: var(--ink); line-height: 1.45; }}
    main {{ max-width: 980px; margin: 0 auto; }}
    h1, h2 {{ line-height: 1.1; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .badge {{ display: inline-block; padding: 0.25rem 0.6rem; border-radius: 999px; color: white; font-weight: 700; }}
    .ok {{ background: var(--ok); }}
    .warn {{ background: var(--warn); }}
    .block {{ background: var(--block); }}
    .summary {{ border-left: 4px solid var(--accent); padding-left: 1rem; margin: 1rem 0 1.4rem; color: var(--muted); }}
    section {{ border-top: 1px solid var(--line); padding-top: 0.6rem; }}
    code {{ font-family: Consolas, Monaco, monospace; background: var(--panel); padding: 0.1rem 0.25rem; border-radius: 4px; }}
    li {{ margin: 0.25rem 0; }}
  </style>
</head>
<body>
<main>
  <p><span class="badge {badge_class}">{escape(status)}</span></p>
  <div class="summary">Local-first receipt for one AI-assisted repository work session.</div>
  {"".join(blocks)}
</main>
</body>
</html>
"""


def _acceptance_status(check_status: str, strict: bool, capture_exit_code: int, errors: list[str]) -> str:
    if errors or capture_exit_code not in (0, 1):
        return "blocked"
    if check_status == "pass":
        return "ready"
    if check_status == "warn" and not strict:
        return "review"
    return "blocked"


def _next_actions(
    *,
    acceptance: str,
    check_status: str,
    warnings: list[Any],
    blocking: list[Any],
    signature_requested: bool,
) -> list[str]:
    if acceptance == "blocked":
        actions = ["Fix blockers, rerun the task, and create a fresh receipt."]
        if blocking:
            actions.append("Start with the blocking rules listed in the review section.")
        return actions
    actions = ["Read the receipt, then open the Markdown evidence report before accepting the run."]
    if check_status == "warn" or warnings:
        actions.append("Review warning rules and explicitly accept them before using the result.")
    if signature_requested:
        actions.append("Verify the signed bundle with the shared signing key before archiving it.")
    else:
        actions.append("Treat the unsigned bundle as local evidence unless a reviewer accepts unsigned handoff.")
    actions.append("Keep the raw bundle private unless the reviewer needs it.")
    return actions


def _command_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value) if value else "n/a"
    if value is None:
        return "n/a"
    return str(value)


def _value(value: Any) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _inline_code_html(text: str) -> str:
    parts = text.split("`")
    rendered = []
    for index, part in enumerate(parts):
        if index % 2:
            rendered.append(f"<code>{escape(part)}</code>")
        else:
            rendered.append(escape(part))
    return "".join(rendered)
