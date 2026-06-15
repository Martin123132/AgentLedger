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
python -m agentledger alpha --repo . --out .agentledger
```

Windows extended alpha pass:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

Expected result:

- Doctor, captured pytest, status, inspect, check, and verify all pass.
- The Windows script also runs install and smoke checks.
- A short summary is printed for the tester to send back.
- `.agentledger/alpha-summary.json` is written for machine-readable handoffs,
  or `--json-output <path>` / `-JsonOutput <path>` writes that summary to a
  chosen location.
- `--strict` is available when warning status should fail the alpha pass.
- If required setup is blocked, the summary records config or doctor errors
  plus doctor repair hints instead of stopping with a traceback.
- If the Windows `-JsonOutput` path cannot be written, the script prints the
  write error and exits 2.
- `python -m agentledger alpha-summary --out .agentledger` prints the same
  handoff summary with validated paths and next actions.
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

- Discover machine-readable command contracts:
  - `python -m agentledger contracts`
  - `python -m agentledger contracts --format json`
- Review the latest run with policy status, report paths, and previous-run comparison:
  - `python -m agentledger review --out .agentledger --allow-warnings`
  - `python -m agentledger review --format markdown --out .agentledger --allow-warnings --output $env:TEMP\agentledger-review.md`
  - `python -m agentledger review --format json --out .agentledger --allow-warnings`
  - `python -m agentledger review --out .agentledger --history-limit 5 --allow-warnings`
- Show latest run status, evidence paths, feedback counts, and next action:
  - `python -m agentledger status --out .agentledger --allow-warnings`
  - `python -m agentledger status --out .agentledger --format json --allow-warnings`
- Inspect the one-command alpha summary if `agentledger alpha` or `scripts/alpha.ps1` was run:
  - `python -m agentledger alpha-summary --out .agentledger`
  - `python -m agentledger alpha-summary --out .agentledger --format json`
  - `python -m agentledger alpha-summary $env:TEMP\agentledger-alpha-summary.json`
- List latest run paths:
  - `python -m agentledger open-latest --out .agentledger`
  - `python -m agentledger open-latest --format json --out .agentledger`
- Show recent runs:
  - `python -m agentledger history --out .agentledger`
  - `python -m agentledger history --out .agentledger --format json`
- Record local feedback for the latest run:
  - `python -m agentledger feedback --out .agentledger --note "First confusing thing: ..."`
  - `python -m agentledger feedback --out .agentledger --list`
  - `python -m agentledger feedback-summary --out .agentledger`
  - `python -m agentledger feedback-export --out .agentledger --output $env:TEMP\agentledger-feedback.md`
  - `python -m agentledger alpha-handoff --out .agentledger --output-dir $env:TEMP\agentledger-alpha-handoff`
  - `python -m agentledger alpha-handoff --out .agentledger --output-dir $env:TEMP\agentledger-alpha-handoff-safe --share-safe`
- Inspect a specific run report:
  - `python -m agentledger inspect-report .agentledger\<run-id>`
- Check a specific run report:
  - `python -m agentledger check --repo . .agentledger\<run-id>`
- Verify a bundle:
  - `python -m agentledger inspect-bundle .agentledger\<run-id>.zip`
  - `python -m agentledger inspect-bundle .agentledger\<run-id>.zip --format json`
  - `python -m agentledger verify-bundle .agentledger\<run-id>.zip`
  - `python -m agentledger verify-bundle .agentledger\<run-id>.zip --format json`
- Optional shared-key signature check:
  - `python -m agentledger signing-key --repo . --key-file .agentledger-signing-key`
  - `python -m agentledger signing-key --repo . --key-file .agentledger-signing-key --format json`
  - `python -m agentledger sign-bundle .agentledger\<run-id>.zip --key-file .agentledger-signing-key`
  - `python -m agentledger sign-bundle .agentledger\<run-id>.zip --key-file .agentledger-signing-key --format json`
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
  - `alpha-feedback.jsonl` when local feedback has been recorded
  - `artifacts/`
- A sibling zipped bundle (`.zip`) with the same base run id includes
  `agentledger-bundle-manifest.json` with SHA-256 checksums.

## What not to commit

- Do not commit `.agentledger/`.
- Do not commit `*.zip`.
- Do not commit `alpha-feedback.jsonl` files unless a reviewer explicitly asks
  for reviewed feedback evidence.
- Do not commit feedback exports unless they have been reviewed and are meant
  to be shared.
- Do not commit alpha handoff packet folders unless they have been reviewed
  and are meant to be shared.
- Use `alpha-handoff --share-safe` before sharing a packet outside your own
  machine so local absolute paths are replaced with stable markers.
- Do not commit `.agentledger-signing-key` or any shared signing key.
- Do not commit temporary `Temp/agentledger-smoke-*` folders.
- Keep only source/config/docs files in git history.

## Known limitations

- `bash ./scripts/smoke.sh` needs WSL/Linux shell support (`bash`).
- Optional integrations are best-effort:
  - RepoMori / Jester / Tokometer warnings are expected when tools are absent.
  - They should not block core run/inspect/compare workflows.
