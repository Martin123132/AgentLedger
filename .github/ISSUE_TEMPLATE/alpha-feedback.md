---
name: Alpha feedback
about: Report public-alpha install, try, smoke, capture, or review friction.
title: "[alpha feedback] "
labels: alpha, feedback
assignees: ""
---

## Environment

- OS:
- Python version:
- Shell:
- AgentLedger version:
- Git available in this shell: yes/no

## Alpha pass

Commands run:

```powershell
python -m agentledger try
python -m agentledger alpha --repo . --out .agentledger
python -m agentledger alpha-summary --out .agentledger
```

Result:

- Passed:
- Failed:
- Status shown by AgentLedger:
- Alpha summary path:
- AgentLedger try packet path:

## What felt confusing

First confusing command or message:

What you expected:

What happened instead:

Redacted error text:

## Evidence review

- Was the Markdown report understandable enough to trust?
- Did `status`, `history`, `inspect-report`, `check`, and `verify-bundle` make sense?
- Was anything too noisy?
- Was anything unsafe to share?

Generated review/share files you reviewed:

- Issue/comment draft:
- Markdown packet:
- JSON packet:
- Feedback export:

## Local feedback notes

Optional local commands run:

```powershell
python -m agentledger feedback --out .agentledger --note "First confusing thing: ..."
python -m agentledger feedback-summary --out .agentledger
python -m agentledger feedback-export --out .agentledger --output $env:TEMP\agentledger-feedback.md
python -m agentledger pack-alpha --out .agentledger --output-dir $env:TEMP\agentledger-alpha-packet
```

Reviewed feedback export or packet attached: yes/no

## Sensitive data check

Do not attach `.agentledger/` folders, zip bundles, signing keys, secrets,
non-public source code, or full reports unless they have been reviewed and were
explicitly requested.

Paste only redacted errors or reviewed packet/export text. Keep raw local
evidence and temporary demo workspaces private by default.
