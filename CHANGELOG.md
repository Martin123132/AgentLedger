# Changelog

## Unreleased

- Added `agentledger.report_integrity.v1` canonical SHA-256 self-digests and
  previous-run links to new evidence reports.
- Added `agentledger verify-chain` text and JSON checks for edited reports,
  missing predecessors, forks, cycles, and legacy history coverage.
- Added report integrity status to history, inspect-report, Markdown, and HTML
  without adding repository paths or evidence contents to chain metadata.

## 0.1.30-alpha - 2026-07-10

- Added a privacy-safe `agentledger.environment.v1` fingerprint to evidence
  reports with AgentLedger, OS, Python, and Git versions plus the starting Git
  commit.
- Added bounded SHA-256 fingerprints for up to 50 recognized tracked
  dependency lockfiles without copying lockfile contents, environment
  variables, hostnames, or executable paths.
- Added measured command duration to report JSON, Markdown, HTML, and
  `inspect-report` output.

## 0.1.29-alpha - 2026-07-09

- Added command-scoped change attribution that separates pre-existing dirty
  files from persistent changes made during a recorded command, including
  files changed in commits that leave the working tree clean.
- Added privacy-safe dirty-file size and SHA-256 fingerprints so further edits
  to an already-dirty file can be detected without copying file contents.
- Removed the implicit OneDrive Tokometer checkout fallback; optional
  Tokometer collection now requires an explicit
  `AGENTLEDGER_TOKOMETER_ROOT`.
- Excluded AgentLedger's selected evidence output directory from Git boundary
  snapshots so recorder-generated files are not attributed to the command.

## 0.1.28-alpha - 2026-07-07

- Added `agentledger doctor --format markdown` so alpha testers can paste a
  copy-ready, path-redacted setup report without exposing local paths or raw
  evidence.
- Updated first-run, troubleshooting, tester, and feedback docs to point setup
  confusion toward reviewed doctor Markdown instead of raw terminal logs.

## 0.1.27-alpha - 2026-06-30

- Polished the README first-look path so new public-alpha users see the
  install, `agentledger try`, and support-packet commands before the feature
  list.
- Added a sanitized first-run output example with placeholder report,
  packet, and support-packet excerpts that are safe to inspect publicly.
- Added checked public-alpha recipes for capturing `pytest`, `unittest`,
  `npm test`, generic commands, latest-run inspection, and privacy-safe
  feedback.

## 0.1.26-alpha - 2026-06-27

- Added a checked alpha install confidence guide for `v0.1.25-alpha` so new
  users can verify the known-good tag, expected version, quick demo, real-repo
  loop, and private-evidence guardrails from one page.
- Added a public demo script guide with a three-command shareable demo,
  copy-ready public wording, and privacy reminders for sharing AgentLedger
  without exposing raw evidence.

## 0.1.25-alpha - 2026-06-25

- Added a `Read first:` block to text-mode `agentledger status` so alpha
  testers can find the Markdown report, verdict, and private-evidence reminder
  before sharing notes.
- Added the requested collaboration/enquiries contact footer to the live
  `LICENSE` file and pinned it with a docs check.

## 0.1.24-alpha - 2026-06-23

- Carries forward the unpublished 0.1.23 alpha feedback readiness docs,
  including the checked support-packet Markdown feedback path and maintainer
  release-readiness checklist.
- Replaced public C-drive examples with D-drive project/temp examples and added
  a docs guard so README, docs, and issue templates do not suggest C-drive or
  OneDrive storage paths.

## 0.1.23-alpha - 2026-06-22

- Added a checked GitHub alpha feedback issue-template path for
  `agentledger support-packet --format markdown`, including sanitized Markdown
  snippets, install/version details, heading checks, redaction confirmation,
  and privacy-safe reproduction notes.
- Added an alpha feedback readiness checklist so maintainers can treat
  support-packet Markdown feedback as a next-alpha signal only after privacy
  and usefulness checks pass.

## 0.1.22-alpha - 2026-06-22

- Added a checked `agentledger support-packet --format markdown` example that
  shows sanitized, copy-ready output without exposing private output paths.
- Added a support-packet Markdown QA checklist so alpha testers can verify
  copy-ready headings, sanitized placeholders, and privacy-safe feedback
  snippets.

## 0.1.21-alpha - 2026-06-22

- Added `agentledger support-packet --format markdown` to print a sanitized,
  copy-ready alpha issue/comment body without writing files or copying raw
  evidence.

## 0.1.20-alpha - 2026-06-22

- Added `agentledger support-packet` to print a privacy-safe alpha support
  report checklist and JSON contract without writing files or copying evidence.

## 0.1.19-alpha - 2026-06-22

- Added alpha feedback capture guidance, issue template updates, and reviewed
  feedback handoff reminders for testers.
- Added `alpha-guide` troubleshooting guidance for install failures, command
  failures, packet-output confusion, and privacy-safe alpha reporting.

## 0.1.18-alpha - 2026-06-22

- Added `agentledger try` as a shorthand for the packet-enabled safe demo path.
- Clarified demo packet output so new users can distinguish review/share files
  from raw evidence that should stay local.
- Updated first-run docs so the current alpha install path can start from the
  new `agentledger try` shorthand.

## 0.1.17-alpha - 2026-06-22

- Added `agentledger demo --packet` so new users can see the share-safe alpha
  packet handoff from an isolated demo workspace before touching a real repo.
- Added `open-packet` coverage to smoke automation and the release dry run so
  CI proves the latest packet pointer can be read after `pack-alpha`.
- Aligned README release-readiness command examples with the current alpha
  release process.
- Ignored local `temp-agentledger-smoke*/` scratch folders.

## 0.1.16-alpha - 2026-06-20

- Added `agentledger open-packet` and a latest alpha packet pointer so testers
  can find the most recent `pack-alpha` handoff without scrolling terminal
  output.

## 0.1.15-alpha - 2026-06-20

- Made `agentledger pack-alpha` default to a fresh temporary packet directory,
  while keeping `--output-dir` for predictable alpha handoffs.

## 0.1.14-alpha - 2026-06-20

- Added `agentledger demo --summary-output` to write a path-free Markdown
  summary for public demo posts and review handoffs.
- Added `summary_output` and `summary_written` to the demo JSON contract.

## 0.1.13-alpha - 2026-06-19

- Added clearer `agentledger demo` first-read guidance for Markdown reports,
  status verdicts, and the next real-repository step.
- Added matching `alpha-guide` reading-order guidance for the first alpha pass.
- Simplified the README public quickstart so the GitHub install, demo, and
  read-only alpha-guide loop are easier to follow.

## 0.1.12-alpha - 2026-06-19

- Added GitHub install documentation for public alpha tags, `master`, editable
  checkouts, uninstall, and source-install verification.
- Added `scripts/install-source-check.ps1` for checking a GitHub/local source
  install in a temporary virtual environment.
- Updated first-run, demo, README, and `alpha-guide` onboarding to start from
  the public GitHub alpha install path.

## 0.1.11-alpha - 2026-06-19

- Added `agentledger demo --format json` for scripted first-run checks and
  machine-readable demo evidence paths.
- Added path-free `public_summary` snippets to alpha handoff packets for GitHub
  issues, short posts, and public alpha updates after review.
- Added `agentledger-alpha-issue.md` to `pack-alpha` as a copy-ready,
  share-safe GitHub issue/comment draft.
- Added install-verification commands to `alpha-guide` and clearer step markers
  to `scripts/install-check.ps1`.

## 0.1.10-alpha - 2026-06-18

- Added `agentledger demo` for a safe first run in an isolated temporary git
  repository.
- Added `docs/demo.md` and README onboarding for trying the demo before
  capturing evidence from a real repository.

## 0.1.9-alpha - 2026-06-16

- Added a local release dry-run script and private-alpha release checklist for
  verifying built-wheel install, smoke, and `pack-alpha` before tagging.
- Added `agentledger pack-alpha` to generate and validate share-safe alpha
  handoff packets.
- Added share-safe local path redaction for `agentledger alpha-handoff`.
- Added `agentledger alpha-handoff` for reviewed Markdown/JSON alpha packets
  without copying raw evidence.
- Added Markdown/file output for `agentledger review` handoffs.
- Added latest-vs-previous comparison details to `agentledger review`.
- Added recent-run context to `agentledger review`, including JSON history
  fields and a `--history-limit` control.
- Added `agentledger inspect-bundle` bundle triage output for manifest,
  signature, report, and review-status summaries.
- Added `agentledger signing-key` preflight checks for shared signing-key files
  without printing key material.
- Added machine-readable `agentledger sign-bundle --format json` output for
  signed bundle handoffs without exposing raw HMAC values.
- Added a release rehearsal receipt for summarizing verified rehearsal
  manifests, key artifacts, doctor status, and next release-prep commands.
- Added a rehearsal stage to the release artifact doctor for validating saved
  release rehearsal manifests and output folders.
- Added a release rehearsal manifest verifier for checking saved release dry-run
  folders without rerunning rehearsal.
- Added a release rehearsal manifest with file sizes, SHA-256 hashes, and
  handling notes for local release dry-run outputs.
- Expanded release rehearsals to write the target command index, metadata JSON,
  and fast readiness report into one local output directory.
- Added a fast release readiness report for metadata, release-process,
  release-notes, and git-hygiene preflight checks before full release readiness.
- Added the release-process consistency checker to the release-readiness gate
  and release evidence summaries.
- Added a release-process consistency checker that compares the generated
  release command index with `docs/release-process.md`.
- Added a release command index generator for the ordered release-day command
  flow, artifact filenames, placeholders, and handoff formats.
- Added a release artifact doctor for checking final-notes, post-release, and
  evidence-packet inputs before running release handoff commands.
- Added a post-release check wrapper that runs GitHub release validation and
  public-safe evidence packet generation under one output directory.
- Updated release rehearsal output to include the rendered release-check
  Markdown summary path used by final release notes and post-release packets.
- Added a public-safe release evidence packet generator that validates release
  artifacts and writes summary-only Markdown/JSON handoffs.
- Added a GitHub release artifact checker for post-release validation of tags,
  prerelease status, publish-ready release notes, and compact JSON/Markdown summaries.
- Added a guarded final-release-notes helper that builds publish-ready GitHub
  prerelease notes from clean release-check evidence and real CI run links.
- Added a release-check Markdown summary renderer and wired the manual Release
  Readiness workflow to append it to the GitHub Actions step summary.
- Added a cross-platform release metadata check for version, license, changelog,
  and README consistency, and wired it into release readiness.
- Reduced duplicate GitHub Actions runs by limiting branch push CI to `master`
  and release tags while keeping PR CI active.
- Added blocked-doctor alpha summaries with repair hints to `scripts/alpha.ps1`.
- Added doctor repair hints to blocked `agentledger alpha` summary next actions.
- Added actionable `hint` text to `agentledger doctor` setup checks.
- Hardened `scripts/alpha.ps1` summary write failures so invalid `-JsonOutput`
  paths report a clear error and exit 2 instead of stopping mid-output.
- Hardened `agentledger alpha` summary write failures so invalid summary paths
  return a normal alpha summary instead of a traceback.
- Hardened `agentledger alpha` config errors so they return a full alpha
  summary and write it when `--out` or `--json-output` is available.
- Hardened `agentledger alpha` so missing or non-git target repos return a
  normal alpha summary instead of traceback-style failures.
- Added `agentledger alpha` as a cross-platform core alpha pass that writes the
  same machine-readable alpha summary schema.
- Added `agentledger alpha-summary` to inspect and validate one-command alpha
  summary JSON.
- Added machine-readable JSON summary output to the one-command alpha pass.
- Added a README/config consistency check for the repository alpha policy.
- Fixed explicit `--out` commands so they still inherit the target repo's
  AgentLedger policy config.
- Added direct `agentledger status` validation to the one-command alpha pass.
- Added `agentledger status` to summarize the latest run policy status,
  evidence paths, feedback counts, and next actions in one command.
- Added `agentledger feedback-export` to write reviewed Markdown or JSON alpha
  feedback handoffs without local evidence paths.
- Added `agentledger feedback-summary` to review local alpha feedback across
  run folders with text and JSON output.
- Added `agentledger feedback` to record and list local alpha feedback notes
  attached to the latest or selected run folder.
- Scoped release-note publish readiness checks to validation placeholders so
  changelog highlights can mention TODO checks without blocking publication.

## 0.1.8-alpha - 2026-06-14

- Added a release rehearsal script that dry-runs release prep, drafts notes
  outside the repo, and writes a local checklist summary.
- Added a publish-ready release notes check to catch TODO validation placeholders
  before creating a GitHub prerelease.
- Added optional JSON summaries to release readiness checks for CI and agent
  handoffs.
- Added release process documentation consistency tests to keep version examples
  and release gates aligned with the release tooling.
- Added `docs/release-process.md` with the end-to-end alpha release checklist.
- Added the build backend to the `dev` extra so packaging metadata tests can
  build wheels without network build isolation.
- Made packaging metadata tests avoid network build-isolation setup while
  leaving isolated wheel validation in release readiness.
- Added optional release-notes draft output to `scripts/prepare_release.py` so
  release prep can generate the GitHub release body from the prepared changelog.
- Added release prep tooling to update package versions and move Unreleased
  changelog entries into a dated release section in one guarded step.
- Added a release-readiness guard that verifies the package version has a
  matching non-empty `CHANGELOG.md` release section before tagging.
- Added release notes tooling to draft GitHub prerelease notes from a
  `CHANGELOG.md` version section.
- Fixed the install-check build backend probe so release-readiness CI can
  install missing build tooling instead of stopping on an import traceback.
- Added a manual GitHub Actions release-readiness workflow for pre-tag
  validation with `scripts/release-check.ps1`.

## 0.1.7-alpha - 2026-06-14

- Added a PowerShell release-readiness check for version consistency, git
  hygiene, wheel metadata, tests, install verification, and smoke coverage.
- Added packaging metadata tests for wheel metadata, console entry point, pure
  Python wheel tags, and packaged module coverage.
- Added docs consistency tests for local Markdown links and code-spanned repo
  file references.
- Added `agentledger contracts` to list known JSON command contracts in text or
  JSON form.
- Added tests that exercise every documented JSON command contract and verify
  stable top-level and nested fields.

## 0.1.6-alpha - 2026-06-14

- Added `schema_version` fields to `history`, `inspect-report`, and `compare`
  JSON output.
- Added `docs/json-contracts.md` to document alpha JSON contracts, exit codes,
  and evidence-handling expectations.
- Added JSON output for `agentledger open-latest` and `agentledger
  verify-bundle` so CI and agent handoffs can consume report paths and bundle
  validation results without scraping text output.
- Added optional `agentledger sign-bundle` HMAC-SHA256 signatures over bundle
  manifests, plus signature verification flags for `verify-bundle`.
- Added `agentledger-bundle-manifest.json` inside zip bundles and made
  `verify-bundle` validate member byte sizes and SHA-256 checksums.
- Added `agentledger review` to summarize the latest or selected run with
  pass/warn/block policy status, report paths, and next-action hints.

## 0.1.5-alpha - 2026-06-14

- Added smoke coverage for `agentledger check --format json` in both Windows
  and Bash smoke scripts.
- Added a CI guide for consuming `agentledger check --format json` from Bash,
  PowerShell, GitHub Actions, or agent handoffs.
- Added CI-friendly `agentledger check --format json` summary fields, including
  rule counts and compact warning/blocking rule lists.
- Improved Markdown and HTML reports with review notes and evidence-file
  pointers for faster human triage.

## 0.1.4-alpha - 2026-06-14

- Added `agentledger init-config` to write a starter `.agentledger.toml` policy
  with overwrite protection.
- Added a committed `.agentledger.toml` public-alpha policy for dogfooding
  AgentLedger on itself, and added `agentledger check` to the alpha pass.
- Added `.agentledger.toml` policy settings for `agentledger check`, including
  required test evidence, dirty-state behavior, max changed files, and default
  warning handling.
- Added `agentledger check` to evaluate captured reports as pass/warn/block
  decisions with text and JSON output.

## 0.1.3-alpha

- Added `.agentledger.toml` policy config support for default privacy mode,
  output location, optional integration skips, and zip export behavior.

## 0.1.2-alpha

- Added `--privacy-mode summary` to omit command transcript content and full
  diffs from generated reports and bundles.

## 0.1.1-alpha

- Added best-effort redaction for obvious secrets in command output, report
  tails, tracked diffs, and optional integration artifact text.

## 0.1.0-alpha

- Added CLI evidence capture for repository snapshots and command runs.
- Added Markdown, JSON, and HTML reports.
- Added zip evidence bundle verification.
- Added latest-run, history, inspect, compare, and doctor commands.
- Added Windows and Ubuntu CI smoke coverage.
- Added public source-available licensing under PolyForm Noncommercial 1.0.0.
