# Alpha Troubleshooting

Use this when an alpha pass fails or the output is unclear. Start with the
read-only guide:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
```

`alpha-guide` prints setup checks, the first-run command loop, and a
troubleshooting map without creating evidence.

## Install Problems

Use this when `agentledger` is not found, `--version` fails, Python is wrong, or
Git is missing:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.27-alpha"
python -m agentledger --version
python -m agentledger doctor --repo . --format markdown
```

Read any `Hint:` lines from `doctor` first. Missing RepoMori, Jester, or
Tokometer is okay for the public alpha. The Markdown doctor report is
copy-ready and path-redacted by default, so it is the safest doctor output to
paste into a GitHub issue or comment after review.

## Command Problems

Use this when `agentledger alpha`, `agentledger run`, or the captured command
fails:

```powershell
python -m agentledger alpha-summary --out .agentledger
python -m agentledger status --out .agentledger --allow-warnings
python -m agentledger open-latest --out .agentledger
```

Report the status summary and redacted error text. Do not paste raw command
transcripts or full reports into public issues.

## Packet Confusion

Use this when the packet files are hard to find or you are not sure what can be
shared:

```powershell
python -m agentledger pack-alpha --out .agentledger
python -m agentledger open-packet --out .agentledger
```

Review the issue/comment draft, Markdown packet, and JSON packet before
sharing. Keep raw `.agentledger/` folders, zip bundles, command transcripts,
signing keys, and temporary demo workspaces private by default.

## Privacy-Safe Reporting

Good alpha feedback includes:

- command used
- OS/platform, shell, Python version, and AgentLedger version
- generated review/share files you reviewed
- redacted error text or the first confusing message
- what you expected and what happened instead

Use `.github/ISSUE_TEMPLATE/alpha-feedback.md` for GitHub issues, or
`docs/alpha-feedback-template.md` for local notes.
Run `python -m agentledger support-packet` to print the same checklist and
privacy reminders, or `python -m agentledger support-packet --format markdown`
for a sanitized issue/comment body without writing files or copying evidence.
If setup itself is confusing, include the reviewed output from
`python -m agentledger doctor --repo . --format markdown` instead of raw
terminal logs.
