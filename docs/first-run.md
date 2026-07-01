# First Run

Use this path when you want to see AgentLedger work before pointing it at a real
project.

## Try It In 60 Seconds

Install the current alpha tag from GitHub:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.27-alpha"
python -m agentledger try
```

`agentledger try` creates a temporary git repository, runs a small
standard-library `unittest` command through AgentLedger, prints the evidence
paths, writes a share-safe alpha packet, labels what to review/share versus
what to keep local, and gives a cleanup command. It does not touch your current
repository. Use `python -m agentledger demo` when you only want the local report
path tour. Add
`--summary-output $env:TEMP\agentledger-demo-summary.md` when you want a
path-free Markdown summary to review before sharing.
For development checkouts, editable installs, source checks, and uninstall
commands, see `docs/install.md`. For the checked public alpha install receipt,
see `docs/alpha-install-confidence.md`. If the install, command, packet, or
reporting step is unclear, see `docs/alpha-troubleshooting.md`.

## What To Look At

The demo output prints:

- `Workspace`: the temporary folder to delete when done
- `Demo repo`: the tiny git repo used for the capture
- `Evidence output`: the folder containing local AgentLedger evidence
- `Markdown report`: the easiest report to read first
- `HTML report`: the same report in browser-friendly form
- `Bundle`: the local zip evidence bundle
- `Public summary`: the optional path-free Markdown summary written by `--summary-output`
- `Alpha packet`: issue/comment, Markdown, and JSON files from `try` or `demo --packet`
- `Review/share after reading`: packet files that can be shared only after review
- `Keep local`: raw demo evidence, bundles, and temporary workspace paths
- `Read first`: the fastest way to understand the report and verdict
- `Try next`: commands for latest paths, history, status, report inspection, and bundle verification
- `Next real repo`: the read-only alpha-guide command to run from your own repository

Open the Markdown report first, then run the printed `status` command for the
pass/warn/block verdict. The status output includes a `Read first:` block that
repeats the Markdown report, verdict, and private-evidence reminder. Evidence
is local proof first. Review reports before sharing them.

## Report Feedback

After `agentledger try`, open the printed `agentledger-alpha-issue.md` draft if
you want to report what happened. Include the command used, platform, shell,
Python version, AgentLedger version, generated review/share files, and redacted
error text or the first confusing message. Paste only reviewed packet/export
text; keep raw `.agentledger/` evidence, zip bundles, command transcripts,
signing keys, and temporary demo workspaces private by default.
Run `python -m agentledger support-packet` when you want the exact checklist,
or `python -m agentledger support-packet --format markdown` when you want a
sanitized issue/comment body to paste after review.

## Next Real Repo

After the demo makes sense, move to the repository you want to test and run:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
python -m agentledger doctor --repo . --format markdown
python -m agentledger alpha --repo . --out .agentledger
python -m agentledger status --out .agentledger --allow-warnings
```

`alpha-guide` is read-only. It shows setup checks, the fast path, evidence
locations, what to read first after the alpha run, what to send back, and what
to keep private. It also prints a troubleshooting map for install problems,
command failures, packet-output confusion, and privacy-safe reporting. Use the
Markdown doctor report when setup is confusing and you need copy-ready,
path-redacted output for a maintainer.

## Keep Private

Do not commit or upload:

- `.agentledger/`
- zip evidence bundles
- signing keys
- full reports or transcripts unless reviewed and requested

Use `python -m agentledger pack-alpha --out .agentledger` when you need a
reviewed, share-safe packet. It writes to a fresh temporary packet directory by
default. Use `python -m agentledger open-packet --out .agentledger` to find that
latest packet again.
