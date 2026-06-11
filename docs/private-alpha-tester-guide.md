# Private Alpha Tester Guide

AgentLedger is a local-first evidence recorder for AI coding-agent work. This private alpha is only checking the core loop: install, run a command under AgentLedger, inspect the evidence, and report where the experience feels unclear.

## What you need

- Windows PowerShell
- Python 3.12 or newer
- Git available in PowerShell
- Access to the private AgentLedger repository

If `git` is installed through GitHub Desktop but PowerShell cannot find it, add GitHub Desktop's bundled git to the current session:

```powershell
$env:Path = "C:\Users\ollet\AppData\Local\GitHubDesktop\app-3.5.4\resources\app\git\cmd;" + $env:Path
```

## Setup

From the repository root:

```powershell
python -m pip install -e ".[dev]"
agentledger --version
python -m agentledger doctor --repo .
```

Expected result:

- `agentledger --version` prints `agentledger 0.1.0`
- `doctor` may say `partial` if optional integrations are missing
- Missing RepoMori, Jester, or Tokometer warnings are OK for this alpha

## Smoke test

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

Expected result:

- Both scripts exit successfully
- Smoke output shows a report folder and zip bundle
- Temporary smoke output stays under a temp folder

## Real capture

Run AgentLedger against the test suite:

```powershell
python -m agentledger run --repo . --out .agentledger --no-repomori --no-jester --no-tokometer -- python -m pytest
```

Inspect the run:

```powershell
python -m agentledger open-latest --out .agentledger
python -m agentledger history --out .agentledger
$run = (Get-Content .agentledger\latest.txt).Trim()
python -m agentledger inspect-report $run
python -m agentledger verify-bundle "$run.zip"
```

Expected result:

- The captured command exits with code `0`
- `history` shows the pytest run
- `inspect-report` summarizes command, exit code, test framework, changed files, and artifacts
- `verify-bundle` prints `Bundle OK`

## Evidence location

AgentLedger writes local evidence under:

```text
.agentledger/
```

Each run includes:

- `agentledger-report.md`
- `agentledger-report.json`
- `agentledger-report.html`
- `artifacts/`
- a sibling `.zip` bundle

Do not commit `.agentledger/`, zip bundles, logs, screenshots, or private evidence.

## Feedback focus

Please report:

- the first command that felt confusing
- any command that failed and the exact error
- whether the report was understandable
- whether the latest/history/inspect/verify flow made sense
- whether anything looked unsafe to share or too noisy

Use `docs/private-alpha-feedback-template.md` for notes.
