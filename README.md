# AgentLedger

Local-first black box recorder for AI coding agents.

[![CI](https://github.com/Martin123132/AgentLedger/actions/workflows/ci.yml/badge.svg)](https://github.com/Martin123132/AgentLedger/actions/workflows/ci.yml)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm%20Noncommercial%201.0.0-blue)](LICENSE)

Source-available for non-commercial use under the PolyForm Noncommercial
License 1.0.0. Commercial use requires separate permission.

AgentLedger captures the boring evidence teams need when agents spend tokens,
run commands, touch repositories, and claim work is done:

- before/after git state
- command execution evidence
- changed files and diffs
- best-effort redaction for obvious secrets in captured text
- RepoMori snapshots and handoff packs when available
- Jester diff safety gate when available
- Tokometer local usage summary when available
- Markdown, JSON, and HTML audit reports
- zip evidence bundle with a manifest and SHA-256 checksums

The first product wedge is intentionally simple:

```powershell
agentledger run --repo C:\path\to\repo -- npm test
```

That writes a timestamped evidence folder under `.agentledger/` with:

```text
agentledger-report.md
agentledger-report.json
agentledger-report.html
artifacts/
```

It also writes a sibling `.zip` bundle for easy handoff. Each bundle includes
`agentledger-bundle-manifest.json`, which records the expected file list,
byte sizes, and SHA-256 checksums for verification.
The Markdown and HTML reports start with a review summary and a short human
checklist, review notes, and evidence-file pointers so the latest run can be
triaged quickly before accepting the work.

## Why This Exists

AI coding agents are now doing real work, changing code, and burning money, but
the evidence trail is scattered across chat logs, terminals, git diffs, and
local tool state. AgentLedger turns one agent work session into a compact audit
record a human, buyer, teammate, or another agent can inspect.

Short pitch:

```text
The black box recorder for AI coding agents.
```

Company pitch:

```text
Local-first control tools for AI coding agents: usage metering, repo memory,
execution evidence, and eval gates.
```

## Quick Start

From this checkout:

```powershell
python -m pip install -e ".[dev]"
agentledger --version
python -m agentledger doctor --repo .
python -m agentledger run --repo . -- python -c "print('hello from AgentLedger')"
```

After a run:

```powershell
Get-Content .agentledger\latest.txt
```

Open the `agentledger-report.md` inside that latest run folder.

Five-minute public alpha check:

```powershell
python -m agentledger alpha --repo . --out .agentledger
```

Windows extended alpha check:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

Manual review loop:

```powershell
python -m agentledger run --repo . --out .agentledger --no-repomori --no-jester --no-tokometer -- python -c "print('agentledger smoke')"
python -m agentledger review --out .agentledger --allow-warnings
python -m agentledger status --out .agentledger --allow-warnings
python -m agentledger open-latest --out .agentledger
python -m agentledger open-latest --format json --out .agentledger
python -m agentledger history --out .agentledger
python -m agentledger feedback --out .agentledger --note "First confusing thing: ..."
python -m agentledger feedback --out .agentledger --list
python -m agentledger feedback-summary --out .agentledger
python -m agentledger feedback-export --out .agentledger --output $env:TEMP\agentledger-feedback.md
$run = (Get-Content .agentledger\latest.txt).Trim()
python -m agentledger inspect-report $run
python -m agentledger check --allow-warnings $run
python -m agentledger inspect-bundle "${run}.zip"
python -m agentledger inspect-bundle "${run}.zip" --format json
python -m agentledger verify-bundle "${run}.zip"
python -m agentledger verify-bundle "${run}.zip" --format json
```

Use summary privacy mode when you want counts, paths, and metadata without full
command transcripts or full diffs in the report/bundle:

```powershell
python -m agentledger run --repo . --privacy-mode summary -- python -m pytest
```

You can also set repo defaults in `.agentledger.toml`. In a repo that does not
already have one, start one with:

```powershell
python -m agentledger init-config --repo .
```

This repository includes a public-alpha example at `.agentledger.toml`:

```toml
privacy_mode = "summary"
out = ".agentledger"
repomori = false
jester = false
tokometer = false
zip = true
check_require_tests = true
check_dirty = "warn"
check_max_changed_files = 25
check_allow_warnings = true
```

`run`, `snapshot`, `open-latest`, `history`, `status`, `alpha`, and
`alpha-summary` read that file from the target repo when it exists. `--out`
overrides only the evidence directory for a single command; the repo policy
still applies. `--privacy-mode` overrides the privacy setting for a single
capture. Boolean entries disable optional integrations or zip export by
default. `check_*` entries tune the local review policy used by
`agentledger check`, `agentledger review`, and `agentledger status`.

## CI and smoke checks

Local checks:

```powershell
python -m pip install -e ".[dev]"
agentledger --version
python -m pytest
python -m agentledger alpha --repo . --out .agentledger --json-output $env:TEMP\agentledger-alpha-cli-summary.json --format json
python scripts/check_release_metadata.py
powershell -ExecutionPolicy Bypass -File scripts/install-check.ps1
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1
powershell -ExecutionPolicy Bypass -File scripts/alpha.ps1
powershell -ExecutionPolicy Bypass -File scripts/alpha.ps1 -JsonOutput $env:TEMP\agentledger-alpha-summary.json
python -m agentledger alpha-summary --out .agentledger
python -m agentledger alpha-summary --format json $env:TEMP\agentledger-alpha-summary.json
python scripts/release_command_index.py --version 0.1.8a0 --date 2026-06-14 --format markdown --output $env:TEMP\agentledger-release-command-index.md
python scripts/check_release_process.py
python scripts/release_readiness_report.py --format markdown --output $env:TEMP\agentledger-release-readiness-report.md
python scripts/rehearse_release.py --version 0.1.8a0 --date 2026-06-14 --output-dir $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha
python scripts/verify_release_rehearsal.py $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-manifest.json
python scripts/release_artifact_doctor.py --version 0.1.8a0 --stage rehearsal --rehearsal-manifest $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-manifest.json
python scripts/release_rehearsal_receipt.py $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-manifest.json --format markdown --output $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-receipt.md
powershell -ExecutionPolicy Bypass -File scripts/release-check.ps1
powershell -ExecutionPolicy Bypass -File scripts/release-check.ps1 -RequireCleanGit -JsonOutput $env:TEMP\agentledger-release-check.json
python scripts/release_check_summary.py $env:TEMP\agentledger-release-check.json --output $env:TEMP\agentledger-release-check-summary.md
python scripts/release_artifact_doctor.py --version 0.1.8a0 --stage final-notes --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md
python scripts/finalize_release_notes.py --version 0.1.8a0 --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --pr-ci-url https://github.com/Martin123132/AgentLedger/actions/runs/<pr-run> --master-ci-url https://github.com/Martin123132/AgentLedger/actions/runs/<master-run> --release-readiness-url https://github.com/Martin123132/AgentLedger/actions/runs/<release-readiness-run> --tag-ci-url https://github.com/Martin123132/AgentLedger/actions/runs/<tag-run> --merge-sha <merge-sha> --output $env:TEMP\agentledger-0.1.8-alpha-release.md
python scripts/check_github_release.py --version 0.1.8a0 --format json --output $env:TEMP\agentledger-github-release-check.json
python scripts/check_github_release.py --version 0.1.8a0 --format markdown --output $env:TEMP\agentledger-github-release-check.md
python scripts/release_evidence_packet.py --version 0.1.8a0 --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --release-notes $env:TEMP\agentledger-0.1.8-alpha-release.md --github-release-check-json $env:TEMP\agentledger-github-release-check.json --output $env:TEMP\agentledger-release-evidence.md --json-output $env:TEMP\agentledger-release-evidence.json
python scripts/release_artifact_doctor.py --version 0.1.8a0 --stage post-release --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --release-notes $env:TEMP\agentledger-0.1.8-alpha-release.md
python scripts/post_release_check.py --version 0.1.8a0 --release-check-json $env:TEMP\agentledger-release-check.json --release-check-summary $env:TEMP\agentledger-release-check-summary.md --release-notes $env:TEMP\agentledger-0.1.8-alpha-release.md --output-dir $env:TEMP\agentledger-post-release-0.1.8-alpha
```

```bash
python -m pip install -e ".[dev]"
agentledger --version
python -m pytest
bash ./scripts/smoke.sh
```

There are also GitHub Actions for the same flow (pytest + install check + smoke) under `.github/workflows/ci.yml`.
CI runs on pull requests, `master` pushes, and `v*` release tags; newer runs on
the same ref cancel stale in-progress runs.
For pre-tag release validation, run the manual `Release Readiness` workflow in
GitHub Actions. It executes `.github/workflows/release-check.yml`, which calls
`scripts/release-check.ps1` on Windows with `-RequireCleanGit` by default.
The smoke scripts validate both text and JSON command surfaces.
For CI or bot consumers, see `docs/check-json-ci.md` and
`docs/json-contracts.md`. Agents can also run
`agentledger contracts --format json` to discover supported JSON contracts.

Alpha docs:

- `ALPHA.md`
- `docs/alpha-checklist.md`
- `docs/alpha-tester-guide.md`
- `docs/alpha-feedback-template.md`
- `docs/alpha-notes.md`
- `docs/json-contracts.md`
- `SECURITY.md`
- `CHANGELOG.md`
- `.agentledger.toml`

Alpha install check:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/install-check.ps1
```

That script installs AgentLedger from the local checkout into a temporary virtual environment using local packaging tools, verifies `agentledger --version`, verifies `python -m agentledger --version`, and removes the temporary environment when it finishes.

Alpha one-command pass:

```powershell
python -m agentledger alpha --repo . --out .agentledger
python -m agentledger alpha --repo . --out .agentledger --format json
```

The cross-platform `alpha` command runs doctor, captures a real pytest pass by
default, checks latest status/history/report/bundle evidence, and writes a
machine-readable `agentledger.alpha_summary.v1` summary to
`.agentledger/alpha-summary.json` by default. Pass a command after `--` to
capture something other than the current Python interpreter running `-m pytest`,
and use `--json-output <path>` to write the summary outside the repo. Use
`--strict` when warning status should fail the alpha pass. If required setup is
blocked, `alpha` still writes a summary with config or doctor errors and next
actions, including doctor repair hints, when an output path is available.

Windows extended alpha pass:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

That script additionally runs install verification and smoke verification
before the same captured pytest/status/report/bundle flow. It writes the same
summary schema to `.agentledger/alpha-summary.json` by default; use
`-JsonOutput <path>` to write that summary outside the repo. If doctor setup is
blocked, it writes a blocked summary with repair hints before exiting 2. If the
summary path cannot be written, the script prints a clear error and exits 2.

Inspect that summary without opening JSON by hand:

```powershell
python -m agentledger alpha-summary --out .agentledger
python -m agentledger alpha-summary --out .agentledger --format json
python -m agentledger alpha-summary $env:TEMP\agentledger-alpha-summary.json
```

Alpha release readiness:

```powershell
python scripts/release_command_index.py --version 0.1.8a0 --date 2026-06-14
python scripts/check_release_process.py --version 0.1.8a0 --date 2026-06-14
python scripts/release_readiness_report.py --format markdown --output $env:TEMP\agentledger-release-readiness-report.md
python scripts/rehearse_release.py --version 0.1.8a0 --date 2026-06-14 --output-dir $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha
python scripts/verify_release_rehearsal.py $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-manifest.json
python scripts/release_rehearsal_receipt.py $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-manifest.json --format markdown --output $env:TEMP\agentledger-release-rehearsal-0.1.8-alpha\release-rehearsal-receipt.md
python scripts/prepare_release.py --version 0.1.8a0 --date 2026-06-14 --dry-run
python scripts/prepare_release.py --version 0.1.8a0 --date 2026-06-14 --release-notes-output $env:TEMP\agentledger-0.1.8-alpha-release.md
powershell -ExecutionPolicy Bypass -File scripts/release-check.ps1
powershell -ExecutionPolicy Bypass -File scripts/release-check.ps1 -RequireCleanGit
python scripts/release_notes.py --version 0.1.8a0 --check
python scripts/release_notes.py --version 0.1.8-alpha --output $env:TEMP\agentledger-0.1.8-alpha-release.md
python scripts/release_notes.py --version 0.1.8a0 --notes-file $env:TEMP\agentledger-0.1.8-alpha-release.md --check-publish-ready
```

That script checks version consistency, release-process documentation alignment,
git hygiene, tracked evidence guardrails, source release metadata, wheel build
metadata, pytest, install verification, and the Windows smoke flow, including
the latest status command.
Use `scripts/check_release_metadata.py` directly when you only need the
cross-platform source metadata check for version, license, README, and changelog
alignment.
Use `-RequireCleanGit` before tagging or publishing a release candidate.
Use `-JsonOutput <path>` to write a machine-readable
`agentledger.release_check.v1` summary for CI or agent handoffs. The summary
embeds both `agentledger.release_metadata_check.v1` and
`agentledger.release_process_check.v1` payloads. Keep that file outside the
repo, for example under `$env:TEMP`.
Use `scripts/release_command_index.py` at the start of a release to print the
ordered command flow, artifact filenames, placeholders, and private-evidence
handling reminders. It can also write JSON or Markdown for handoffs.
Use `scripts/check_release_process.py` after generating or editing the command
index to confirm `docs/release-process.md` still documents every generated
command, artifact path, placeholder, and do-not-commit reminder. Its JSON output
uses `agentledger.release_process_check.v1`.
Use `scripts/release_readiness_report.py` for a fast Markdown or JSON preflight
of release metadata, release-process alignment, release notes source, and git
hygiene before the heavier release-check script runs. Its JSON output uses
`agentledger.release_readiness_report.v1`.
Use `scripts/release_check_summary.py` to render the release-check JSON as a
short Markdown summary. The manual GitHub Release Readiness workflow also
appends that Markdown to the job step summary.
Use `scripts/finalize_release_notes.py` after PR, master, Release Readiness, and
tag CI have real GitHub Actions URLs. It refuses dirty release-check JSON,
missing metadata summaries, mismatched versions, placeholder TODO validation,
and non-AgentLedger Actions URLs before writing publish-ready release notes.
Use `scripts/release_artifact_doctor.py` before release rehearsal handoff,
final notes, post-release, or evidence-packet commands to confirm required
artifact paths exist and are valid, and to get concrete next actions when
something is missing.
Use `scripts/check_github_release.py` after publishing to verify the GitHub
release tag, prerelease/draft status, release URL, publish-ready body, and
published timestamp. It can call `gh release view` directly or validate saved
release JSON with `--release-json`.
Use `scripts/release_evidence_packet.py` after the GitHub release check to build
a public-safe `agentledger.release_evidence_packet.v1` handoff summary from the
validated release-check JSON, rendered summary, final release notes, and GitHub
release check JSON. It records validation status and artifact names only; it
refuses `.agentledger/`, zip bundles, and signing-key paths.
Use `scripts/post_release_check.py` after publishing when you want one command
to run the GitHub release check, write `agentledger.github_release_check.v1`,
build the public-safe evidence packet, and write
`agentledger.post_release_check.v1` summary files under one output directory.
Use `scripts/rehearse_release.py` before release prep to dry-run the target
version, draft release notes outside the repo, write the target command index,
source metadata JSON, fast readiness report, release readiness artifacts, and
one local checklist summary under the chosen output directory. It also writes
`release-rehearsal-manifest.json` with file sizes and SHA-256 hashes for the
generated rehearsal outputs.
Use `scripts/verify_release_rehearsal.py` to verify a saved rehearsal output
folder from that manifest later without rerunning the rehearsal.
Use `scripts/release_rehearsal_receipt.py` after verification to write a compact
human handoff with key artifacts, the rehearsal doctor result, and the exact
next `scripts/prepare_release.py` commands.
Use `scripts/prepare_release.py` to move current Unreleased notes into a dated
release section while updating `pyproject.toml` and `src/agentledger/__init__.py`
together. Run it with `--dry-run` first. Add `--release-notes-output` to write
a draft GitHub release body from the prepared changelog.
Use `scripts/release_notes.py` to draft GitHub release notes from the matching
`CHANGELOG.md` section. It also accepts the PEP 440 package version, such as
`0.1.7a0`, when checking that the release section exists. Replace the validation
TODOs with real run links before publishing, then run `--check-publish-ready`
against the final notes file.
See the [release process](docs/release-process.md) for the full release-day
checklist.

Notes:

- Smoke runs use temporary repos and temporary output folders.
- Do not commit evidence folders or bundles. `.agentledger/`, `*.zip`, and related generated paths are already ignored by `.gitignore`.
- Do not commit shared signing keys such as `.agentledger-signing-key`; local key filenames are ignored as a guardrail.
- Treat evidence reports as local proof first. AgentLedger redacts common token, password, API key, and private-key patterns, but you should still review reports before sharing because they can contain command output, file paths, and repository metadata.

For Windows shells that cannot find `git`, AgentLedger includes a helper that locates common Git installs, including GitHub Desktop's bundled git:

```powershell
. .\scripts\ensure-git.ps1
```

Then install the package in editable mode if needed:

```powershell
python -m pip install -e ".[dev]"
```

Contributor sync checklist:

```powershell
git remote -v
git status --short --branch
git branch --show-current
```

For a contribution branch:

```powershell
git switch -c my-agentledger-branch
git push -u origin my-agentledger-branch
```

Open a pull request for review rather than pushing directly to `master`.

## Commands

Capture repository state only:

```powershell
agentledger snapshot --repo C:\path\to\repo
```

Capture state around a command:

```powershell
agentledger run --repo C:\path\to\repo -- npm test
```

Capture a lower-detail report:

```powershell
agentledger run --repo C:\path\to\repo --privacy-mode summary -- npm test
agentledger snapshot --repo C:\path\to\repo --privacy-mode summary
```

`--privacy-mode summary` omits command transcript content and full diffs from
the generated reports and bundles. It also skips optional integrations that can
add detailed local artifacts.

Check local integration readiness:

```powershell
agentledger doctor --repo C:\path\to\repo
agentledger doctor --json
```

Doctor prints a `Hint:` line for missing required setup and optional
integrations, so blocked alpha testers can usually fix the next step without
reading the full guide.

Check the installed CLI version:

```powershell
agentledger --version
python -m agentledger --version
```

Write a starter policy config:

```powershell
agentledger init-config --repo C:\path\to\repo
agentledger init-config --repo C:\path\to\repo --force
```

Skip optional integrations:

```powershell
agentledger run --repo C:\path\to\repo --no-repomori --no-jester --no-tokometer -- pytest
```

Inspect a specific run:

```powershell
agentledger inspect-report .agentledger\2026-06-11T120000Z-abc12345
```

Check a run against the default review policy:

```powershell
agentledger check .agentledger\2026-06-11T120000Z-abc12345
agentledger check --format json .agentledger\2026-06-11T120000Z-abc12345
agentledger check --allow-warnings .agentledger\2026-06-11T120000Z-abc12345
```

`check` returns `0` for pass, `1` for warn, and `2` for block. Use
`--allow-warnings` when a script should only fail on block-level issues. The
default policy blocks failed commands or incomplete reports, and warns on
missing test evidence, dirty final repo state, report warnings, optional
artifact warnings, and redaction markers.

JSON output includes stable CI fields: `ok`, `summary`, `rule_counts`,
`warning_rules`, and `blocking_rules`, alongside the full `rules` list.

Review the latest run with report paths and policy status in one command:

```powershell
agentledger review --out .agentledger --allow-warnings
agentledger review .agentledger\2026-06-11T120000Z-abc12345
agentledger review --format json --out .agentledger --allow-warnings
agentledger review --out .agentledger --history-limit 5 --allow-warnings
```

`review` uses the same pass/warn/block policy and exit codes as `check`, then
adds the Markdown/JSON/HTML report paths, zip bundle path when present, warning
or blocking rule summaries, recent run context, previous-run comparison when
available, and a short next-action hint.
It shows the three most recent runs by default; pass `--history-limit 0` to
hide that context.

Show the latest run status, evidence paths, feedback counts, and next action:

```powershell
agentledger status --out .agentledger --allow-warnings
agentledger status --out .agentledger --format json --allow-warnings
```

`status` uses the same pass/warn/block policy as `review`, then adds local
feedback counts so an alpha pass can start from one compact command.

Inspect the latest one-command alpha pass summary:

```powershell
agentledger alpha-summary --out .agentledger
agentledger alpha-summary --out .agentledger --format json
agentledger alpha-summary $env:TEMP\agentledger-alpha-summary.json
```

`alpha-summary` validates the `agentledger.alpha_summary.v1` file written by
`agentledger alpha` or `scripts/alpha.ps1`, prints the important run paths and
feedback counts, and returns a nonzero exit code if the summary is missing,
invalid, or records errors.

You can tune the default check policy in `.agentledger.toml`:

```toml
check_require_tests = true
check_dirty = "block"
check_max_changed_files = 10
check_allow_warnings = false
```

`check_require_tests = true` turns missing test evidence into a block.
`check_dirty` accepts `"pass"`, `"warn"`, or `"block"` for final dirty repo
state. `check_max_changed_files` blocks runs above the configured changed-file
count, even when dirty state is otherwise allowed. `check_allow_warnings = true`
makes warnings exit `0`, the same as passing `--allow-warnings`.

Discover machine-readable command contracts:

```powershell
agentledger contracts
agentledger contracts --format json
```

Open the latest run summary paths:

```powershell
agentledger open-latest --out .agentledger
agentledger open-latest --out .agentledger --format json
```

JSON output includes `ok`, `latest_run`, report `paths`, `missing_reports`,
and `errors` for CI or agent handoffs.

List recent runs:

```powershell
agentledger history --out .agentledger
agentledger history --out .agentledger --format json
agentledger history --out .agentledger --limit 5
```

Record local alpha feedback against the latest run:

```powershell
agentledger feedback --out .agentledger --note "First confusing thing: ..."
agentledger feedback --out .agentledger --category docs --severity high --note "Could not find the HTML report."
agentledger feedback --out .agentledger --list
agentledger feedback --out .agentledger --format json --note "Review command was clear."
agentledger feedback-summary --out .agentledger
agentledger feedback-summary --out .agentledger --category docs --format json
agentledger feedback-export --out .agentledger --output $env:TEMP\agentledger-feedback.md
agentledger feedback-export --out .agentledger --output $env:TEMP\agentledger-feedback.json --output-format json --format json
```

`feedback` writes `alpha-feedback.jsonl` inside the selected run folder. It
redacts obvious secrets in notes before saving them, but feedback files are
still local evidence and should not be committed or shared without review.
`feedback-summary` reads those local feedback files across recent run folders
so tester friction can be reviewed without opening each run directory.
`feedback-export` writes a reviewed Markdown or JSON export that omits local
run directories and feedback file paths. Review the exported notes before
sharing because redaction is best-effort.

The normal local review loop is:

```powershell
agentledger run --repo . --out .agentledger --no-repomori --no-jester --no-tokometer -- python -c "print('agentledger smoke')"
agentledger review --out .agentledger --allow-warnings
agentledger review --out .agentledger --history-limit 5 --allow-warnings
agentledger status --out .agentledger --allow-warnings
agentledger open-latest --out .agentledger
agentledger open-latest --out .agentledger --format json
agentledger history --out .agentledger
agentledger feedback --out .agentledger --note "First confusing thing: ..."
agentledger feedback-summary --out .agentledger
agentledger feedback-export --out .agentledger --output $env:TEMP\agentledger-feedback.md
$run = (Get-Content .agentledger\latest.txt).Trim()
agentledger inspect-report $run
agentledger check --allow-warnings $run
agentledger inspect-bundle "${run}.zip"
agentledger inspect-bundle "${run}.zip" --format json
agentledger verify-bundle "${run}.zip"
agentledger verify-bundle "${run}.zip" --format json
```

With a repo `.agentledger.toml`, the same loop can use the configured output
folder and privacy mode:

```powershell
agentledger run --repo . -- python -m pytest
agentledger review --repo . --allow-warnings
agentledger review --repo . --history-limit 5 --allow-warnings
agentledger status --repo . --allow-warnings
agentledger open-latest --repo .
agentledger history --repo .
agentledger feedback --repo . --note "First confusing thing: ..."
agentledger feedback-summary --repo .
agentledger feedback-export --repo . --output $env:TEMP\agentledger-feedback.md
$run = (Get-Content .agentledger\latest.txt).Trim()
agentledger check $run
```

Compare two runs:

```powershell
agentledger compare .agentledger\2026-06-11T120000Z-abc12345 .agentledger\2026-06-11T120100Z-def67890
```

Inspect or verify a produced zip bundle:

```powershell
agentledger inspect-bundle .agentledger\2026-06-11T120000Z-abc12345.zip
agentledger inspect-bundle .agentledger\2026-06-11T120000Z-abc12345.zip --format json
agentledger verify-bundle .agentledger\2026-06-11T120000Z-abc12345.zip
agentledger verify-bundle .agentledger\2026-06-11T120000Z-abc12345.zip --format json
```

`inspect-bundle` reads a bundle without a signing key and summarizes manifest
metadata, signature presence, report members, command outcome, artifacts, and a
pass/warn/block review status. Use it for quick triage; it does not verify a
shared-key signature.
`verify-bundle` requires `agentledger-bundle-manifest.json` inside the zip and
checks each listed file's byte size and SHA-256 digest before reporting
`Bundle OK`. JSON output includes `ok`, `manifest`, `signature`, report
members, artifact counts, and `errors`.

Optionally sign a bundle manifest with a local shared-key HMAC:

```powershell
agentledger signing-key --repo . --key-file .agentledger-signing-key
agentledger signing-key --repo . --key-file .agentledger-signing-key --format json
agentledger sign-bundle .agentledger\2026-06-11T120000Z-abc12345.zip --key-file .agentledger-signing-key
agentledger sign-bundle .agentledger\2026-06-11T120000Z-abc12345.zip --key-file .agentledger-signing-key --format json
agentledger verify-bundle .agentledger\2026-06-11T120000Z-abc12345.zip --signature-key-file .agentledger-signing-key
agentledger verify-bundle .agentledger\2026-06-11T120000Z-abc12345.zip --signature-key-file .agentledger-signing-key --require-signature
agentledger verify-bundle .agentledger\2026-06-11T120000Z-abc12345.zip --format json --signature-key-file .agentledger-signing-key --require-signature
```

This is a shared-key HMAC-SHA256 integrity check over the bundle manifest, not
a public-key signature. `sign-bundle --format json` reports the signature
member, signed manifest, algorithm, and digest but omits the raw HMAC value.
`signing-key` checks that the key file exists, is non-empty, and is not tracked
or accidentally unignored when it lives inside the target repo. It never prints
the key or a key digest.
Keep signing keys private, rotate them if shared too widely, and do not commit
them.

## Current Integrations

### Git

Always on. Captures:

- current branch
- current HEAD
- `git status --short`
- `git diff --stat`
- redacted tracked diff

### Command Transcripts

For `agentledger run`, full stdout and stderr are stored under:

```text
artifacts/command/stdout.txt
artifacts/command/stderr.txt
```

AgentLedger also labels common test commands such as `pytest`, `npm test`,
`vitest`, `jest`, `go test`, and `cargo test` so reports can distinguish
verification runs from ordinary shell commands.

Command transcripts and report tails are redacted for common secret-looking
patterns before they are written to disk.

For lower-detail sharing, use `--privacy-mode summary` to omit transcript
content and full diffs entirely.

### RepoMori

When `python -m repomori` is available, AgentLedger runs before/after snapshots
and stores the RepoMori output under the run artifacts folder.

This is the repo-memory and handoff layer.

If RepoMori is missing, AgentLedger keeps running and records a warning artifact
instead. `agentledger doctor` still reports ready when required checks pass and
marks RepoMori as an optional integration that is not configured.

### Memento Mori Jester

When `jester` or `memento-mori-jester` is on PATH, AgentLedger pipes `git diff`
into the Jester diff gate.

This is the safety and overconfidence layer.

### Tokometer

AgentLedger imports Tokometer's local `getUsageSummary` parser through a small
Node/TS bridge when `npx tsx` and the Tokometer checkout are available. The
artifact is intentionally bounded: it keeps usage totals, windows, limits,
freshness, alerts, top sessions, and parser counts, but omits the full scanned
session-file list.

This is the cost and usage layer.

Override the Tokometer checkout path when needed:

```powershell
$env:AGENTLEDGER_TOKOMETER_ROOT='C:\path\to\codex-token-gauge'
```

## Product Shape

AgentLedger is the wrapper product. It should orchestrate existing assets first
instead of copying all of their internals.

Core assets it can use:

- Tokometer: token usage, burn rate, cost dashboard
- RepoMori: repo memory, source-backed context, handoff packs, provenance
- Memento Mori Jester: command/diff/final-answer safety checks
- The Marked Bench: eval gates, result cards, scoring/report schemas
- ChatP2P: signed work packets and verified result records
- Rat-Trap Proof Kit: buyer-facing proof bundle structure
- TokenSquash: later compact protocol for repeated agent workflows

## Roadmap

### v0.1 Public Alpha Wedge

- CLI evidence capture
- Markdown/JSON report export
- before/after git state
- optional RepoMori/Jester/Tokometer hooks
- local smoke tests

### v0.2 Evidence Bundle

- zip export
- HTML report
- command transcript files
- test-result parser
- richer file-touch manifest
- final-answer verification checklist

### v0.3 Usage + Cost

- direct Tokometer usage summary import
- per-session token deltas
- estimated cost model
- weekly/monthly projections in report

### v0.4 Repo Memory

- first-class RepoMori handoff capsule links
- changed-file source context
- before/after pack comparison summary
- chain/anchor verification section

### v0.5 Eval Gate

- Marked Bench compatible gate schema
- project-local eval suites
- pass/warn/block policies
- result-card export

### v1.0 Buyer Pilot

- desktop dashboard
- signed evidence bundles
- team policy config
- pilot report template
- packaged alpha installer

## License

AgentLedger is source-available under the PolyForm Noncommercial License 1.0.0.
This is not an OSI open-source license because commercial use is restricted.
See `LICENSE` for terms and `COMMERCIAL.md` for commercial-use enquiries.
