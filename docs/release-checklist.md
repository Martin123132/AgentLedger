# Private Alpha Release Checklist

Use this checklist before tagging an AgentLedger alpha release. It is a local
preflight, not a publish step.

## Start Clean

```powershell
git switch master
git pull --ff-only origin master
git status --short --branch
python -m pip install -e ".[dev]"
```

Expected result:

- Local `master` matches `origin/master`.
- The working tree is clean before release prep starts.
- The editable install can run `python -m agentledger --version`.

## Verify The Checkout

```powershell
python -m pytest
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\smoke.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\release-dry-run.ps1
```

`scripts\release-dry-run.ps1` safely removes old local build output, builds a
wheel into a temporary wheelhouse, installs that built wheel into a temporary
virtual environment, and runs the main smoke flow from the installed package.
It also runs `agentledger pack-alpha` in a temporary git repository.

The temporary smoke evidence and alpha packet are isolated under `$env:TEMP`
and are removed when the script exits.

## Release Gate

Before preparing a tag or GitHub prerelease, run the full release gate from a
clean committed branch:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\release-check.ps1 -RequireCleanGit -JsonOutput $env:TEMP\agentledger-release-check.json
python scripts\release_check_summary.py $env:TEMP\agentledger-release-check.json --output $env:TEMP\agentledger-release-check-summary.md
```

Expected result:

- `agentledger.release_check.v1` reports `ok=true`.
- The release-check summary says the branch is ready.
- The release metadata, release-process docs, tests, install check, and smoke
  checks all pass.

## Evidence And Alpha Packet

For a tester handoff after a successful local alpha run:

```powershell
python -m agentledger alpha --repo . --out .agentledger
python -m agentledger pack-alpha --out .agentledger
python -m agentledger open-packet --out .agentledger
```

Share only the reviewed files printed by `pack-alpha`. Do not share or commit
raw `.agentledger/` run folders, zip bundles, command transcripts, signing
keys, or temporary release artifacts. Pass `--output-dir` only when a
predictable packet folder is useful.

## Do Not Commit

Confirm these are absent from `git status --short --untracked-files=all` before
committing release-prep work:

- `.agentledger/`
- `*.zip`
- `.agentledger-signing-key`
- `agentledger-signing-key*`
- `agentledger-release-rehearsal*`
- release notes or evidence files written under `$env:TEMP`

## Then Use The Full Release Process

This checklist proves the current checkout can be packaged, installed, smoked,
and alpha-packed. Use `docs\release-process.md` for the full release-day flow:
release rehearsal, release prep, PR validation, master CI, manual Release
Readiness workflow, tag CI, GitHub prerelease, and post-release checks.
