# Support Packet Markdown QA

Use this checklist when reviewing alpha feedback about
`agentledger support-packet --format markdown`. It keeps testers focused on the
copy-ready Markdown shape and privacy behavior, without asking them to attach
raw evidence.

## Checked Command

Run the command with a private output directory so the redaction behavior is
visible:

```powershell
python -m agentledger support-packet --format markdown --out <private-output-dir>
```

Compare the result with
[docs/support-packet-markdown-example.md](support-packet-markdown-example.md).
The example uses sanitized demo inputs only.

## What To Verify

- The output starts with `## AgentLedger alpha support report`.
- The copy-ready headings are present: `### Summary`, `### Command used`,
  `### Generated review/share files reviewed`, `### Redacted error text or first confusing message`,
  `### Useful commands`, and `### Keep private by default`.
- The summary says `Raw evidence copied: no`, `Local paths included: no`, and
  `Raw evidence kept private: yes`.
- Any supplied private output path is replaced by `<agentledger-output>`.
- Raw `.agentledger/` evidence, bundles, transcripts, signing keys, private
  repo paths, private URLs, credentials, tokens, and secrets are not copied into
  the Markdown.

## Feedback Notes

When reporting a problem, paste only reviewed snippets into
[.github/ISSUE_TEMPLATE/alpha-feedback.md](../.github/ISSUE_TEMPLATE/alpha-feedback.md)
using its `Support-packet Markdown feedback` section, or record local notes in
`docs/alpha-feedback-template.md`.

Maintainers should use
[docs/alpha-feedback-readiness.md](alpha-feedback-readiness.md) before treating
support-packet Markdown feedback as a next-alpha release-readiness signal.

Useful feedback includes:

- whether the headings are easy to copy into an issue or comment
- whether the `<agentledger-output>` placeholder was clear
- whether a private output path appeared anywhere in the generated Markdown
- the install method and `python -m agentledger --version` output
- the exact redacted line that was confusing, with private paths and secrets
  removed

Do not include raw `.agentledger/` folders, zip bundles, full transcripts,
signing keys, private repository paths, private URLs, credentials, tokens, or
secrets in public feedback.
