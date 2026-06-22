# Alpha Feedback Readiness

Use this maintainer checklist before considering the next public alpha after
feedback about `agentledger support-packet --format markdown`. It is a
triage signal for release planning, not a replacement for the full release
process in `docs/release-process.md`.

## Inputs To Review

- Issues filed with `.github/ISSUE_TEMPLATE/alpha-feedback.md`, especially the
  `Support-packet Markdown feedback` section.
- Sanitized Markdown snippets only, not full reports or raw local evidence.
- The installed version and install method, for example `v0.1.23-alpha` from
  the public GitHub tag.
- The command the tester ran:

```powershell
python -m agentledger support-packet --format markdown --out <private-output-dir>
```

## Ready Signal

Treat support-packet Markdown feedback as release-ready input only when all of
these are true:

- The report includes the installed version and install method.
- The snippet starts with `## AgentLedger alpha support report`.
- The copy-ready headings are present: `### Summary`, `### Command used`,
  `### Generated review/share files reviewed`,
  `### Redacted error text or first confusing message`, `### Useful commands`,
  and `### Keep private by default`.
- The tester confirms redaction: any supplied private output path is replaced
  by `<agentledger-output>`.
- The feedback includes reproduction notes clear enough to classify as an
  install issue, command issue, packet-output confusion, docs issue, or
  next-alpha blocker.
- The feedback contains no raw `.agentledger/` folders, zip bundles,
  transcripts, signing keys, temp workspaces, private paths, private URLs,
  credentials, tokens, secrets, customer data, or non-public source code.

## Not Ready

Do not use the feedback as a release-readiness signal until it is clarified or
redacted if any of these are true:

- The installed version or install method is missing.
- The snippet omits the expected copy-ready headings.
- A supplied private output path appears instead of `<agentledger-output>`.
- Raw evidence bundles, full transcripts, private paths, private URLs,
  credentials, tokens, secrets, customer data, or non-public source code were
  pasted or attached.
- The report is only a reaction without enough reproduction notes to triage.

## Release Handoff

Before opening the next alpha release PR, summarize the reviewed feedback in
maintainer notes without quoting private data:

- support-packet Markdown issues reviewed: yes/no
- sanitized snippets only: yes/no
- installed version/method present: yes/no
- copy-ready headings confirmed: yes/no
- redaction confirmation present: yes/no
- privacy blockers found: yes/no
- release blocker summary:

If privacy blockers were found, keep the public issue focused on the redacted
finding and ask for a sanitized replacement. Do not copy raw evidence, bundles,
transcripts, signing keys, private paths, private URLs, credentials, tokens,
secrets, customer data, or non-public source code into release notes, PR bodies,
comments, screenshots, tags, or release artifacts.
