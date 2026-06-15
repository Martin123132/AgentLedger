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

Use `agentledger contracts` for a human summary of known JSON command surfaces,
or `agentledger contracts --format json` when another agent needs to discover
available contracts programmatically.

## Exit Codes

- `0`: command succeeded
- `1`: warning status for review/check commands when warnings are not allowed
- `2`: invalid input, missing evidence, blocked policy, or verification failure

## Commands

### `agentledger contracts --format json`

Schema: `agentledger.contracts.v1`

Use this to discover AgentLedger's known JSON command contracts.

Stable fields:

- `schema_version`
- `agentledger_version`
- `docs`
- `compatibility`: alpha compatibility expectations
- `contracts`: known command contracts, each with command text, schema version,
  purpose, stable fields, and exit code meanings

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

### `agentledger status --format json`

Schema: `agentledger.status.v1`

Use this to get the latest run policy status, evidence paths, local feedback
counts, and next actions in one payload.

Stable fields:

- `ok`: boolean, true only when the embedded check passes and no status errors
  were found
- `status`: latest run policy status, `pass`, `warn`, `block`, or `unknown`
- `repo`: resolved repository path used for config lookup
- `out`: resolved AgentLedger output directory, or `null` on config failure
- `latest_run`: resolved latest run directory, or `null`
- `paths`: `markdown`, `json`, `html`, and optional `zip`
- `missing_reports`: expected report files that are absent
- `check`: embedded `agentledger.check.v1` payload, or `null` when no latest
  run is available
- `feedback`: local feedback counts and category/severity totals
- `next_actions`: human-readable next action list
- `errors`: human-readable error list
- `status_exit_code`: exit code returned by the command for this payload

### `agentledger feedback --format json --note <text>`

Schema: `agentledger.feedback.v1`

Use this to attach local alpha feedback to the latest run, or to a selected run
directory. Feedback is written to `alpha-feedback.jsonl` in the run folder and
is not added to an already-created evidence zip bundle.

Stable fields:

- `ok`: boolean
- `action`: `record` or `list`
- `run_dir`: resolved run directory, or `null` on failure
- `feedback_file`: resolved feedback JSONL path, or `null` on failure
- `entry`: recorded feedback entry for record actions, otherwise `null`
- `entries`: feedback entries returned by the command
- `errors`: human-readable error list

Each feedback entry includes `schema_version`, `id`, `created_at`, `run_id`,
`run_dir`, `category`, `severity`, `source`, `note`, and `redacted`.

### `agentledger feedback-summary --format json`

Schema: `agentledger.feedback_summary.v1`

Use this to summarize local alpha feedback across run folders without opening
each run directory. The command reads `alpha-feedback.jsonl` files under the
configured AgentLedger output directory.

Stable fields:

- `ok`: boolean
- `out`: resolved AgentLedger output directory, or `null` on config failure
- `filters`: active `category`, `severity`, and `limit`
- `total_entries`: total matching feedback entries before the limit is applied
- `returned_entries`: number of entries included in this response
- `run_count`: number of run folders scanned
- `runs_with_feedback`: number of run folders with matching feedback
- `categories`: matching entry counts by category
- `severities`: matching entry counts by severity
- `runs`: run-level feedback file and count summaries
- `entries`: recent matching feedback entries
- `errors`: human-readable error list

### `agentledger feedback-export --format json --output <path>`

Schema: `agentledger.feedback_export_result.v1`

Use this to write a reviewed Markdown or JSON export for sharing feedback
without copying raw `.agentledger` evidence. The export file omits local run
directories and feedback file paths, while the command result reports where it
was written.

Stable fields:

- `ok`: boolean
- `out`: resolved AgentLedger output directory, or `null` on config failure
- `output`: resolved export file path, or `null` on failure
- `output_format`: export file format, `markdown` or `json`
- `export_schema_version`: schema used inside JSON export files
- `filters`: active `category`, `severity`, and `limit`
- `total_entries`: total matching feedback entries before the limit is applied
- `returned_entries`: number of entries included in the export
- `run_count`: number of run folders scanned
- `runs_with_feedback`: number of run folders with matching feedback
- `errors`: human-readable error list

JSON export files use `agentledger.feedback_export.v1` and include reviewed
feedback entries without raw local evidence paths.

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

## Script Summaries

### `agentledger alpha --format json [-- command]`

Schema: `agentledger.alpha_summary.v1`

Use this to run the core alpha pass, capture a verification command, validate
the latest report and bundle, and write a machine-readable handoff summary.
When no command is supplied after `--`, AgentLedger captures the current Python
interpreter running `-m pytest`.

Stable fields are the same as `agentledger alpha-summary --format json`.

### `agentledger alpha-summary --format json [summary-file]`

Schema: `agentledger.alpha_summary.v1`

Use this to inspect the one-command alpha pass result without scraping terminal
output. `agentledger alpha` and `scripts/alpha.ps1` write the same schema to
`.agentledger/alpha-summary.json` by default, or to a requested JSON handoff
path.

Stable fields:

- `ok`: boolean
- `summary_file`: resolved summary JSON path
- `started_at`
- `ended_at`
- `repo`: resolved AgentLedger checkout path
- `out`: resolved AgentLedger output directory used by the alpha pass
- `latest_run`: resolved latest captured run directory
- `bundle`: latest captured run zip bundle path
- `agentledger_version`
- `python_version`
- `git_version`
- `doctor`: first-line doctor readiness summary
- `status`: latest run policy status
- `status_summary`: embedded status/check summary
- `status_exit_code`
- `report_paths`: `markdown`, `json`, `html`, and optional `zip`
- `feedback`: latest feedback counts
- `next_actions`: human-readable next action list
- `errors`: machine-readable alpha pass errors

## Evidence Handling

JSON output may contain local paths and command summaries. Do not commit or
upload `.agentledger/` folders, zip bundles, signing keys, or CI temp JSON files
unless a reviewer has checked the contents and explicitly needs them.
