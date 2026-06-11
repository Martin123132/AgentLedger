# Private Alpha Notes

Date: 2026-06-11

## What worked

- Local editable install completed with `python -m pip install -e ".[dev]"`.
- `agentledger --version` returned `agentledger 0.1.0`.
- `python -m agentledger doctor --repo .` correctly reported required tooling as ready.
- `scripts/install-check.ps1` installed AgentLedger into a temporary virtual environment and passed.
- `scripts/smoke.ps1` completed the run/open/history/inspect/verify/compare flow.
- A real AgentLedger capture of `python -m pytest` against this repo completed successfully.
- `open-latest`, `history`, `inspect-report`, and `verify-bundle` all worked on the captured pytest run.
- The generated report summary was easy to scan:
  - command: `python -m pytest`
  - exit code: `0`
  - test framework: `pytest`
  - changed files: `0`
  - bundle verification: OK

## What was confusing

- A plain PowerShell session did not initially have `git` on PATH, even though GitHub Desktop has a bundled git available.
- Older `doctor` output reported `partial` when optional integrations were missing, which was accurate but looked worrying to a first alpha tester.
- `pip` upgrade notices add noise during install and install-check runs.
- `git init` prints the default-branch hint during smoke tests, which makes the smoke output longer than the useful AgentLedger output.
- README still includes an older private-repo push checklist that mentions adding `origin` and pushing `alpha-report-review`; that may confuse testers now that `origin/master` already exists.

## Exact setup friction

When `git` is not on PATH, tests and smoke flows that create temporary git repos fail with:

```text
git : The term 'git' is not recognized as the name of a cmdlet, function, script file, or operable program.
```

For this local pass, adding GitHub Desktop's bundled git to PATH fixed it. The repo now includes a helper for that setup:

```powershell
. .\scripts\ensure-git.ps1
```

## Report readability

- The latest-run paths are clear.
- The history summary is concise and useful.
- The inspect-report summary gives the right level of detail for a human review.
- Bundle verification prints enough detail to confirm the archive is usable.

## Known limitations to tell alpha testers

- Bash smoke requires WSL or another Linux shell with `bash`.
- RepoMori, Jester, and Tokometer are optional integrations. Missing RepoMori/Jester warnings are expected and should not block core AgentLedger usage.
- Evidence folders and zip bundles must stay out of git: `.agentledger/`, `*.zip`, and temp smoke folders are generated output.

## Readiness call

AgentLedger is ready to hand to one outside private alpha tester. The stale private-repo push checklist was cleaned up, Windows Git setup friction now has `scripts/ensure-git.ps1`, and `doctor` now treats missing optional integrations as ready-with-notes rather than partial readiness.
