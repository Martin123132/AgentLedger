# Private Alpha Checklist

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

- List latest run paths:
  - `python -m agentledger open-latest --out .agentledger`
- Show recent runs:
  - `python -m agentledger history --out .agentledger`
  - `python -m agentledger history --out .agentledger --format json`
- Inspect a specific run report:
  - `python -m agentledger inspect-report .agentledger\<run-id>`
- Verify a bundle:
  - `python -m agentledger verify-bundle .agentledger\<run-id>.zip`
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
  - zipped bundle (`.zip`) with the same base run id

## What not to commit

- Do not commit `.agentledger/`.
- Do not commit `*.zip`.
- Do not commit temporary `Temp/agentledger-smoke-*` folders.
- Keep only source/config/docs files in git history.

## Known limitations

- `bash ./scripts/smoke.sh` needs WSL/Linux shell support (`bash`).
- Optional integrations are best-effort:
  - RepoMori / Jester / Tokometer warnings are expected when tools are absent.
  - They should not block core run/inspect/compare workflows.
