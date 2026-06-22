# AgentLedger Alpha

This alpha checks one thing: can you run AgentLedger locally, capture a real test run, inspect the evidence, and tell us where the experience feels unclear?

AgentLedger is source-available for non-commercial use. See `LICENSE` and
`COMMERCIAL.md` before using it outside evaluation or hobby/research contexts.

## Before you start

You need:

- AgentLedger installed from the GitHub alpha tag, or a local checkout if you are contributing
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
- the command used, platform, shell, Python version, and AgentLedger version
- generated review/share files you reviewed, especially the issue/comment draft and handoff packet from `agentledger try` or `pack-alpha`
- redacted error text or the first confusing message, with secrets and private source removed
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
- command transcripts
- temporary demo workspaces
- signing keys
- non-public source code
- secrets, tokens, or credentials
- full evidence reports unless explicitly requested

Generated evidence is local proof for you first. We only need your reviewed
summary, packet/export text, and notes for this pass.

## More detail

- Install guide: `docs/install.md`
- First run: `docs/first-run.md`
- Safe demo guide: `docs/demo.md`
- Tester guide: `docs/alpha-tester-guide.md`
- Troubleshooting: `docs/alpha-troubleshooting.md`
- Checklist: `docs/alpha-checklist.md`
- Feedback template: `docs/alpha-feedback-template.md`
