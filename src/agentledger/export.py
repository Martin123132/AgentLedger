from __future__ import annotations

import json
from html import escape

from .integrations import summarize_repomori_artifact
from .model import LedgerReport
from .report_reader import changed_file_count, tokometer_summary


def _command_text(report: LedgerReport) -> str:
    return " ".join(report.command.command) if report.command else "No command executed"


def _run_outcome(report: LedgerReport) -> str:
    if report.command is None:
        return "snapshot only"
    return "command passed" if report.command.exit_code == 0 else "command failed"


def _artifact_counts(report: LedgerReport) -> tuple[int, int]:
    return (
        sum(1 for artifact in report.artifacts if artifact.ok),
        sum(1 for artifact in report.artifacts if not artifact.ok),
    )


def _dirty_text(status: str) -> str:
    return "yes" if status else "no"


def _diff_text(report: LedgerReport) -> str:
    if report.after.diff:
        return report.after.diff
    if report.privacy_mode == "summary":
        return "Full diff omitted by privacy-mode summary."
    return ""


def _review_notes(report: LedgerReport, changed_files: int, artifact_warn: int) -> list[str]:
    notes: list[str] = []
    command = report.command
    if command is None:
        notes.append("Snapshot-only run; use this as repository state evidence, not command completion evidence.")
    elif command.exit_code != 0:
        notes.append("Command failed; inspect stderr/stdout before accepting the work.")
    elif command.test_detected:
        notes.append(f"Verification command detected: {command.test_framework or 'test command'}.")
    else:
        notes.append("No recognized test command detected; run a verification command before accepting the work.")

    if changed_files:
        suffix = "file" if changed_files == 1 else "files"
        notes.append(f"Review {changed_files} changed {suffix} in the diff/status output.")
    else:
        notes.append("No changed files were detected after the run.")

    if artifact_warn:
        suffix = "warning" if artifact_warn == 1 else "warnings"
        notes.append(f"Resolve or explicitly accept {artifact_warn} optional artifact {suffix}.")
    else:
        notes.append("No optional artifact warnings were recorded.")

    if report.warnings:
        suffix = "warning" if len(report.warnings) == 1 else "warnings"
        notes.append(f"Read {len(report.warnings)} report-level {suffix} before sharing the bundle.")

    if report.privacy_mode == "summary":
        notes.append("Summary privacy mode omits command transcript content and full diffs from reports.")

    return notes


def write_json(report: LedgerReport, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")


def write_markdown(report: LedgerReport, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    command = report.command
    changed_files = changed_file_count(report.to_dict())
    artifact_ok, artifact_warn = _artifact_counts(report)
    before_dirty = _dirty_text(report.before.status)
    after_dirty = _dirty_text(report.after.status)
    outcome = _run_outcome(report)
    command_text = _command_text(report)
    zip_path = path.parent.with_suffix(".zip")
    json_path = path.parent / "agentledger-report.json"
    html_path = path.parent / "agentledger-report.html"
    review_notes = _review_notes(report, changed_files, artifact_warn)
    lines = [
        "# AgentLedger Evidence Report",
        "",
        "## Review Summary",
        "",
        f"- Outcome: `{outcome}`",
        f"- Changed files: `{changed_files}`",
        f"- Artifacts: `{artifact_ok} ok / {artifact_warn} warn`",
        f"- Evidence bundle: `{zip_path}`",
        f"- Command: `{command_text}`",
        "",
        "## Review Notes",
        "",
        *[f"- {note}" for note in review_notes],
        "",
        "## Human Review Checklist",
        "",
        "- [ ] Confirm the command matches the intended task.",
        "- [ ] Review changed files and diff for unexpected edits.",
        "- [ ] Open stdout/stderr transcripts if command output matters.",
        "- [ ] Check artifact warnings before trusting optional integrations.",
        "",
        "## Evidence Files",
        "",
        f"- Markdown report: `{path}`",
        f"- JSON report: `{json_path}`",
        f"- HTML report: `{html_path}`",
        f"- Evidence bundle: `{zip_path}`",
        "",
        "## Run Metadata",
        "",
        f"- Run ID: `{report.run_id}`",
        f"- Started: `{report.started_at}`",
        f"- Ended: `{report.ended_at}`",
        f"- Repo: `{report.target_repo}`",
        f"- Branch: `{report.after.branch or 'detached/unknown'}`",
        f"- Privacy mode: `{report.privacy_mode}`",
        f"- Before dirty: `{before_dirty}`",
        f"- After dirty: `{after_dirty}`",
        "",
        "## Command",
        "",
    ]
    if command:
        lines.extend(
            [
                f"- Command: `{command_text}`",
                f"- Exit code: `{command.exit_code}`",
                f"- Test detected: `{command.test_detected}`",
                f"- Test framework: `{command.test_framework or 'n/a'}`",
                f"- Started: `{command.started_at}`",
                f"- Ended: `{command.ended_at}`",
                f"- Stdout: `{command.stdout_path or 'n/a'}`",
                f"- Stderr: `{command.stderr_path or 'n/a'}`",
                "",
            ]
        )
        if command.stdout_tail or command.stderr_tail:
            lines.extend(["### Command Tail", ""])
            if command.stdout_tail:
                lines.extend(["Stdout:", "", "```text", command.stdout_tail, "```", ""])
            if command.stderr_tail:
                lines.extend(["Stderr:", "", "```text", command.stderr_tail, "```", ""])
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
            if artifact.name.startswith("repomori_"):
                repomori_summary = summarize_repomori_artifact(artifact.output_path)
                if repomori_summary:
                    lines.append(f"  RepoMori: {repomori_summary}")
            if artifact.output_path:
                lines.append(f"  Output: `{artifact.output_path}`")
        lines.append("")

    if report.warnings:
        lines.extend(["## Warnings", ""])
        for warning in report.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.extend(["## Diff", "", "```diff", _diff_text(report), "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_html(report: LedgerReport, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    command = report.command
    command_text = _command_text(report)
    exit_code = str(command.exit_code) if command else "n/a"
    test_text = f"{command.test_framework or 'detected'}" if command and command.test_detected else "not detected"
    changed_files = changed_file_count(report.to_dict())
    artifact_ok, artifact_warn = _artifact_counts(report)
    outcome = _run_outcome(report)
    outcome_class = "ok" if outcome in {"command passed", "snapshot only"} else "warn"
    tokometer_text = tokometer_summary(report.to_dict()) or "n/a"
    artifact_items = []
    for artifact in report.artifacts:
        repomori_summary = summarize_repomori_artifact(artifact.output_path) if artifact.name.startswith("repomori_") else None
        artifact_items.append(
            f"<li><strong>{escape(artifact.name)}</strong>: "
            f"{'ok' if artifact.ok else 'warn'} - {escape(artifact.summary)}"
            + (f"<br>RepoMori: {escape(repomori_summary)}" if repomori_summary else "")
            + (f"<br><code>{escape(artifact.output_path)}</code>" if artifact.output_path else "")
            + "</li>"
        )
    artifacts = "\n".join(artifact_items)
    warnings = "\n".join(f"<li>{escape(warning)}</li>" for warning in report.warnings)
    review_notes = "\n".join(f"<li>{escape(note)}</li>" for note in _review_notes(report, changed_files, artifact_warn))
    zip_path = path.parent.with_suffix(".zip")
    json_path = path.parent / "agentledger-report.json"
    checklist = "\n".join(
        f"<li>{escape(item)}</li>"
        for item in (
            "Confirm the command matches the intended task.",
            "Review changed files and diff for unexpected edits.",
            "Open stdout/stderr transcripts if command output matters.",
            "Check artifact warnings before trusting optional integrations.",
        )
    )
    command_tail_parts = []
    if command and command.stdout_tail:
        command_tail_parts.extend(["Stdout:", command.stdout_tail])
    if command and command.stderr_tail:
        command_tail_parts.extend(["Stderr:", command.stderr_tail])
    command_tail = "\n\n".join(command_tail_parts) if command_tail_parts else "No command tail captured."
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AgentLedger Evidence Report</title>
  <style>
    :root {{
      --ink: #172033;
      --muted: #526071;
      --line: #d7dde6;
      --panel: #f7f9fb;
      --ok: #176b49;
      --warn: #a33f16;
      --accent: #245d8f;
    }}
    body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 2rem; line-height: 1.45; color: var(--ink); background: #ffffff; }}
    main {{ max-width: 1100px; margin: 0 auto; }}
    h1, h2 {{ line-height: 1.1; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .lede {{ margin-top: 0; color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 0.75rem; }}
    .box {{ border: 1px solid var(--line); border-radius: 6px; padding: 0.8rem; background: var(--panel); }}
    .summary {{ border-left: 4px solid var(--accent); padding-left: 1rem; margin: 1rem 0 1.25rem; }}
    .badge {{ display: inline-block; border-radius: 999px; padding: 0.2rem 0.55rem; color: #ffffff; font-size: 0.85rem; font-weight: 700; }}
    .ok {{ background: var(--ok); }}
    .warn {{ background: var(--warn); }}
    .checklist {{ columns: 2 260px; padding-left: 1.25rem; }}
    code, pre {{ font-family: Consolas, Monaco, monospace; }}
    pre {{ overflow: auto; border: 1px solid var(--line); border-radius: 6px; padding: 1rem; background: #f6f8fa; }}
    .muted {{ color: var(--muted); }}
  </style>
</head>
<body>
<main>
  <h1>AgentLedger Evidence Report</h1>
  <p class="lede">Local evidence for one AI-assisted repository work session.</p>
  <section class="summary">
    <p><span class="badge {outcome_class}">{escape(outcome)}</span></p>
    <p><strong>Review focus:</strong> inspect the command, changed files, artifact warnings, and evidence bundle before accepting the work.</p>
  </section>
  <h2>Review Notes</h2>
  <ul>{review_notes}</ul>
  <section class="grid">
    <div class="box"><strong>Run ID</strong><br><code>{escape(report.run_id)}</code></div>
    <div class="box"><strong>Repo</strong><br><code>{escape(report.target_repo)}</code></div>
    <div class="box"><strong>Branch</strong><br><code>{escape(report.after.branch or 'detached/unknown')}</code></div>
    <div class="box"><strong>Privacy Mode</strong><br><code>{escape(report.privacy_mode)}</code></div>
    <div class="box"><strong>Exit Code</strong><br><code>{escape(exit_code)}</code></div>
    <div class="box"><strong>Test Command</strong><br><code>{escape(test_text)}</code></div>
    <div class="box"><strong>Changed Files</strong><br><code>{changed_files}</code></div>
    <div class="box"><strong>Artifact Results</strong><br><code>{artifact_ok} ok / {artifact_warn} warn</code></div>
    <div class="box"><strong>Tokometer</strong><br><code>{escape(tokometer_text)}</code></div>
  </section>
  <h2>Human Review Checklist</h2>
  <ul class="checklist">{checklist}</ul>
  <h2>Evidence Files</h2>
  <ul>
    <li>Markdown report: <code>{escape(str(path))}</code></li>
    <li>JSON report: <code>{escape(str(json_path))}</code></li>
    <li>HTML report: <code>{escape(str(path.parent / 'agentledger-report.html'))}</code></li>
    <li>Evidence bundle: <code>{escape(str(zip_path))}</code></li>
  </ul>
  <h2>Command</h2>
  <pre>{escape(command_text)}</pre>
  <p class="muted">Stdout transcript: <code>{escape(command.stdout_path if command and command.stdout_path else 'n/a')}</code><br>
  Stderr transcript: <code>{escape(command.stderr_path if command and command.stderr_path else 'n/a')}</code></p>
  <h2>Command Tail</h2>
  <pre>{escape(command_tail)}</pre>
  <h2>Changes</h2>
  <pre>{escape(report.after.diff_stat or 'No tracked file diff.')}</pre>
  <h2>Artifacts</h2>
  <ul>{artifacts or '<li>No optional artifacts.</li>'}</ul>
  <h2>Warnings</h2>
  <ul>{warnings or '<li>No warnings.</li>'}</ul>
  <h2>Diff</h2>
  <pre>{escape(_diff_text(report))}</pre>
</main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
