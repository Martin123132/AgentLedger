# Alpha Feedback Template

Use this file for local notes. When feedback belongs in GitHub, use
`.github/ISSUE_TEMPLATE/alpha-feedback.md` and paste only reviewed summary
text or reviewed exports.

Tester:

Date:

Environment:

- OS:
- Python version:
- Git available in PowerShell: yes/no
- Shell used:

## Install and setup

Commands run:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.21-alpha"
agentledger --version
python -m agentledger try
python -m agentledger doctor --repo .
```

Result:

- Passed:
- Failed:
- AgentLedger version:
- Platform / shell / Python version:
- Try packet issue/comment draft:
- Alpha summary JSON path:
- Confusing:

Redacted error text:

Generated review/share files you reviewed:

- Issue/comment draft:
- Markdown packet:
- JSON packet:
- Feedback export:

## Smoke test

Commands run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

Result:

- Passed:
- Failed:
- Confusing:

## Real capture

Command run:

```powershell
python -m agentledger run --repo . --out .agentledger --no-repomori --no-jester --no-tokometer -- python -m pytest
```

Result:

- Exit code:
- Evidence folder created:
- Bundle verified:
- Confusing:

## Report review

Was the report understandable?

Did `agentledger review` make the latest run status clear?

What was useful?

What was noisy or unclear?

Was anything unsafe to share?

## Local feedback capture

Optional command to attach notes to the latest local run:

```powershell
python -m agentledger feedback --out .agentledger --category friction --severity medium --note "First confusing thing: ..."
python -m agentledger feedback --out .agentledger --list
python -m agentledger feedback-summary --out .agentledger
python -m agentledger feedback-export --out .agentledger --output $env:TEMP\agentledger-feedback.md
python -m agentledger support-packet
python -m agentledger support-packet --format markdown
```

Feedback is stored in `alpha-feedback.jsonl` beside the run reports. Do not
commit or upload it unless the contents have been reviewed. Use
`feedback-export` when you need a Markdown or JSON handoff that omits local run
directories and feedback file paths.

Use `pack-alpha` when you need a copy-ready GitHub issue/comment draft. It
prints the files to review/share and keeps raw evidence, bundles, command
transcripts, signing keys, and temporary workspaces private by default.
Use `support-packet` when you only need the exact report checklist and privacy
reminders. Use `support-packet --format markdown` for a sanitized issue/comment
body. `docs/support-packet-markdown-example.md` shows the checked output shape.
`docs/support-packet-markdown-qa.md` lists what to verify before reporting a
Markdown support-packet problem.
Neither mode writes files or copies evidence.

## Overall readiness

Would you trust this enough to use after an AI coding-agent session?

What one thing should be fixed before the next tester?

## Sensitive data reminder

Do not paste non-public source code, secrets, tokens, zip bundles, `.agentledger/` folders, or full evidence reports into public channels.

Paste only redacted errors or reviewed packet/export text.
