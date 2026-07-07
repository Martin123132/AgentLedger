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
python -m agentledger support-packet
python -m agentledger support-packet --format markdown --out <private-output-dir>
python -m agentledger pack-alpha --out .agentledger --output-dir $env:TEMP\agentledger-alpha-packet
```

Reviewed feedback export or packet attached: yes/no

## Doctor Markdown setup feedback

Use this section when install or setup failed before you had useful run
evidence. Follow `docs/doctor-markdown-feedback.md` and paste only a reviewed,
redacted snippet from `agentledger doctor --format markdown`.

Command run:

```powershell
python -m agentledger doctor --repo . --format markdown
```

Checklist:

- [ ] The snippet includes `Raw evidence copied: no`.
- [ ] The snippet includes `Local paths included: no`.
- [ ] Blocked required checks include only the confusing line and `Next:` hint.
- [ ] No raw terminal logs, `.agentledger/` folders, zip bundles, transcripts,
  full reports, private paths, private URLs, credentials, tokens, secrets, or
  customer data are attached or pasted here.

Reviewed doctor Markdown snippet:

```markdown
Paste a short reviewed snippet here. Replace accidental local paths with
<local path redacted> or <private repo path> before posting.
```

## Support-packet Markdown feedback

Use this section for `agentledger support-packet --format markdown` feedback in
`v0.1.28-alpha` or newer. Paste only a reviewed, sanitized snippet from the
generated Markdown body.

Install method:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.28-alpha"
python -m agentledger --version
```

Command run:

```powershell
python -m agentledger support-packet --format markdown --out <private-output-dir>
```

Checklist:

- [ ] Output started with `## AgentLedger alpha support report`.
- [ ] Copy-ready headings were present: `### Summary`, `### Command used`,
  `### Generated review/share files reviewed`,
  `### Redacted error text or first confusing message`, `### Useful commands`,
  and `### Keep private by default`.
- [ ] `<agentledger-output>` replaced the supplied private output path.
- [ ] The generated Markdown did not include the supplied private output path,
  private repo paths, private URLs, credentials, tokens, secrets, or customer
  data.
- [ ] No raw `.agentledger/` folders, zip bundles, transcripts, signing keys,
  full reports, or temp workspaces are attached or pasted here.

Sanitized Markdown snippet:

```markdown
Paste a short reviewed snippet here. Remove private paths, URLs, credentials,
tokens, secrets, customer data, and raw evidence before posting.
```

Reproduction notes:

- What you expected:
- What happened instead:
- Redacted error or confusing line:
- Platform / shell / Python version:

## Sensitive data check

Do not attach `.agentledger/` folders, zip bundles, signing keys, secrets,
non-public source code, or full reports unless they have been reviewed and were
explicitly requested.

Paste only redacted errors or reviewed packet/export text. Keep raw local
evidence and temporary demo workspaces private by default.
