# AgentLedger JSON Contracts

AgentLedger's JSON output is for CI, bots, and agent handoffs that need to read
status without scraping human text.

The text output is still the primary human interface. JSON consumers should use
command exit codes for gating and JSON fields for summaries, routing, and links
to evidence.

## Compatibility

AgentLedger is still alpha. Within a `*.v1` schema, consumers can expect:

- existing top-level field names to keep their meaning
- `schema_version` to change when a breaking payload change is made
- new fields to be added without a schema version bump
- paths to be strings using the local platform path format
- missing optional paths to be `null`

Consumers should ignore unknown fields and check `schema_version` before relying
on a payload shape.

## Exit Codes

- `0`: command succeeded
- `1`: warning status for review/check commands when warnings are not allowed
- `2`: invalid input, missing evidence, blocked policy, or verification failure

## Commands

### `agentledger doctor --json`

Schema: `agentledger.doctor.v1`

Use this before an alpha pass to check local setup.

Stable fields:

- `status`: `ready` or `blocked`
- `required_ok`: boolean
- `optional`: configured and missing optional integration summary
- `checks`: ordered setup checks with `name`, `ok`, `detail`, and `required`

### `agentledger open-latest --format json`

Schema: `agentledger.open_latest.v1`

Use this to locate the latest local evidence without parsing text output.

Stable fields:

- `ok`: boolean
- `repo`: resolved repository path used for config lookup
- `out`: resolved AgentLedger output directory, or `null` if config failed
- `latest_run`: resolved latest run directory, or `null`
- `paths`: `markdown`, `json`, `html`, and optional `zip`
- `missing_reports`: expected report files that are absent
- `errors`: human-readable error list

### `agentledger history --format json`

Schema: `agentledger.history.v1`

Use this to list recent runs from an output directory.

Stable fields:

- `out`: resolved AgentLedger output directory
- `runs`: newest-first run summaries

Each run summary includes `run_id`, `run_dir`, timestamps, `command`,
`exit_code`, `changed_files`, `test_framework`, `privacy_mode`, artifact counts,
and report paths.

### `agentledger inspect-report --format json <run-dir>`

Schema: `agentledger.inspect_report.v1`

Use this for a compact summary of one run report.

Stable fields:

- `run_dir`
- `command`
- `exit_code`
- `test_framework`
- `changed_files`
- `artifacts`: `ok` and `warn` counts
- `tokometer`: optional summary string
- `privacy_mode`

### `agentledger check --format json <run-dir>`

Schema: `agentledger.check.v1`

Use this as the main CI gate for a captured run.

Stable fields:

- `status`: `pass`, `warn`, or `block`
- `ok`: `true` only when status is `pass`
- `run_dir`
- `report`
- `summary`
- `rule_counts`: pass/warn/block totals
- `warning_rules`
- `blocking_rules`
- `rules`: ordered rule results with `id`, `status`, and `message`
- `policy`: effective check policy when the report loaded

### `agentledger review --format json`

Schema: `agentledger.review.v1`

Use this when an agent or reviewer needs policy status plus direct evidence
paths.

Stable fields:

- `status`
- `ok`
- `summary`
- `run_dir`
- `command_exit_code`
- `paths`: `markdown`, `json`, `html`, and optional `zip`
- `check`: embedded `agentledger.check.v1` payload
- `review_exit_code`

### `agentledger verify-bundle --format json <bundle.zip>`

Schema: `agentledger.verify_bundle.v1`

Use this to validate portable evidence bundles before sharing or archiving them.

Stable fields:

- `ok`: boolean
- `bundle`: resolved zip path
- `run_id`: report run id when verification succeeds
- `manifest`: bundle manifest member, schema, digest algorithm, file count, and run id
- `signature`: `required`, signature member, `status`, and `verified`
- `reports`: zip members for JSON, Markdown, and HTML reports
- `command`
- `changed_files`
- `artifacts`: `ok` and `warn` counts
- `errors`: human-readable error list

Signature status values are `not_present`, `present_unverified`, `verified`, or
`invalid`.

### `agentledger compare --format json <old-run> <new-run>`

Schema: `agentledger.compare.v1`

Use this to compare two captured runs.

Stable fields:

- `changed_files`: old/new counts, numeric delta, and display delta text
- `exit_code`: old/new exit codes and trend
- `artifacts`: old/new artifact counts
- `command`: old/new command text
- `tokometer`: old/new optional token summary
- `test_framework`: old/new detected framework
- `privacy_mode`: old/new privacy mode

## Evidence Handling

JSON output may contain local paths and command summaries. Do not commit or
upload `.agentledger/` folders, zip bundles, signing keys, or CI temp JSON files
unless a reviewer has checked the contents and explicitly needs them.
