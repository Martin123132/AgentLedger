# AgentLedger

Local-first black box recorder for AI coding agents.

[![CI](https://github.com/Martin123132/AgentLedger/actions/workflows/ci.yml/badge.svg)](https://github.com/Martin123132/AgentLedger/actions/workflows/ci.yml)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue)](LICENSE)

Source-available for non-commercial use under the PolyForm Noncommercial
License 1.0.0. Commercial use requires separate permission.

AgentLedger captures the boring evidence teams need when agents spend tokens,
run commands, touch repositories, and claim work is done:

- before/after git state
- command execution evidence
- changed files and diffs
- best-effort redaction for obvious secrets in captured text
- RepoMori snapshots and handoff packs when available
- Jester diff safety gate when available
- Tokometer local usage summary when available
- Markdown, JSON, and HTML audit reports
- zip evidence bundle

The first product wedge is intentionally simple:

```powershell
agentledger run --repo C:\path\to\repo -- npm test
```

That writes a timestamped evidence folder under `.agentledger/` with:

```text
agentledger-report.md
agentledger-report.json
agentledger-report.html
artifacts/
```

It also writes a sibling `.zip` bundle for easy handoff.
The Markdown and HTML reports start with a review summary and a short human
checklist so the latest run can be triaged quickly before accepting the work.

## Why This Exists

AI coding agents are now doing real work, changing code, and burning money, but
the evidence trail is scattered across chat logs, terminals, git diffs, and
local tool state. AgentLedger turns one agent work session into a compact audit
record a human, buyer, teammate, or another agent can inspect.

Short pitch:

```text
The black box recorder for AI coding agents.
```

Company pitch:

```text
Local-first control tools for AI coding agents: usage metering, repo memory,
execution evidence, and eval gates.
```

## Quick Start

From this checkout:

```powershell
python -m pip install -e ".[dev]"
agentledger --version
python -m agentledger doctor --repo .
python -m agentledger run --repo . -- python -c "print('hello from AgentLedger')"
```

After a run:

```powershell
Get-Content .agentledger\latest.txt
```

Open the `agentledger-report.md` inside that latest run folder.

Five-minute public alpha check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

Manual review loop:

```powershell
python -m agentledger run --repo . --out .agentledger --no-repomori --no-jester --no-tokometer -- python -c "print('agentledger smoke')"
python -m agentledger open-latest --out .agentledger
python -m agentledger history --out .agentledger
$run = (Get-Content .agentledger\latest.txt).Trim()
python -m agentledger inspect-report $run
python -m agentledger check --allow-warnings $run
python -m agentledger verify-bundle "${run}.zip"
```

Use summary privacy mode when you want counts, paths, and metadata without full
command transcripts or full diffs in the report/bundle:

```powershell
python -m agentledger run --repo . --privacy-mode summary -- python -m pytest
```

You can also set repo defaults in `.agentledger.toml`. This repository includes
a public-alpha example at `.agentledger.toml`:

```toml
privacy_mode = "summary"
out = ".agentledger"
repomori = false
jester = false
tokometer = false
zip = true
check_require_tests = true
check_dirty = "warn"
check_max_changed_files = 20
check_allow_warnings = false
```

`run`, `snapshot`, `open-latest`, and `history` read that file from the target
repo when it exists. `--out` and `--privacy-mode` override the config for a
single command; boolean entries disable optional integrations or zip export by
default. `check_*` entries tune the local review policy used by
`agentledger check`.

## CI and smoke checks

Local checks:

```powershell
python -m pip install -e ".[dev]"
agentledger --version
python -m pytest
powershell -ExecutionPolicy Bypass -File scripts/install-check.ps1
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

```bash
python -m pip install -e ".[dev]"
agentledger --version
python -m pytest
bash ./scripts/smoke.sh
```

There are also GitHub Actions for the same flow (pytest + install check + smoke) under `.github/workflows/ci.yml`.

Alpha docs:

- `ALPHA.md`
- `docs/alpha-checklist.md`
- `docs/alpha-tester-guide.md`
- `docs/alpha-feedback-template.md`
- `docs/alpha-notes.md`
- `SECURITY.md`
- `CHANGELOG.md`
- `.agentledger.toml`

Alpha install check:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-check.ps1
```

That script installs AgentLedger from the local checkout into a temporary virtual environment using local packaging tools, verifies `agentledger --version`, verifies `python -m agentledger --version`, and removes the temporary environment when it finishes.

Alpha one-command pass:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

That script runs install verification, smoke verification, doctor, a captured pytest pass, report inspection, bundle verification, and prints the short summary an alpha tester should send back.

Notes:

- Smoke runs use temporary repos and temporary output folders.
- Do not commit evidence folders or bundles. `.agentledger/`, `*.zip`, and related generated paths are already ignored by `.gitignore`.
- Treat evidence reports as local proof first. AgentLedger redacts common token, password, API key, and private-key patterns, but you should still review reports before sharing because they can contain command output, file paths, and repository metadata.

For Windows shells that cannot find `git`, AgentLedger includes a helper that locates common Git installs, including GitHub Desktop's bundled git:

```powershell
. .\scripts\ensure-git.ps1
```

Then install the package in editable mode if needed:

```powershell
python -m pip install -e ".[dev]"
```

Contributor sync checklist:

```powershell
git remote -v
git status --short --branch
git branch --show-current
```

For a contribution branch:

```powershell
git switch -c my-agentledger-branch
git push -u origin my-agentledger-branch
```

Open a pull request for review rather than pushing directly to `master`.

## Commands

Capture repository state only:

```powershell
agentledger snapshot --repo C:\path\to\repo
```

Capture state around a command:

```powershell
agentledger run --repo C:\path\to\repo -- npm test
```

Capture a lower-detail report:

```powershell
agentledger run --repo C:\path\to\repo --privacy-mode summary -- npm test
agentledger snapshot --repo C:\path\to\repo --privacy-mode summary
```

`--privacy-mode summary` omits command transcript content and full diffs from
the generated reports and bundles. It also skips optional integrations that can
add detailed local artifacts.

Check local integration readiness:

```powershell
agentledger doctor --repo C:\path\to\repo
agentledger doctor --json
```

Check the installed CLI version:

```powershell
agentledger --version
python -m agentledger --version
```

Skip optional integrations:

```powershell
agentledger run --repo C:\path\to\repo --no-repomori --no-jester --no-tokometer -- pytest
```

Inspect a specific run:

```powershell
agentledger inspect-report .agentledger\2026-06-11T120000Z-abc12345
```

Check a run against the default review policy:

```powershell
agentledger check .agentledger\2026-06-11T120000Z-abc12345
agentledger check --format json .agentledger\2026-06-11T120000Z-abc12345
agentledger check --allow-warnings .agentledger\2026-06-11T120000Z-abc12345
```

`check` returns `0` for pass, `1` for warn, and `2` for block. Use
`--allow-warnings` when a script should only fail on block-level issues. The
default policy blocks failed commands or incomplete reports, and warns on
missing test evidence, dirty final repo state, report warnings, optional
artifact warnings, and redaction markers.

You can tune the default check policy in `.agentledger.toml`:

```toml
check_require_tests = true
check_dirty = "block"
check_max_changed_files = 10
check_allow_warnings = false
```

`check_require_tests = true` turns missing test evidence into a block.
`check_dirty` accepts `"pass"`, `"warn"`, or `"block"` for final dirty repo
state. `check_max_changed_files` blocks runs above the configured changed-file
count, even when dirty state is otherwise allowed. `check_allow_warnings = true`
makes warnings exit `0`, the same as passing `--allow-warnings`.

Open the latest run summary paths:

```powershell
agentledger open-latest --out .agentledger
```

List recent runs:

```powershell
agentledger history --out .agentledger
agentledger history --out .agentledger --format json
agentledger history --out .agentledger --limit 5
```

The normal local review loop is:

```powershell
agentledger run --repo . --out .agentledger --no-repomori --no-jester --no-tokometer -- python -c "print('agentledger smoke')"
agentledger open-latest --out .agentledger
agentledger history --out .agentledger
$run = (Get-Content .agentledger\latest.txt).Trim()
agentledger inspect-report $run
agentledger check --allow-warnings $run
agentledger verify-bundle "${run}.zip"
```

With a repo `.agentledger.toml`, the same loop can use the configured output
folder and privacy mode:

```powershell
agentledger run --repo . -- python -m pytest
agentledger open-latest --repo .
agentledger history --repo .
$run = (Get-Content .agentledger\latest.txt).Trim()
agentledger check $run
```

Compare two runs:

```powershell
agentledger compare .agentledger\2026-06-11T120000Z-abc12345 .agentledger\2026-06-11T120100Z-def67890
```

Verify a produced zip bundle:

```powershell
agentledger verify-bundle .agentledger\2026-06-11T120000Z-abc12345.zip
```

## Current Integrations

### Git

Always on. Captures:

- current branch
- current HEAD
- `git status --short`
- `git diff --stat`
- redacted tracked diff

### Command Transcripts

For `agentledger run`, full stdout and stderr are stored under:

```text
artifacts/command/stdout.txt
artifacts/command/stderr.txt
```

AgentLedger also labels common test commands such as `pytest`, `npm test`,
`vitest`, `jest`, `go test`, and `cargo test` so reports can distinguish
verification runs from ordinary shell commands.

Command transcripts and report tails are redacted for common secret-looking
patterns before they are written to disk.

For lower-detail sharing, use `--privacy-mode summary` to omit transcript
content and full diffs entirely.

### RepoMori

When `python -m repomori` is available, AgentLedger runs before/after snapshots
and stores the RepoMori output under the run artifacts folder.

This is the repo-memory and handoff layer.

If RepoMori is missing, AgentLedger keeps running and records a warning artifact
instead. `agentledger doctor` still reports ready when required checks pass and
marks RepoMori as an optional integration that is not configured.

### Memento Mori Jester

When `jester` or `memento-mori-jester` is on PATH, AgentLedger pipes `git diff`
into the Jester diff gate.

This is the safety and overconfidence layer.

### Tokometer

AgentLedger imports Tokometer's local `getUsageSummary` parser through a small
Node/TS bridge when `npx tsx` and the Tokometer checkout are available. The
artifact is intentionally bounded: it keeps usage totals, windows, limits,
freshness, alerts, top sessions, and parser counts, but omits the full scanned
session-file list.

This is the cost and usage layer.

Override the Tokometer checkout path when needed:

```powershell
$env:AGENTLEDGER_TOKOMETER_ROOT='C:\path\to\codex-token-gauge'
```

## Product Shape

AgentLedger is the wrapper product. It should orchestrate existing assets first
instead of copying all of their internals.

Core assets it can use:

- Tokometer: token usage, burn rate, cost dashboard
- RepoMori: repo memory, source-backed context, handoff packs, provenance
- Memento Mori Jester: command/diff/final-answer safety checks
- The Marked Bench: eval gates, result cards, scoring/report schemas
- ChatP2P: signed work packets and verified result records
- Rat-Trap Proof Kit: buyer-facing proof bundle structure
- TokenSquash: later compact protocol for repeated agent workflows

## Roadmap

### v0.1 Public Alpha Wedge

- CLI evidence capture
- Markdown/JSON report export
- before/after git state
- optional RepoMori/Jester/Tokometer hooks
- local smoke tests

### v0.2 Evidence Bundle

- zip export
- HTML report
- command transcript files
- test-result parser
- richer file-touch manifest
- final-answer verification checklist

### v0.3 Usage + Cost

- direct Tokometer usage summary import
- per-session token deltas
- estimated cost model
- weekly/monthly projections in report

### v0.4 Repo Memory

- first-class RepoMori handoff capsule links
- changed-file source context
- before/after pack comparison summary
- chain/anchor verification section

### v0.5 Eval Gate

- Marked Bench compatible gate schema
- project-local eval suites
- pass/warn/block policies
- result-card export

### v1.0 Buyer Pilot

- desktop dashboard
- signed evidence bundles
- team policy config
- pilot report template
- packaged alpha installer

## License

AgentLedger is source-available under the PolyForm Noncommercial License 1.0.0.
This is not an OSI open-source license because commercial use is restricted.
See `LICENSE` for terms and `COMMERCIAL.md` for commercial-use enquiries.
