# AgentLedger Alpha

This alpha checks one thing: can you run AgentLedger locally, capture a real test run, inspect the evidence, and tell us where the experience feels unclear?

AgentLedger is source-available for non-commercial use. See `LICENSE` and
`COMMERCIAL.md` before using it outside evaluation or hobby/research contexts.

## Before you start

You need:

- access to this repository
- Windows PowerShell
- Python 3.12 or newer
- Git installed locally

If PowerShell cannot find `git`, the alpha script will try common Windows Git locations, including GitHub Desktop.

## Run the alpha pass

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

The script runs:

- install verification
- local readiness check
- smoke verification
- a captured `python -m pytest` run
- latest/history/inspect/verify checks

At the end, it prints a short summary headed:

```text
Send back this summary:
```

## What to send back

Send back:

- the final summary printed by `scripts/alpha.ps1`
- notes from `docs/alpha-feedback-template.md`
- optional local `agentledger feedback --out .agentledger --note "..."` entries
- the first command or message that felt confusing
- whether the generated report was clear enough to trust

## What not to send

Do not send or commit:

- `.agentledger/`
- zip evidence bundles
- non-public source code
- secrets, tokens, or credentials
- full evidence reports unless explicitly requested

Generated evidence is local proof for you first. We only need your summary and notes for this pass.

## More detail

- Tester guide: `docs/alpha-tester-guide.md`
- Checklist: `docs/alpha-checklist.md`
- Feedback template: `docs/alpha-feedback-template.md`
