from __future__ import annotations

import json
from html import escape
from pathlib import Path

from .model import LedgerReport


def write_json(report: LedgerReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")


def write_markdown(report: LedgerReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = report.command
    before_dirty = "yes" if report.before.status else "no"
    after_dirty = "yes" if report.after.status else "no"
    lines = [
        "# AgentLedger Evidence Report",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Started: `{report.started_at}`",
        f"- Ended: `{report.ended_at}`",
        f"- Repo: `{report.target_repo}`",
        f"- Branch: `{report.after.branch or 'detached/unknown'}`",
        f"- Before dirty: `{before_dirty}`",
        f"- After dirty: `{after_dirty}`",
        "",
        "## Command",
        "",
    ]
    if command:
        lines.extend(
            [
                f"- Command: `{' '.join(command.command)}`",
                f"- Exit code: `{command.exit_code}`",
                f"- Started: `{command.started_at}`",
                f"- Ended: `{command.ended_at}`",
                "",
            ]
        )
    else:
        lines.append("No command was executed; this report captured repository state only.\n")

    lines.extend(["## Changes", ""])
    lines.append("```text")
    lines.append(report.after.diff_stat or "No tracked file diff.")
    lines.append("```")
    lines.append("")

    if report.artifacts:
        lines.extend(["## Artifacts", ""])
        for artifact in report.artifacts:
            state = "ok" if artifact.ok else "warn"
            lines.append(f"- `{artifact.name}`: {state}. {artifact.summary}")
            if artifact.output_path:
                lines.append(f"  Output: `{artifact.output_path}`")
        lines.append("")

    if report.warnings:
        lines.extend(["## Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.extend(["## Diff", "", "```diff", report.after.diff or "", "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_html(report: LedgerReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    command = report.command
    command_text = " ".join(command.command) if command else "No command executed"
    exit_code = str(command.exit_code) if command else "n/a"
    artifacts = "\n".join(
        f"<li><strong>{escape(artifact.name)}</strong>: "
        f"{'ok' if artifact.ok else 'warn'} - {escape(artifact.summary)}"
        + (f"<br><code>{escape(artifact.output_path)}</code>" if artifact.output_path else "")
        + "</li>"
        for artifact in report.artifacts
    )
    warnings = "\n".join(f"<li>{escape(warning)}</li>" for warning in report.warnings)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentLedger Evidence Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.45; color: #18202a; }}
    main {{ max-width: 1100px; margin: 0 auto; }}
    h1, h2 {{ line-height: 1.1; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; }}
    .box {{ border: 1px solid #d8dee8; border-radius: 6px; padding: 0.8rem; background: #fafbfc; }}
    code, pre {{ font-family: Consolas, Monaco, monospace; }}
    pre {{ overflow: auto; border: 1px solid #d8dee8; border-radius: 6px; padding: 1rem; background: #f6f8fa; }}
  </style>
</head>
<body>
<main>
  <h1>AgentLedger Evidence Report</h1>
  <section class="grid">
    <div class="box"><strong>Run ID</strong><br><code>{escape(report.run_id)}</code></div>
    <div class="box"><strong>Repo</strong><br><code>{escape(report.target_repo)}</code></div>
    <div class="box"><strong>Branch</strong><br><code>{escape(report.after.branch or 'detached/unknown')}</code></div>
    <div class="box"><strong>Exit Code</strong><br><code>{escape(exit_code)}</code></div>
  </section>
  <h2>Command</h2>
  <pre>{escape(command_text)}</pre>
  <h2>Changes</h2>
  <pre>{escape(report.after.diff_stat or 'No tracked file diff.')}</pre>
  <h2>Artifacts</h2>
  <ul>{artifacts or '<li>No optional artifacts.</li>'}</ul>
  <h2>Warnings</h2>
  <ul>{warnings or '<li>No warnings.</li>'}</ul>
  <h2>Diff</h2>
  <pre>{escape(report.after.diff or '')}</pre>
</main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
