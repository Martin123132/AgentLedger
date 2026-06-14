# Alpha Checklist

## Before first run

- Install once from this checkout (editable + dev dependencies):
  - `python -m pip install -e ".[dev]"`
  - `agentledger --version`
- Confirm branch and remote are correct:
  - `git status --short --branch`
  - `git branch --show-current`
- Optional safety check on dependencies:
  - `python -m pytest`

## First local smoke

Preferred one-command alpha pass:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

Expected result:

- Install check, smoke check, doctor, captured pytest, inspect, check, and verify all pass.
- A short summary is printed for the tester to send back.
- `.agentledger/` evidence is created locally and must not be committed or sent unless requested.

Manual fallback flow:

Run this exact flow from repo root:

```powershell
python -m pip install -e ".[dev]"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

Expected result:

- Temporary `.agentledger/<run-id>/` output is created in a temp folder.
- A summary is printed and a `*.zip` bundle is generated.
- Command exits with status `0`.

## Verify a captured run

- Review the latest run with policy status and report paths:
  - `python -m agentledger review --out .agentledger --allow-warnings`
  - `python -m agentledger review --format json --out .agentledger --allow-warnings`
- List latest run paths:
  - `python -m agentledger open-latest --out .agentledger`
  - `python -m agentledger open-latest --format json --out .agentledger`
- Show recent runs:
  - `python -m agentledger history --out .agentledger`
  - `python -m agentledger history --out .agentledger --format json`
- Inspect a specific run report:
  - `python -m agentledger inspect-report .agentledger\<run-id>`
- Check a specific run report:
  - `python -m agentledger check --repo . .agentledger\<run-id>`
- Verify a bundle:
  - `python -m agentledger verify-bundle .agentledger\<run-id>.zip`
  - `python -m agentledger verify-bundle .agentledger\<run-id>.zip --format json`
- Optional shared-key signature check:
  - `python -m agentledger sign-bundle .agentledger\<run-id>.zip --key-file .agentledger-signing-key`
  - `python -m agentledger verify-bundle .agentledger\<run-id>.zip --signature-key-file .agentledger-signing-key --require-signature`
  - `python -m agentledger verify-bundle .agentledger\<run-id>.zip --format json --signature-key-file .agentledger-signing-key --require-signature`
- Compare two runs:
  - `python -m agentledger compare .agentledger\<run-id-a> .agentledger\<run-id-b>`

## Where evidence appears

- Default output root: `.agentledger/`
- Latest run path is tracked in `.agentledger/latest.txt`
- Each run folder includes:
  - `agentledger-report.md`
  - `agentledger-report.json`
  - `agentledger-report.html`
  - `artifacts/`
- A sibling zipped bundle (`.zip`) with the same base run id includes
  `agentledger-bundle-manifest.json` with SHA-256 checksums.

## What not to commit

- Do not commit `.agentledger/`.
- Do not commit `*.zip`.
- Do not commit `.agentledger-signing-key` or any shared signing key.
- Do not commit temporary `Temp/agentledger-smoke-*` folders.
- Keep only source/config/docs files in git history.

## Known limitations

- `bash ./scripts/smoke.sh` needs WSL/Linux shell support (`bash`).
- Optional integrations are best-effort:
  - RepoMori / Jester / Tokometer warnings are expected when tools are absent.
  - They should not block core run/inspect/compare workflows.
