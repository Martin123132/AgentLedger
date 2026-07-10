from __future__ import annotations

import json
from html import escape

from .integrations import summarize_repomori_artifact
from .model import ChangeSet, LedgerReport
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

    if report.change_attribution and report.change_attribution.available:
        attributed = report.change_attribution.changed_during_run.changed_file_count
        preexisting = len(report.change_attribution.preexisting_dirty)
        notes.append(
            f"Boundary attribution found {attributed} persistent file change"
            f"{'s' if attributed != 1 else ''} during the command; "
            f"{preexisting} file{'s were' if preexisting != 1 else ' was'} already dirty."
        )

    if report.environment:
        lock_count = report.environment.dependency_lock_count
        notes.append(
            f"Environment fingerprint captured runtime versions and {lock_count} recognized dependency lock"
            f"{'s' if lock_count != 1 else ''} without environment variables or file contents."
        )

    if report.integrity:
        chain_position = "linked" if report.integrity.previous_run_id else "root"
        notes.append(
            f"History integrity recorded a canonical SHA-256 self-digest at a {chain_position} chain position."
        )

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


def _format_paths(paths: list[str]) -> str:
    return ", ".join(f"`{path}`" for path in paths) if paths else "none"


def _change_set_markdown(changes: ChangeSet) -> list[str]:
    renamed = [f"{item['from']} -> {item['to']}" for item in changes.renamed]
    return [
        f"- Added: {_format_paths(changes.added)}",
        f"- Modified: {_format_paths(changes.modified)}",
        f"- Deleted: {_format_paths(changes.deleted)}",
        f"- Renamed: {_format_paths(renamed)}",
        f"- Restored to clean: {_format_paths(changes.restored)}",
    ]


def _change_set_html(changes: ChangeSet) -> str:
    renamed = [f"{item['from']} -> {item['to']}" for item in changes.renamed]
    items = (
        ("Added", changes.added),
        ("Modified", changes.modified),
        ("Deleted", changes.deleted),
        ("Renamed", renamed),
        ("Restored to clean", changes.restored),
    )
    return "".join(
        f"<li><strong>{label}:</strong> {escape(', '.join(paths) if paths else 'none')}</li>"
        for label, paths in items
    )


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
    attribution = report.change_attribution
    environment = report.environment
    integrity = report.integrity
    attributed_files = attribution.changed_during_run.changed_file_count if attribution and attribution.available else None
    preexisting_files = len(attribution.preexisting_dirty) if attribution else 0
    lines = [
        "# AgentLedger Evidence Report",
        "",
        "## Review Summary",
        "",
        f"- Outcome: `{outcome}`",
        f"- Changed files: `{changed_files}`",
        f"- Changed during command: `{attributed_files if attributed_files is not None else 'n/a'}`",
        f"- Pre-existing dirty files: `{preexisting_files}`",
        f"- Command duration: `{f'{command.duration_seconds:.3f}s' if command and command.duration_seconds is not None else 'n/a'}`",
        f"- Dependency locks fingerprinted: `{environment.dependency_lock_count if environment else 'n/a'}`",
        f"- History integrity: `{'linked' if integrity and integrity.previous_run_id else 'root' if integrity else 'legacy'}`",
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
                f"- Duration: `{f'{command.duration_seconds:.3f}s' if command.duration_seconds is not None else 'n/a'}`",
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

    lines.extend(["## Environment Fingerprint", ""])
    if environment:
        lines.extend(
            [
                f"- Schema: `{environment.schema_version}`",
                f"- AgentLedger: `{environment.agentledger_version}`",
                f"- OS: `{environment.os.get('system', 'unknown')} {environment.os.get('release', 'unknown')} ({environment.os.get('machine', 'unknown')})`",
                f"- Python: `{environment.python.get('implementation', 'unknown')} {environment.python.get('version', 'unknown')}`",
                f"- Git: `{environment.git_version}`",
                f"- Base commit: `{environment.base_commit or 'unborn/unknown'}`",
                f"- Recognized dependency locks: `{environment.dependency_lock_count}`",
                f"- Fingerprint limit: `{environment.dependency_lock_limit}`",
                f"- Lock list truncated: `{environment.dependency_locks_truncated}`",
                f"- Environment variables included: `{environment.privacy.get('environment_variables_included', False)}`",
                f"- Executable paths included: `{environment.privacy.get('executable_paths_included', False)}`",
                f"- Hostnames included: `{environment.privacy.get('hostnames_included', False)}`",
                f"- File contents included: `{environment.privacy.get('file_contents_included', False)}`",
                "",
                "### Dependency Lock Hashes",
                "",
            ]
        )
        if environment.dependency_locks:
            for lock in environment.dependency_locks:
                lines.append(
                    f"- `{lock.path}` ({lock.ecosystem}, {lock.size} bytes): `sha256:{lock.sha256}`"
                )
            lines.append("")
        else:
            lines.extend(["No recognized tracked dependency locks were found.", ""])
    else:
        lines.extend(["Unavailable in this legacy report.", ""])

    lines.extend(["## History Integrity", ""])
    if integrity:
        lines.extend(
            [
                f"- Schema: `{integrity.schema_version}`",
                f"- Algorithm: `{integrity.algorithm}`",
                f"- Canonicalization: `{integrity.canonicalization}`",
                f"- Report SHA-256: `{integrity.report_sha256}`",
                f"- Previous run: `{integrity.previous_run_id or 'none (chain root)'}`",
                f"- Previous report SHA-256: `{integrity.previous_report_sha256 or 'none (chain root)'}`",
                "",
                "The digest covers canonical report JSON except its own digest field. "
                "This detects later edits and broken links but does not authenticate an unsigned history.",
                "",
            ]
        )
    else:
        lines.extend(["Unavailable in this legacy report.", ""])

    lines.extend(["## Command Change Attribution", ""])
    if attribution and attribution.available:
        lines.extend(
            [
                f"- Basis: `{', '.join(attribution.basis)}`",
                f"- Persistent files changed during command: `{attributed_files}`",
                f"- Git HEAD changed: `{attribution.head_changed}`",
                f"- Pre-existing dirty: {_format_paths(attribution.preexisting_dirty)}",
                f"- Unchanged pre-existing dirt: {_format_paths(attribution.unchanged_preexisting)}",
                "",
                "### Combined Boundary Changes",
                "",
                *_change_set_markdown(attribution.changed_during_run),
                "",
                "### Committed During Command",
                "",
                *_change_set_markdown(attribution.committed_during_run),
                "",
                "### Working-Tree Changes During Command",
                "",
                *_change_set_markdown(attribution.working_tree_during_run),
                "",
                "### Attribution Limits",
                "",
                *[f"- {item}" for item in attribution.limitations],
                "",
            ]
        )
    else:
        lines.extend(["Unavailable for snapshot-only evidence; no command boundary was recorded.", ""])

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
    attribution = report.change_attribution
    environment = report.environment
    integrity = report.integrity
    attributed_files = attribution.changed_during_run.changed_file_count if attribution and attribution.available else None
    preexisting_files = len(attribution.preexisting_dirty) if attribution else 0
    if attribution and attribution.available:
        attribution_html = f"""
  <p><strong>Basis:</strong> <code>{escape(', '.join(attribution.basis))}</code><br>
  <strong>Git HEAD changed:</strong> <code>{str(attribution.head_changed).lower()}</code><br>
  <strong>Pre-existing dirty:</strong> <code>{escape(', '.join(attribution.preexisting_dirty) or 'none')}</code><br>
  <strong>Unchanged pre-existing dirt:</strong> <code>{escape(', '.join(attribution.unchanged_preexisting) or 'none')}</code></p>
  <h3>Combined Boundary Changes</h3>
  <ul>{_change_set_html(attribution.changed_during_run)}</ul>
  <h3>Committed During Command</h3>
  <ul>{_change_set_html(attribution.committed_during_run)}</ul>
  <h3>Working-Tree Changes During Command</h3>
  <ul>{_change_set_html(attribution.working_tree_during_run)}</ul>
  <h3>Attribution Limits</h3>
  <ul>{''.join(f'<li>{escape(item)}</li>' for item in attribution.limitations)}</ul>"""
    else:
        attribution_html = "<p>Unavailable for snapshot-only evidence; no command boundary was recorded.</p>"
    duration_text = f"{command.duration_seconds:.3f}s" if command and command.duration_seconds is not None else "n/a"
    if environment:
        lock_items = "".join(
            f"<li><code>{escape(lock.path)}</code> ({escape(lock.ecosystem)}, {lock.size} bytes): "
            f"<code>sha256:{escape(lock.sha256)}</code></li>"
            for lock in environment.dependency_locks
        ) or "<li>No recognized tracked dependency locks were found.</li>"
        environment_html = f"""
  <p><strong>Schema:</strong> <code>{escape(environment.schema_version)}</code><br>
  <strong>AgentLedger:</strong> <code>{escape(environment.agentledger_version)}</code><br>
  <strong>OS:</strong> <code>{escape(environment.os.get('system', 'unknown'))} {escape(environment.os.get('release', 'unknown'))} ({escape(environment.os.get('machine', 'unknown'))})</code><br>
  <strong>Python:</strong> <code>{escape(environment.python.get('implementation', 'unknown'))} {escape(environment.python.get('version', 'unknown'))}</code><br>
  <strong>Git:</strong> <code>{escape(environment.git_version)}</code><br>
  <strong>Base commit:</strong> <code>{escape(environment.base_commit or 'unborn/unknown')}</code><br>
  <strong>Recognized dependency locks:</strong> <code>{environment.dependency_lock_count}</code><br>
  <strong>Fingerprint limit:</strong> <code>{environment.dependency_lock_limit}</code><br>
  <strong>Lock list truncated:</strong> <code>{str(environment.dependency_locks_truncated).lower()}</code></p>
  <h3>Privacy Boundary</h3>
  <ul>
    <li>Environment variables included: <code>{str(environment.privacy.get('environment_variables_included', False)).lower()}</code></li>
    <li>Executable paths included: <code>{str(environment.privacy.get('executable_paths_included', False)).lower()}</code></li>
    <li>Hostnames included: <code>{str(environment.privacy.get('hostnames_included', False)).lower()}</code></li>
    <li>File contents included: <code>{str(environment.privacy.get('file_contents_included', False)).lower()}</code></li>
  </ul>
  <h3>Dependency Lock Hashes</h3>
  <ul>{lock_items}</ul>"""
    else:
        environment_html = "<p>Unavailable in this legacy report.</p>"
    if integrity:
        integrity_html = f"""
  <p><strong>Schema:</strong> <code>{escape(integrity.schema_version)}</code><br>
  <strong>Algorithm:</strong> <code>{escape(integrity.algorithm)}</code><br>
  <strong>Canonicalization:</strong> <code>{escape(integrity.canonicalization)}</code><br>
  <strong>Report SHA-256:</strong> <code>{escape(integrity.report_sha256)}</code><br>
  <strong>Previous run:</strong> <code>{escape(integrity.previous_run_id or 'none (chain root)')}</code><br>
  <strong>Previous report SHA-256:</strong> <code>{escape(integrity.previous_report_sha256 or 'none (chain root)')}</code></p>
  <p>This detects later report edits and broken links but does not authenticate an unsigned history.</p>"""
        integrity_status = "linked" if integrity.previous_run_id else "root"
    else:
        integrity_html = "<p>Unavailable in this legacy report.</p>"
        integrity_status = "legacy"
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
    <div class="box"><strong>Command Duration</strong><br><code>{escape(duration_text)}</code></div>
    <div class="box"><strong>Test Command</strong><br><code>{escape(test_text)}</code></div>
    <div class="box"><strong>Changed Files</strong><br><code>{changed_files}</code></div>
    <div class="box"><strong>Changed During Command</strong><br><code>{attributed_files if attributed_files is not None else 'n/a'}</code></div>
    <div class="box"><strong>Pre-existing Dirty Files</strong><br><code>{preexisting_files}</code></div>
    <div class="box"><strong>Dependency Locks</strong><br><code>{environment.dependency_lock_count if environment else 'n/a'}</code></div>
    <div class="box"><strong>History Integrity</strong><br><code>{escape(integrity_status)}</code></div>
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
  <h2>Environment Fingerprint</h2>
  {environment_html}
  <h2>History Integrity</h2>
  {integrity_html}
  <h2>Command Change Attribution</h2>
  {attribution_html}
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
