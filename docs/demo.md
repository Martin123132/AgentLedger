# AgentLedger Demo

`agentledger try` is the shortest safe first run available from the current
alpha tag. It creates a tiny temporary git repository, captures a real
verification command, prints the report paths, and generates the share-safe
packet handoff without touching the current repository. `agentledger demo` is
the same isolated walkthrough without the packet unless `--packet` is supplied.

## Run It

From any shell with Python and Git:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.31-alpha"
python -m agentledger try
```

Use the report-only walkthrough when you do not need the packet:

```powershell
python -m agentledger demo
```

Use an empty directory when you want predictable paths:

```powershell
python -m agentledger try --output-dir $env:TEMP\agentledger-demo
```

The chosen `--output-dir` must be empty. This avoids mixing demo evidence with
other files.

Use JSON output when a wrapper, script, or another agent needs the evidence
paths without scraping text:

```powershell
python -m agentledger demo --format json
```

Write a short path-free Markdown summary when you want copyable public proof to
review before sharing:

```powershell
python -m agentledger demo --summary-output $env:TEMP\agentledger-demo-summary.md
```

Show the full share-safe handoff path without touching a real repo:

```powershell
python -m agentledger try
python -m agentledger demo --packet
```

## What It Does

The command creates:

- `demo-repo/`: a tiny git repository with `README.md` and `test_demo.py`
- `agentledger-output/`: the local AgentLedger evidence directory
- one timestamped run folder under `agentledger-output/`
- a sibling `.zip` evidence bundle beside that run folder
- `agentledger-alpha-packet/` when `try` or `demo --packet` is used

The captured command is:

```powershell
python -B -m unittest test_demo.py
```

That test writes `demo-result.txt`, so the report shows a small real file
change instead of a fake no-op capture.

## Expected Output

The exact timestamp and paths will differ, but the shape should look like this:

```text
AgentLedger demo: pass
Workspace: D:\Temp\agentledger-demo-...
Demo repo: D:\Temp\agentledger-demo-...\demo-repo
Evidence output: D:\Temp\agentledger-demo-...\agentledger-output
What happened:
- Created an isolated demo git repo.
- Captured command: python -B -m unittest test_demo.py
- Wrote local Markdown, HTML, JSON, and zip evidence.
- Privacy mode: summary
Latest run: D:\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345
Markdown report: D:\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345\agentledger-report.md
JSON report: D:\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345\agentledger-report.json
HTML report: D:\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345\agentledger-report.html
Bundle: D:\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345.zip
Read first:
- Open the Markdown report for the human summary.
- Run status when you want the pass/warn/block verdict.
Alpha packet:
- Printed when `try` or `demo --packet` is used.
- Shows the issue/comment draft, Markdown packet, JSON packet, and latest packet pointer.
Review/share after reading:
- Issue/comment draft: D:\Temp\agentledger-demo-...\agentledger-alpha-packet\agentledger-alpha-issue.md
- Markdown packet: D:\Temp\agentledger-demo-...\agentledger-alpha-packet\agentledger-alpha-handoff.md
- JSON packet: D:\Temp\agentledger-demo-...\agentledger-alpha-packet\agentledger-alpha-handoff.json
Keep local:
- Demo workspace: D:\Temp\agentledger-demo-...
- Raw evidence output: D:\Temp\agentledger-demo-...\agentledger-output
- Zip bundle: D:\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345.zip
- Raw AgentLedger evidence unless someone explicitly asks for it.
Feedback to include:
- Command used, such as python -m agentledger try or python -m agentledger alpha --repo . --out .agentledger.
- Platform, shell, Python version, and AgentLedger version.
- Generated review/share files from the alpha packet after you have reviewed them.
- Redacted error text or the first confusing message, with secrets and private source removed.
- What you expected and what happened instead.
Try next:
- python -m agentledger open-latest --repo <demo-repo> --out <agentledger-output>
- python -m agentledger history --repo <demo-repo> --out <agentledger-output>
- python -m agentledger status --repo <demo-repo> --out <agentledger-output> --allow-warnings
- python -m agentledger inspect-report <latest-run>
- python -m agentledger verify-bundle <latest-run>.zip
Next real repo:
- cd <your-repo>
- python -m agentledger alpha-guide --repo . --out .agentledger
Cleanup:
- python -c "import shutil; shutil.rmtree('<workspace>')"
```

## Inspect The Demo Evidence

Run the `Try next:` commands printed by `agentledger try` or `agentledger demo`.
They show:

- latest report paths
- recent run history
- pass/warn/block review status
- a concise report summary
- bundle manifest verification

Use the printed `Next real repo:` commands only after the demo report makes
sense. `alpha-guide` is read-only, so it is safe to run before creating evidence
inside your own checkout.

The demo uses `--privacy-mode summary` by default, so reports keep counts,
paths, and metadata while omitting full command transcript content and full
diffs.

With `--format json`, the payload uses schema `agentledger.demo.v1` and includes
`workspace`, `repo`, `out`, `latest_run`, `paths`, `summary_output`,
`summary_written`, optional `packet`, `try_next`, `cleanup`, and `errors`.

## Public Demo Summary

`--summary-output` writes a compact Markdown file that omits local paths and raw
evidence. It includes the demo result, AgentLedger version, captured demo
command, evidence types produced, privacy mode, what to read first, and what to
keep private.

The summary is meant as a starting point for short posts or GitHub comments.
Review it before sharing, and keep the full run folder and zip bundle local
unless you intentionally choose to share them.

## Alpha Feedback

`agentledger try` and `agentledger demo --packet` write
`agentledger-alpha-issue.md` beside the handoff packet. Use that file as a
copy-ready issue/comment draft after review. Good alpha feedback includes the
command used, platform, shell, Python version, AgentLedger version, generated
review/share files, redacted error text, and the first confusing message.
Run `python -m agentledger support-packet` when you want that checklist, or
`python -m agentledger support-packet --format markdown` when you want a
sanitized issue/comment body without writing files or copying evidence.

Do not attach raw `agentledger-output/`, `.agentledger/` folders, zip bundles,
command transcripts, signing keys, secrets, non-public source, or full reports
unless they have been reviewed and explicitly requested.

## What Stays Local

| Item | Keep local? | Notes |
| --- | --- | --- |
| Demo workspace | Yes | Delete it with the printed cleanup command when done |
| `agentledger-output/` | Yes | This is raw local evidence |
| Run folder | Yes | Contains reports and artifacts |
| Zip bundle | Yes | Useful for verification, but do not commit or post by default |
| Demo alpha packet | Review first | Created only with `--packet`; share listed files only after review |
| Public demo summary | Review first | Path-free by design, but still check before sharing |
| Printed status summary | Usually safe | Review before sharing because paths may reveal local context |

AgentLedger redacts common token, password, API key, and private-key patterns,
but reports can still include local paths, command names, and repository
metadata. Treat evidence as local proof first.

## Next Real Run

For the shortest walkthrough, see `docs/first-run.md`.

After the demo makes sense, run the alpha guide from your target repository:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
python -m agentledger alpha --repo . --out .agentledger
```

For a direct capture:

```powershell
python -m agentledger run --repo . --privacy-mode summary -- python -m pytest
```

Do not commit `.agentledger/`, zip bundles, signing keys, or temporary demo
folders.
