# Alpha Tester Guide

AgentLedger is a local-first evidence recorder for AI coding-agent work. This alpha is checking the core loop: install, run a command under AgentLedger, inspect the evidence, and report where the experience feels unclear.

## What you need

- Windows PowerShell
- Python 3.12 or newer
- Git available in PowerShell
- Access to an AgentLedger checkout

If PowerShell cannot find `git`, let AgentLedger locate a common Git install for the current session:

```powershell
. .\scripts\ensure-git.ps1
```

## Setup

From the repository root:

```powershell
python -m pip install -e ".[dev]"
agentledger --version
python -m agentledger doctor --repo .
```

Expected result:

- `agentledger --version` prints the installed AgentLedger version
- `doctor` should say `ready` when required checks pass
- Missing RepoMori, Jester, or Tokometer warnings are OK for this alpha

## One-command alpha pass

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

Expected result:

- install check passes
- smoke check passes
- a real pytest run is captured under `.agentledger/`
- latest/history/inspect/check/verify commands all succeed
- the script prints a short summary to send back

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
python -m agentledger review --out .agentledger --allow-warnings
$run = (Get-Content .agentledger\latest.txt).Trim()
python -m agentledger inspect-report $run
python -m agentledger check --repo . $run
python -m agentledger verify-bundle "$run.zip"
```

Expected result:

- The captured command exits with code `0`
- `history` shows the pytest run
- `review` prints the latest report paths and pass/warn/block policy status
- `inspect-report` summarizes command, exit code, test framework, changed files, and artifacts
- `check` evaluates the run using `.agentledger.toml`
- `verify-bundle` prints `Bundle OK` after validating the bundle manifest and checksums
- Optional: `sign-bundle` adds a shared-key HMAC signature that `verify-bundle --signature-key-file --require-signature` can verify

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
- a sibling `.zip` bundle with `agentledger-bundle-manifest.json`

Do not commit `.agentledger/`, zip bundles, signing keys, logs, screenshots, or sensitive evidence.

## Feedback focus

Please report:

- the first command that felt confusing
- any command that failed and the exact error
- whether the report was understandable
- whether the latest/history/inspect/check/verify flow made sense
- whether anything looked unsafe to share or too noisy

Use `docs/alpha-feedback-template.md` for notes.
