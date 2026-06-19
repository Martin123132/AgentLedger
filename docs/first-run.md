# First Run

Use this path when you want to see AgentLedger work before pointing it at a real
project.

## Try It In 60 Seconds

Install the current alpha tag from GitHub:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.12-alpha"
python -m agentledger demo
```

`agentledger demo` creates a temporary git repository, runs a small
standard-library `unittest` command through AgentLedger, and prints the evidence
paths plus cleanup command. It does not touch your current repository.
For development checkouts, editable installs, source checks, and uninstall
commands, see `docs/install.md`.

## What To Look At

The demo output prints:

- `Workspace`: the temporary folder to delete when done
- `Demo repo`: the tiny git repo used for the capture
- `Evidence output`: the folder containing local AgentLedger evidence
- `Markdown report`: the easiest report to read first
- `HTML report`: the same report in browser-friendly form
- `Bundle`: the local zip evidence bundle
- `Try next`: commands for latest paths, history, status, report inspection, and bundle verification

Evidence is local proof first. Review reports before sharing them.

## Next Real Repo

After the demo makes sense, move to the repository you want to test and run:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
python -m agentledger alpha --repo . --out .agentledger
python -m agentledger status --out .agentledger --allow-warnings
```

`alpha-guide` is read-only. It shows setup checks, the fast path, evidence
locations, what to send back, and what to keep private.

## Keep Private

Do not commit or upload:

- `.agentledger/`
- zip evidence bundles
- signing keys
- full reports or transcripts unless reviewed and requested

Use `python -m agentledger pack-alpha --out .agentledger --output-dir $env:TEMP\agentledger-alpha-packet`
when you need a reviewed, share-safe packet.
