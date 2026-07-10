# Alpha Install Confidence

Use this page when you want to confirm the public alpha install path before
running AgentLedger against a real repository.

## Known Good Alpha

`v0.1.31-alpha` is the current checked public alpha tag.

Expected version:

```text
agentledger 0.1.31a0
```

The tag has passed the repo CI, release-readiness gate, tag CI, post-release
check, and a public install-from-tag smoke check.

## One Minute Check

Run these commands from any normal working folder:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.31-alpha"
python -m agentledger --version
python -m agentledger try
```

`agentledger try` creates an isolated temporary demo repo and prints the report,
packet, status, and cleanup paths for that demo.

Open the printed Markdown report first. Then run the printed `status` command
to inspect the pass, warn, or block verdict.

## Real Repo Loop

After the safe demo makes sense, move into a repository you control:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
python -m agentledger alpha --repo . --out .agentledger
python -m agentledger status --out .agentledger --allow-warnings
python -m agentledger support-packet --format markdown
```

`alpha-guide` is read-only. `alpha` creates the local evidence. `status` tells
you what to read first.

`support-packet --format markdown` prints a sanitized issue/comment body. Use
it for feedback after you review it.

## Keep Private

Do not paste, upload, commit, or attach raw evidence by default:

- `.agentledger/` evidence folders
- zip evidence bundles
- command transcripts
- signing keys
- temporary workspaces
- private repo paths
- private URLs
- credentials, tokens, or secrets
- customer data

For troubleshooting, see `docs/alpha-troubleshooting.md`. For the wider tester
loop, see `docs/public-alpha-trial.md`. For a short privacy-safe sharing script,
see `docs/public-demo-script.md`.
