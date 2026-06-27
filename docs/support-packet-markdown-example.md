# Support Packet Markdown Example

Use `agentledger support-packet --format markdown` when an alpha tester needs a
copy-ready issue or comment body without writing files or copying raw evidence.
The command is read-only and prints to stdout.

## Command

Use a private AgentLedger output directory if you want the helper commands to
point at your local evidence location. Absolute paths are replaced with the
safe `<agentledger-output>` marker in the generated Markdown.

```powershell
python -m agentledger support-packet --format markdown --out <private-output-dir>
```

## Sanitized Output Shape

Exact platform, Python, and shell values will vary. The important sharing
properties are stable: raw evidence is not copied, local paths are not included,
and useful follow-up commands use `<agentledger-output>` instead of a private
path.

```markdown
## AgentLedger alpha support report

### Summary
- Result: pass / warn / block / failed / not sure
- AgentLedger version: `0.1.26a0`
- Platform: `Windows-...`
- Python: `3.13...`
- Shell: `powershell.exe`
- Raw evidence copied: no
- Local paths included: no
- Raw evidence kept private: yes

### Command used

Paste the command you ran, for example `python -m agentledger try`.

### Generated review/share files reviewed
- [ ] agentledger-alpha-issue.md from agentledger try or pack-alpha after review.
- [ ] agentledger-alpha-handoff.md after review.
- [ ] agentledger-alpha-handoff.json after review, when a maintainer asks for JSON.

### Redacted error text or first confusing message

Paste only reviewed, redacted text. Remove secrets, private source, private URLs, and local paths.

### Useful commands
- `python -m agentledger status --out <agentledger-output> --allow-warnings`
- `python -m agentledger open-packet --out <agentledger-output>`
- `python -m agentledger support-packet --format markdown`

### Keep private by default
- raw .agentledger/ run folders and local agentledger-output/ folders
- zip evidence bundles
- command transcripts, terminal logs, full reports, and raw diffs
- private repo paths, private URLs, non-public source, credentials, tokens, and secrets
```

Review the generated body before posting it. Do not attach `.agentledger/`
folders, zip bundles, transcripts, signing keys, private paths, private URLs,
credentials, or secrets unless a maintainer explicitly asks for reviewed
evidence.

For tester feedback about this mode, use
[docs/support-packet-markdown-qa.md](support-packet-markdown-qa.md).
