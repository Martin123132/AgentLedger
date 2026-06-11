from __future__ import annotations

import json
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
