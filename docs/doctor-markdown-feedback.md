# Doctor Markdown Feedback

Use this when setup is confusing before a tester has useful run evidence. The
doctor Markdown output is read-only, copy-ready, and path-redacted by default.

```powershell
python -m agentledger doctor --repo . --format markdown
```

## What To Paste

Paste a short reviewed snippet, not the whole terminal session:

- the `### Summary` lines for status, required setup, optional integrations,
  `Raw evidence copied`, and `Local paths included`
- any blocked `### Required checks` item and its `Next:` hint
- optional integration lines only when the warning is confusing
- the one command you ran, install method, AgentLedger version, OS, shell, and
  Python version
- what you expected and what happened instead

Use placeholders for anything local:

```markdown
## AgentLedger doctor report

### Summary
- Status: blocked - required setup needs attention
- Required setup: fix required
- Optional integrations configured: 3/6
- Raw evidence copied: no
- Local paths included: no

### Required checks
- [ ] `target_git_repo`: missing - <redacted setup error>
  - Next: Run from a git checkout or pass --repo <path> to an existing git repo.
```

## Check Before Posting

- `Local paths included: no` is present.
- `Raw evidence copied: no` is present.
- private repo paths, private URLs, usernames, customer names, credentials,
  tokens, and secrets are not present.
- raw `.agentledger/` folders, zip bundles, transcripts, full reports, and
  terminal logs are not attached.
- Any accidental local path is replaced with `<local path redacted>` or
  `<private repo path>`.

If a private path appears in the generated Markdown, do not paste it. Report
that as a redaction problem with the command used and a redacted one-line
description of where the path appeared.

For wider alpha feedback, use
[.github/ISSUE_TEMPLATE/alpha-feedback.md](../.github/ISSUE_TEMPLATE/alpha-feedback.md)
or [docs/alpha-feedback-template.md](alpha-feedback-template.md).
