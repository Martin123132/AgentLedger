# First Run

Use this path when you want to see AgentLedger work before pointing it at a real
project.

## Try It In 60 Seconds

Install the current alpha tag from GitHub:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.15-alpha"
python -m agentledger demo
```

`agentledger demo` creates a temporary git repository, runs a small
standard-library `unittest` command through AgentLedger, and prints the evidence
paths, a `Read first` cue, follow-up inspection commands, and a cleanup command.
It does not touch your current repository. Add
`--summary-output $env:TEMP\agentledger-demo-summary.md` when you want a
path-free Markdown summary to review before sharing.
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
- `Public summary`: the optional path-free Markdown summary written by `--summary-output`
- `Read first`: the fastest way to understand the report and verdict
- `Try next`: commands for latest paths, history, status, report inspection, and bundle verification
- `Next real repo`: the read-only alpha-guide command to run from your own repository

Open the Markdown report first, then run the printed `status` command for the
pass/warn/block verdict. Evidence is local proof first. Review reports before
sharing them.

## Next Real Repo

After the demo makes sense, move to the repository you want to test and run:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
python -m agentledger alpha --repo . --out .agentledger
python -m agentledger status --out .agentledger --allow-warnings
```

`alpha-guide` is read-only. It shows setup checks, the fast path, evidence
locations, what to read first after the alpha run, what to send back, and what
to keep private.

## Keep Private

Do not commit or upload:

- `.agentledger/`
- zip evidence bundles
- signing keys
- full reports or transcripts unless reviewed and requested

Use `python -m agentledger pack-alpha --out .agentledger` when you need a
reviewed, share-safe packet. It writes to a fresh temporary packet directory by
default.
