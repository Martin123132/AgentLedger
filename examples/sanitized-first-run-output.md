# Sanitized First-Run Output

This is a public-safe example of what a first AgentLedger run should feel like.
It is not a real evidence bundle, not a transcript, and not something to
verify. It uses placeholders instead of local paths so it can be copied into
docs, issues, and comments without exposing private workspaces.

Run the public alpha first-look flow:

```powershell
python -m agentledger try
python -m agentledger support-packet --format markdown
```

## Terminal Shape

```text
AgentLedger try demo captured.
Workspace: <temporary-demo-workspace>
Output: <agentledger-output>

Markdown report: <agentledger-output>/<run-id>/agentledger-report.md
JSON report: <agentledger-output>/<run-id>/agentledger-report.json
HTML report: <agentledger-output>/<run-id>/agentledger-report.html
Zip bundle: <agentledger-output>/<run-id>.zip

Packet files to review:
- <packet-output>/agentledger-alpha-summary.md
- <packet-output>/agentledger-alpha-issue.md

Next:
- Open the Markdown report first.
- Run: python -m agentledger status --out <agentledger-output> --allow-warnings
- Share only reviewed packet snippets.
- Keep raw evidence, zip bundles, transcripts, signing keys, and temp workspaces private.
```

## Report Excerpt

```text
# AgentLedger Report

Review summary: warn
Command: python -m unittest
Exit code: 0
Changed files: 0
Privacy mode: standard

Human checklist:
- Review the command and exit code.
- Check changed files and evidence pointers.
- Keep the local evidence folder private unless a reviewer explicitly asks for it.
```

## Support Packet Markdown Excerpt

````markdown
## AgentLedger alpha support report

### Summary
- AgentLedger version: 0.1.26a0
- Platform: <platform>
- Python: <python-version>
- Shell: <shell>
- Raw evidence copied: no
- Local paths included: no
- Raw evidence kept private: yes

### Command used
Paste the command you ran, for example:

```text
python -m agentledger try
```

### Generated review/share files reviewed
- <packet-output>/agentledger-alpha-summary.md
- <packet-output>/agentledger-alpha-issue.md

### Redacted error text or first confusing message
Paste only redacted text. Replace local paths with <agentledger-output>.

### Keep private by default
Do not paste raw .agentledger folders, zip bundles, transcripts, signing keys,
temp workspaces, private repo paths, private URLs, credentials, tokens, secrets,
or customer data.
````

## Before Sharing

Check the snippet you are about to post:

- no supplied private output path appears anywhere
- no raw `.agentledger/` folders or zip bundles are attached
- no transcripts, signing keys, private paths, private URLs, credentials,
  tokens, secrets, or customer data are included
- generated Markdown headings are still copy-ready
- version and install method are included

For the full checked support-packet shape, see
[docs/support-packet-markdown-example.md](../docs/support-packet-markdown-example.md).
For the three-command public sharing loop, see
[docs/public-demo-script.md](../docs/public-demo-script.md).
