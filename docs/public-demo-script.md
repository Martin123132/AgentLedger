# Public Demo Script

Use this when you want to show AgentLedger publicly without exposing raw
evidence, private paths, or customer data.

## Three Command Demo

Run this from any normal working folder:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.25-alpha"
python -m agentledger try
python -m agentledger support-packet --format markdown
```

`agentledger try` runs in an isolated temporary demo workspace. It prints the
Markdown report, HTML report, JSON report, zip bundle, status command, cleanup
command, and share-safe packet files for that demo.

Open the printed Markdown report first. Then review the generated packet or the
`support-packet --format markdown` output before copying anything into GitHub,
X, chat, email, or a support issue.

## Share This

Short version:

```text
AgentLedger is a local-first black box recorder for AI coding agents. It captures
the repo state, command result, reports, and bundle checks for an agent work
session so a human can review what happened before accepting the work.
```

Demo caption:

```text
I tried AgentLedger with the safe public alpha demo:

python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.25-alpha"
python -m agentledger try

It produced local Markdown, HTML, and JSON reports plus a share-safe packet to
review before posting anything. Raw evidence stays local by default.
```

Feedback prompt:

```text
What I checked:
- install method and AgentLedger version
- the printed Markdown report
- the printed status verdict
- the support-packet Markdown headings
- whether local paths and raw evidence stayed private
```

## Keep Private

Do not paste, upload, commit, screenshot, or attach raw evidence by default:

- `.agentledger/` evidence folders
- zip evidence bundles
- command transcripts
- signing keys
- temporary workspaces
- private repo paths
- private URLs
- credentials, tokens, or secrets
- customer data

Share only reviewed snippets from generated packet files, public summaries, or
`agentledger support-packet --format markdown`.

## Real Repo Follow-Up

After the demo makes sense, move into a repository you control:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
python -m agentledger alpha --repo . --out .agentledger
python -m agentledger status --out .agentledger --allow-warnings
```

For install confidence, see `docs/alpha-install-confidence.md`. For the public
tester loop, see `docs/public-alpha-trial.md`. For troubleshooting, see
`docs/alpha-troubleshooting.md`.
