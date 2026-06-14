# Changelog

## Unreleased

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
