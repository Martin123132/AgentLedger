# AgentLedger Demo

`agentledger demo` is the safest first run for a new user. It creates a tiny
temporary git repository, captures a real verification command, and prints the
report paths without touching the current repository.

## Run It

From an AgentLedger checkout:

```powershell
python -m pip install -e ".[dev]"
python -m agentledger demo
```

Use an empty directory when you want predictable paths:

```powershell
python -m agentledger demo --output-dir $env:TEMP\agentledger-demo
```

The chosen `--output-dir` must be empty. This avoids mixing demo evidence with
other files.

Use JSON output when a wrapper, script, or another agent needs the evidence
paths without scraping text:

```powershell
python -m agentledger demo --format json
```

## What It Does

The command creates:

- `demo-repo/`: a tiny git repository with `README.md` and `test_demo.py`
- `agentledger-output/`: the local AgentLedger evidence directory
- one timestamped run folder under `agentledger-output/`
- a sibling `.zip` evidence bundle beside that run folder

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
Workspace: C:\Users\you\AppData\Local\Temp\agentledger-demo-...
Demo repo: C:\Users\you\AppData\Local\Temp\agentledger-demo-...\demo-repo
Evidence output: C:\Users\you\AppData\Local\Temp\agentledger-demo-...\agentledger-output
Latest run: C:\Users\you\AppData\Local\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345
Markdown report: C:\Users\you\AppData\Local\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345\agentledger-report.md
JSON report: C:\Users\you\AppData\Local\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345\agentledger-report.json
HTML report: C:\Users\you\AppData\Local\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345\agentledger-report.html
Bundle: C:\Users\you\AppData\Local\Temp\agentledger-demo-...\agentledger-output\2026-06-17T000000Z0000-abc12345.zip
Try next:
- python -m agentledger open-latest --repo <demo-repo> --out <agentledger-output>
- python -m agentledger history --repo <demo-repo> --out <agentledger-output>
- python -m agentledger status --repo <demo-repo> --out <agentledger-output> --allow-warnings
- python -m agentledger inspect-report <latest-run>
- python -m agentledger verify-bundle <latest-run>.zip
Cleanup:
- python -c "import shutil; shutil.rmtree('<workspace>')"
```

## Inspect The Demo Evidence

Run the `Try next:` commands printed by `agentledger demo`. They show:

- latest report paths
- recent run history
- pass/warn/block review status
- a concise report summary
- bundle manifest verification

The demo uses `--privacy-mode summary` by default, so reports keep counts,
paths, and metadata while omitting full command transcript content and full
diffs.

With `--format json`, the payload uses schema `agentledger.demo.v1` and includes
`workspace`, `repo`, `out`, `latest_run`, `paths`, `try_next`, `cleanup`, and
`errors`.

## What Stays Local

| Item | Keep local? | Notes |
| --- | --- | --- |
| Demo workspace | Yes | Delete it with the printed cleanup command when done |
| `agentledger-output/` | Yes | This is raw local evidence |
| Run folder | Yes | Contains reports and artifacts |
| Zip bundle | Yes | Useful for verification, but do not commit or post by default |
| Printed status summary | Usually safe | Review before sharing because paths may reveal local context |

AgentLedger redacts common token, password, API key, and private-key patterns,
but reports can still include local paths, command names, and repository
metadata. Treat evidence as local proof first.

## Next Real Run

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
