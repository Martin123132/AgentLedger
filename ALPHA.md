# AgentLedger Alpha

This alpha checks one thing: can you run AgentLedger locally, capture a real test run, inspect the evidence, and tell us where the experience feels unclear?

AgentLedger is source-available for non-commercial use. See `LICENSE` and
`COMMERCIAL.md` before using it outside evaluation or hobby/research contexts.

## Before you start

You need:

- access to this repository
- Python 3.12 or newer
- Git installed locally
- Windows PowerShell only if you use the extended script

If PowerShell cannot find `git`, the alpha script will try common Windows Git locations, including GitHub Desktop.

## Run the alpha pass

From the repository root:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
python -m agentledger alpha --repo . --out .agentledger
```

`alpha-guide` prints the commands to run, where evidence appears, what to send
back, and what must stay private.

Windows users can also run the extended script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

The Python command runs:

- local readiness check
- a captured `python -m pytest` run
- latest/history/inspect/verify checks

The PowerShell script additionally runs install and smoke verification.

At the end, it prints a short summary headed:

```text
Send back this summary:
```

## What to send back

Send back:

- the final summary printed by `agentledger alpha` or `scripts/alpha.ps1`
- notes from `docs/alpha-feedback-template.md`
- a GitHub issue using `.github/ISSUE_TEMPLATE/alpha-feedback.md` when feedback is tracked in the repo
- optional local `agentledger feedback --out .agentledger --note "..."` entries
- optional local `agentledger feedback-summary --out .agentledger` output
- optional reviewed `agentledger feedback-export --out .agentledger --output <path>` file
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
