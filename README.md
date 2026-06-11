# AgentLedger

Local-first black box recorder for AI coding agents.

AgentLedger captures the boring evidence teams need when agents spend tokens,
run commands, touch repositories, and claim work is done:

- before/after git state
- command execution evidence
- changed files and diffs
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
python -m agentledger doctor --repo .
python -m agentledger snapshot --repo .
python -m agentledger run --repo . -- python -c "print('hello from AgentLedger')"
python -m pytest
```

After a run:

```powershell
Get-Content .agentledger\latest.txt
```

Open the `agentledger-report.md` inside that latest run folder.

Quick review loop:

```powershell
python -m agentledger run --repo . --out .agentledger --no-repomori --no-jester --no-tokometer -- python -c "print('agentledger smoke')"
python -m agentledger open-latest --out .agentledger
$run = (Get-Content .agentledger\latest.txt).Trim()
python -m agentledger inspect-report $run
python -m agentledger verify-bundle "${run}.zip"
```

## CI and smoke checks

Local checks:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

```bash
python -m pip install -e ".[dev]"
python -m pytest
bash ./scripts/smoke.sh
```

There are also private-repo GitHub Actions for the same flow (pytest + smoke) under `.github/workflows/ci.yml`.

Notes:

- Smoke runs use temporary repos and temporary output folders.
- Do not commit evidence folders or bundles. `.agentledger/`, `*.zip`, and related generated paths are already ignored by `.gitignore`.

## Commands

Capture repository state only:

```powershell
agentledger snapshot --repo C:\path\to\repo
```

Capture state around a command:

```powershell
agentledger run --repo C:\path\to\repo -- npm test
```

Check local integration readiness:

```powershell
agentledger doctor --repo C:\path\to\repo
agentledger doctor --json
```

Skip optional integrations:

```powershell
agentledger run --repo C:\path\to\repo --no-repomori --no-jester --no-tokometer -- pytest
```

Inspect a specific run:

```powershell
agentledger inspect-report .agentledger\2026-06-11T120000Z-abc12345
```

Open the latest run summary paths:

```powershell
agentledger open-latest --out .agentledger
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
- full tracked diff

### Command Transcripts

For `agentledger run`, full stdout and stderr are stored under:

```text
artifacts/command/stdout.txt
artifacts/command/stderr.txt
```

AgentLedger also labels common test commands such as `pytest`, `npm test`,
`vitest`, `jest`, `go test`, and `cargo test` so reports can distinguish
verification runs from ordinary shell commands.

### RepoMori

When `python -m repomori` is available, AgentLedger runs before/after snapshots
and stores the RepoMori output under the run artifacts folder.

This is the repo-memory and handoff layer.

If RepoMori is missing, AgentLedger keeps running and records a warning artifact
instead. `agentledger doctor` shows this as partial readiness.

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

### v0.1 Private Wedge

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
- private beta installer

## License

Proprietary private repository. Commercial terms TBD.
