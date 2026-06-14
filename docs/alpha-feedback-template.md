# Alpha Feedback Template

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
python -m pip install -e ".[dev]"
agentledger --version
python -m agentledger doctor --repo .
```

Result:

- Passed:
- Failed:
- Confusing:

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
```

Feedback is stored in `alpha-feedback.jsonl` beside the run reports. Do not
commit or upload it unless the contents have been reviewed.

## Overall readiness

Would you trust this enough to use after an AI coding-agent session?

What one thing should be fixed before the next tester?

## Sensitive data reminder

Do not paste non-public source code, secrets, tokens, zip bundles, `.agentledger/` folders, or full evidence reports into public channels.
