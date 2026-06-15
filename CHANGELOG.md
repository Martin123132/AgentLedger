# Changelog

## Unreleased

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
