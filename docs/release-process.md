# Release Process

This checklist is for preparing and publishing an AgentLedger alpha release from
a clean local checkout. It assumes `origin` points at `Martin123132/AgentLedger`
and that GitHub Actions is available.

Use the package version in commands that edit source files, for example
`0.1.8a0`. Use the release label for tags and GitHub release names, for example
`v0.1.8-alpha`.

## 1. Start clean

```powershell
git switch master
git pull --ff-only origin master
git status --short --branch
python -m pip install -e ".[dev]"
python -m pytest
```

Expected result:

- Local `master` matches `origin/master`.
- The working tree is clean before release prep starts.
- `python -m pytest` passes.

## 2. Prepare source files

Run a local rehearsal first. It writes draft release notes and summaries outside
the repo:

```powershell
python scripts/rehearse_release.py --version 0.1.8a0 --date 2026-06-14 --output-dir $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha
```

Then run the release prep dry run:

```powershell
python scripts/prepare_release.py --version 0.1.8a0 --date 2026-06-14 --release-notes-output $env:TEMP\agentledger-0.1.8-alpha-release.md --dry-run
```

Then write the source changes and draft release notes:

```powershell
python scripts/prepare_release.py --version 0.1.8a0 --date 2026-06-14 --release-notes-output $env:TEMP\agentledger-0.1.8-alpha-release.md
```

Expected result:

- `pyproject.toml` and `src/agentledger/__init__.py` contain the new package
  version.
- `CHANGELOG.md` has an empty `Unreleased` section followed by a dated release
  section.
- The rehearsal summary lists git hygiene, dry-run release prep, draft release
  notes, publish-readiness status, and release-check status.
- The draft release notes file is outside the repo, usually under `$env:TEMP`.

Do not commit generated release note files, evidence folders, zip bundles, or
signing keys.

## 3. Validate before PR

```powershell
python scripts/check_release_metadata.py
python scripts/release_notes.py --version 0.1.8a0 --check
python -m pytest
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/release-check.ps1 -RequireCleanGit -JsonOutput $env:TEMP\agentledger-release-check.json
python scripts/release_check_summary.py $env:TEMP\agentledger-release-check.json --output $env:TEMP\agentledger-release-check-summary.md
```

`scripts/check_release_metadata.py` is the cross-platform source metadata gate
for version, license, README, and changelog alignment. `scripts/release-check.ps1`
also runs that check, then validates version consistency, changelog release notes
source, git hygiene, isolated wheel metadata, tests, install check, and the
Windows smoke flow, including the latest status command. `-JsonOutput` writes an
`agentledger.release_check.v1` summary, including the
`agentledger.release_metadata_check.v1` payload, that can be referenced from PR
or release notes without parsing console output. `scripts/release_check_summary.py`
renders that JSON into a short Markdown summary for review notes or handoffs.

If `-RequireCleanGit` fails because release prep changes are uncommitted, commit
the intended source changes and rerun the command from that clean branch.

## 4. Open and merge the PR

Use a release-prep branch such as `alpha-release-0.1.8` and open a draft PR. The
PR body should include:

- the package version and release label
- the path to the draft release notes file
- local `python -m pytest` result
- local `scripts/release-check.ps1 -RequireCleanGit` result
- local release-check JSON summary path or status

Before merging:

- PR CI must pass on Ubuntu and Windows.
- No `.agentledger/`, `*.zip`, release-note temp files, or signing keys should
  appear in `git diff --stat` or `git status --short --untracked-files=all`.

After merging, confirm master CI passes for the merge commit.

## 5. Run release readiness on master

Trigger the manual workflow:

```powershell
gh workflow run "Release Readiness" --repo Martin123132/AgentLedger --ref master -f require_clean_git=true -f skip_editable_install=false
```

Watch it:

```powershell
gh run list --repo Martin123132/AgentLedger --workflow "Release Readiness" --limit 1
gh run watch <run-id> --repo Martin123132/AgentLedger --interval 10 --exit-status
```

Expected result:

- The manual Release Readiness workflow passes on the merge commit.
- The workflow logs include the release-check JSON summary.
- The workflow step summary includes the rendered release-check Markdown summary.
- The workflow URL is added to the GitHub release notes validation section.

## 6. Tag and verify

Only tag after master CI and Release Readiness have passed.

```powershell
git switch master
git pull --ff-only origin master
git status --short --branch
git tag v0.1.8-alpha
git push origin v0.1.8-alpha
```

Watch the tag CI run from GitHub Actions and add the tag workflow URL to the
release notes validation section.

## 7. Publish the GitHub release

Create a prerelease from tag `v0.1.8-alpha` using the draft notes generated by
`scripts/prepare_release.py`. Before publishing, replace every validation TODO
with real links or commit identifiers:

- local release-check result
- PR CI URL
- master CI URL
- Release Readiness workflow URL
- tag CI URL

Then validate the final notes file:

```powershell
python scripts/finalize_release_notes.py --version 0.1.8a0 --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --pr-ci-url https://github.com/Martin123132/AgentLedger/actions/runs/<pr-run> --master-ci-url https://github.com/Martin123132/AgentLedger/actions/runs/<master-run> --release-readiness-url https://github.com/Martin123132/AgentLedger/actions/runs/<release-readiness-run> --tag-ci-url https://github.com/Martin123132/AgentLedger/actions/runs/<tag-run> --merge-sha <merge-sha> --output $env:TEMP\agentledger-0.1.8-alpha-release.md
python scripts/release_notes.py --version 0.1.8a0 --notes-file $env:TEMP\agentledger-0.1.8-alpha-release.md --check-publish-ready
```

`scripts/finalize_release_notes.py` builds the publish-ready GitHub release body
from `CHANGELOG.md`, clean release-check JSON, the rendered release-check
Markdown summary, and real GitHub Actions run URLs. It refuses dirty
release-check results, mismatched versions, missing metadata summaries,
placeholder validation TODOs, non-AgentLedger Actions URLs, and invalid merge
SHAs.

Keep the alpha footer in the release notes unless there is a deliberate reason
to remove it.

## 8. Post-release checks

After publishing:

```powershell
git status --short --branch
gh release view v0.1.8-alpha --repo Martin123132/AgentLedger
python scripts/post_release_check.py --version 0.1.8a0 --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --release-notes $env:TEMP\agentledger-0.1.8-alpha-release.md --output-dir $env:TEMP\agentledger-post-release-0.1.8-alpha
python scripts/release_notes.py --version 0.1.8a0 --check
```

`scripts/post_release_check.py` runs `scripts/check_github_release.py` logic,
writes `agentledger-github-release-check.json` and
`agentledger-github-release-check.md`, then builds
`agentledger-release-evidence.json` and `agentledger-release-evidence.md` with
`scripts/release_evidence_packet.py`. It also writes
`agentledger-post-release-check.json` and `agentledger-post-release-check.md`
as the wrapper-level summary. Use the lower-level scripts directly when
debugging one artifact at a time:

```powershell
python scripts/check_github_release.py --version 0.1.8a0 --format json --output $env:TEMP\agentledger-github-release-check.json
python scripts/check_github_release.py --version 0.1.8a0 --format markdown --output $env:TEMP\agentledger-github-release-check.md
python scripts/release_evidence_packet.py --version 0.1.8a0 --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --release-notes $env:TEMP\agentledger-0.1.8-alpha-release.md --github-release-check-json $env:TEMP\agentledger-github-release-check.json --output $env:TEMP\agentledger-release-evidence.md --json-output $env:TEMP\agentledger-release-evidence.json
```

Confirm:

- The release is marked as a prerelease.
- The release body includes validation links.
- `scripts/post_release_check.py` reports `agentledger.post_release_check.v1`
  with `ok=true`, writes the GitHub release check artifacts, and builds the
  evidence packet.
- `scripts/check_github_release.py` reports `agentledger.github_release_check.v1`
  with `ok=true` inside the post-release output directory.
- `scripts/release_evidence_packet.py` reports
  `agentledger.release_evidence_packet.v1` with `ok=true`, stores only
  validation status and artifact names, and refuses `.agentledger/`, zip
  bundles, and signing-key paths.
- No local evidence bundles, signing keys, or temp release-note files were
  committed.
- `CHANGELOG.md` is ready for the next `Unreleased` entries.

