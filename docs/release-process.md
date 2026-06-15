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

Generate an operator command index for the exact version and date when you want
one ordered handoff:

```powershell
python scripts/release_command_index.py --version 0.1.8a0 --date 2026-06-14 --format markdown --output $env:TEMP\agentledger-release-command-index.md
python scripts/check_release_process.py --version 0.1.8a0 --date 2026-06-14
```

The command index reports `agentledger.release_command_index.v1`, the expected
artifact filenames, placeholder values that must be replaced, and the
release-day command order. The release-process check reports
`agentledger.release_process_check.v1` and confirms this checklist still covers
every generated command, artifact path, placeholder, and do-not-commit reminder.

## 2. Prepare source files

Run a local rehearsal first. It writes draft release notes, the target command
index, source metadata, fast readiness, and release-check summaries outside the
repo:

```powershell
python scripts/rehearse_release.py --version 0.1.8a0 --date 2026-06-14 --output-dir $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha
python scripts/verify_release_rehearsal.py $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-manifest.json
python scripts/release_artifact_doctor.py --version 0.1.8a0 --stage rehearsal --rehearsal-manifest $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-manifest.json
python scripts/release_rehearsal_receipt.py $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-manifest.json --format markdown --output $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-receipt.md
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
- The rehearsal summary lists git hygiene, target command index, source
  metadata, fast readiness, dry-run release prep, draft release notes,
  publish-readiness status, and release-check status.
- The rehearsal output directory contains `release-command-index.md`,
  `release-command-index.json`, `release-metadata.json`, and, from a git
  checkout, `release-readiness-report.md` and `release-readiness-report.json`.
- The rehearsal output directory contains `release-rehearsal-manifest.json`
  using `agentledger.release_rehearsal_manifest.v1`, with file sizes, SHA-256
  hashes, and handling notes for every generated rehearsal output except the
  manifest itself.
- `scripts/verify_release_rehearsal.py` reports
  `agentledger.release_rehearsal_manifest_verify.v1` with `ok=true`.
- `scripts/release_artifact_doctor.py --stage rehearsal` reports
  `agentledger.release_artifact_doctor.v1` with `ok=true` before source files
  are changed.
- `scripts/release_rehearsal_receipt.py` writes
  `release-rehearsal-receipt.md` using
  `agentledger.release_rehearsal_receipt.v1`, including key artifacts and the
  exact next `scripts/prepare_release.py` commands.
- The draft release notes file is outside the repo, usually under `$env:TEMP`.

Do not commit generated release note files, evidence folders, zip bundles, or
signing keys.

## 3. Validate before PR

```powershell
python scripts/check_release_metadata.py
python scripts/release_readiness_report.py --format markdown --output $env:TEMP\agentledger-release-readiness-report.md
python scripts/release_notes.py --version 0.1.8a0 --check
python -m pytest
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/release-check.ps1 -RequireCleanGit -JsonOutput $env:TEMP\agentledger-release-check.json
python scripts/release_check_summary.py $env:TEMP\agentledger-release-check.json --output $env:TEMP\agentledger-release-check-summary.md
```

`scripts/check_release_metadata.py` is the cross-platform source metadata gate
for version, license, README, and changelog alignment. `scripts/release-check.ps1`
also runs that check, then validates version consistency, release-process
documentation alignment, changelog release notes source, git hygiene, isolated
wheel metadata, tests, install check, and the Windows smoke flow, including the
latest status command. `-JsonOutput` writes an `agentledger.release_check.v1`
summary, including the `agentledger.release_metadata_check.v1` and
`agentledger.release_process_check.v1` payloads, that can be referenced from PR
or release notes without parsing console output. `scripts/release_check_summary.py`
renders that JSON into a short Markdown summary for review notes or handoffs.
Use `scripts/release_readiness_report.py` for a fast preflight of metadata,
release-process alignment, release notes source, and git hygiene before running
the heavier wheel, pytest, install, and smoke checks. The report JSON uses
`agentledger.release_readiness_report.v1`.

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

Useful local/GitHub commands:

```powershell
git status --short --branch --untracked-files=all
git diff --stat
gh pr create --draft --fill
gh pr checks <pr-number> --watch --interval 10
gh pr ready <pr-number>
gh pr merge <pr-number> --merge --delete-branch
git switch master
git pull --ff-only origin master
```

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
- The release-check summary includes release metadata and release-process check
  counts.
- The workflow URL is added to the GitHub release notes validation section.

## 6. Tag and verify

Only tag after master CI and Release Readiness have passed.

```powershell
git switch master
git pull --ff-only origin master
git status --short --branch
git tag v0.1.8-alpha
git push origin v0.1.8-alpha
gh run list --repo Martin123132/AgentLedger --limit 5
gh run watch <tag-run-id> --repo Martin123132/AgentLedger --interval 10 --exit-status
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
python scripts/release_artifact_doctor.py --version 0.1.8a0 --stage final-notes --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md
python scripts/finalize_release_notes.py --version 0.1.8a0 --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --pr-ci-url https://github.com/Martin123132/AgentLedger/actions/runs/<pr-run> --master-ci-url https://github.com/Martin123132/AgentLedger/actions/runs/<master-run> --release-readiness-url https://github.com/Martin123132/AgentLedger/actions/runs/<release-readiness-run> --tag-ci-url https://github.com/Martin123132/AgentLedger/actions/runs/<tag-run> --merge-sha <merge-sha> --output $env:TEMP\agentledger-0.1.8-alpha-release.md
python scripts/release_notes.py --version 0.1.8a0 --notes-file $env:TEMP\agentledger-0.1.8-alpha-release.md --check-publish-ready
gh release create v0.1.8-alpha --repo Martin123132/AgentLedger --title v0.1.8-alpha --notes-file $env:TEMP\agentledger-0.1.8-alpha-release.md --prerelease
```

`scripts/release_artifact_doctor.py --stage final-notes` checks that the
release-check JSON and rendered summary exist, match the release version, and
are suitable for final release notes before `scripts/finalize_release_notes.py`
runs.

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
python scripts/release_artifact_doctor.py --version 0.1.8a0 --stage post-release --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --release-notes $env:TEMP\agentledger-0.1.8-alpha-release.md
python scripts/post_release_check.py --version 0.1.8a0 --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --release-notes $env:TEMP\agentledger-0.1.8-alpha-release.md --output-dir $env:TEMP\agentledger-post-release-0.1.8-alpha
python scripts/release_notes.py --version 0.1.8a0 --check
```

`scripts/release_artifact_doctor.py --stage post-release` checks that the
release-check artifacts and final release notes exist and are publish-ready
before `scripts/post_release_check.py` calls GitHub and builds handoff files. Use
`--stage evidence-packet` before the lower-level
`scripts/release_evidence_packet.py` command when validating an existing
`agentledger-github-release-check.json`.

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
python scripts/release_artifact_doctor.py --version 0.1.8a0 --stage evidence-packet --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --release-notes $env:TEMP\agentledger-0.1.8-alpha-release.md --github-release-check-json $env:TEMP\agentledger-github-release-check.json
python scripts/release_evidence_packet.py --version 0.1.8a0 --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --release-notes $env:TEMP\agentledger-0.1.8-alpha-release.md --github-release-check-json $env:TEMP\agentledger-github-release-check.json --output $env:TEMP\agentledger-release-evidence.md --json-output $env:TEMP\agentledger-release-evidence.json
```

Confirm:

- The release is marked as a prerelease.
- The release body includes validation links.
- `scripts/release_artifact_doctor.py` reports
  `agentledger.release_artifact_doctor.v1` with `ok=true` before final release
  notes, post-release commands, and rehearsal handoffs.
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
  committed. This includes `.agentledger/`, `*.zip`, `.agentledger-signing-key`,
  signing keys, and temp release artifacts.
- `CHANGELOG.md` is ready for the next `Unreleased` entries.

