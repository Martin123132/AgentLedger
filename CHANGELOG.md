# Changelog

## Unreleased

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
