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

### `agentledger demo --format json`

Schema: `agentledger.demo.v1`

Use this for automated first-run smoke checks and onboarding wrappers that need
the demo evidence paths without scraping text output. Add `--packet` when the
wrapper should also produce a share-safe alpha packet and return the
`open-packet` handoff paths.

### `agentledger try --format json`

Schema: `agentledger.demo.v1`

Use this for the quickest public-alpha onboarding wrapper. It runs the same
isolated demo as `demo --packet`, returns packet handoff paths, and keeps raw
evidence local.

Both commands use the same stable fields:

- `ok`: boolean
- `status`: `pass` or `failed`
- `entrypoint`: `demo` or `try`
- `workspace`: isolated demo workspace, or `null` when setup failed early
- `repo`: demo git repository path, or `null`
- `out`: demo evidence output directory, or `null`
- `latest_run`: resolved latest run directory, or `null`
- `paths`: `markdown`, `json`, `html`, and optional `zip`
- `privacy_mode`: evidence detail level used for the demo capture
- `command`: captured verification command as an argument list
- `command_exit_code`: captured command exit code, or `null`
- `summary_output`: requested public-safe Markdown summary path, or `null`
- `summary_written`: boolean indicating whether `summary_output` was written
- `packet`: `null` unless `--packet` was requested; when present it includes
  `requested`, `ok`, `status`, `summary`, `output_dir`, `latest_packet`,
  `files`, `raw_evidence_copied`, `pack_exit_code`, `open_exit_code`, and
  `errors`
- `try_next`: follow-up CLI commands for inspecting demo evidence
- `cleanup`: command for removing the isolated workspace, or `null`
- `errors`: human-readable error list

### `agentledger doctor --json`

Schema: `agentledger.doctor.v1`

Use this before an alpha pass to check local setup.

Stable fields:

- `status`: `ready` or `blocked`
- `required_ok`: boolean
- `optional`: configured and missing optional integration summary
- `checks`: ordered setup checks with `name`, `ok`, `detail`, `required`, and
  `hint`

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

### `agentledger alpha-guide --format json`

Schema: `agentledger.alpha_guide.v1`

Use this to show the first-run alpha review loop without creating evidence.
The payload is suitable for agents that need to tell a tester what to run,
where evidence appears, and what must stay private.

Stable fields:

- `ok`: boolean
- `repo`: resolved repository path used for config lookup
- `out`: resolved AgentLedger output directory, or `null` on config failure
- `doctor`: compact `agentledger.doctor.v1` readiness snapshot with summary,
  optional integration counts, required blockers, and raw checks
- `fix_first`: concise ordered setup repair actions, empty when required checks
  are ready
- `commands`: setup, verify, run, inspect, and feedback command lists
- `evidence`: output root, latest pointer, run folder contents, and bundle note
- `troubleshooting`: install, command, packet, and reporting checks with next
  actions for alpha testers
- `send_back`: reviewed summary items a tester can report
- `keep_private`: evidence and secret handling reminders
- `known_limitations`: expected alpha limitations such as missing optional tools
- `errors`: human-readable error list

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

### `agentledger alpha-handoff --format json --output-dir <dir>`

Schema: `agentledger.alpha_handoff.v1`

Use this after a capture or alpha run to write a compact reviewed handoff
packet without copying raw `.agentledger` folders, transcript files, diff
files, zip evidence bundles, or signing keys.

Stable fields:

- `ok`: boolean, true when the packet was written and the latest status is
  acceptable for the selected strictness
- `status`: latest pass/warn/block status
- `summary`: latest review summary
- `generated_at`
- `agentledger_version`
- `repo`
- `out`
- `latest_run`
- `output_dir`
- `files`: written `markdown` and `json` packet paths
- `share_safe`: boolean, true when local absolute paths were redacted
- `redactions`: path-redaction status, marker labels, and sharing note
- `sharing`: review-required flag, packet files to review/share, and
  keep-private reminders for raw evidence. It also includes `feedback_fields`
  so wrappers can show testers what to include in an alpha issue without
  scraping text output.
- `review`: embedded `agentledger.review.v1` payload
- `status_payload`: embedded `agentledger.status.v1` payload
- `feedback_summary`: embedded `agentledger.feedback_summary.v1` payload
- `alpha_summary`: optional loaded `agentledger.alpha_summary.v1` payload plus
  availability and validation errors
- `public_summary`: path-free `text` and `markdown` snippets for GitHub issues,
  short posts, or public alpha updates after review
- `handling`: proof that no raw evidence files were copied, plus do-not-commit
  handling notes
- `next_actions`
- `errors`

Use `--strict` when warning status should make the command exit nonzero. Use
`--share-safe` or `--redact-local-paths` to replace local absolute paths with
stable markers such as `[repo]`, `[agentledger-output]`, `[latest-run]`, and
`[handoff-output]` in the written packet. Review the packet before sharing
because feedback notes and command summaries can still contain project context,
even though raw evidence is not copied.

`public_summary` is intentionally compact and omits local paths, raw evidence,
full reports, command transcripts, zip bundles, signing keys, and source
snippets. `public_summary.text` is capped at 280 characters for short-post
workflows; `public_summary.markdown` is a longer GitHub issue/comment starting
point. Both are still drafts for humans to review before posting.

### `agentledger pack-alpha --format json [--output-dir <dir>]`

Schema: `agentledger.pack_alpha.v1`

Use this to create the share-safe alpha handoff packet and validate the written
issue/comment draft plus Markdown/JSON before sharing. It wraps
`alpha-handoff --share-safe`, checks the generated packet files for local
absolute path leaks, and reports exactly which files should be reviewed/shared.
By default it writes to a fresh temporary packet directory; pass `--output-dir`
when you need a predictable local folder. It also writes
`.agentledger/latest-alpha-packet.json` so `open-packet` can find the packet
again.

Stable fields:

- `ok`: boolean, true when the share-safe handoff was written and validation
  passed
- `status`: latest pass/warn/block status from the handoff
- `summary`
- `generated_at`
- `agentledger_version`
- `repo`: local repository path used to generate the packet
- `out`: resolved AgentLedger output directory used for the latest packet pointer
- `output_dir`: local directory containing the packet files
- `latest_packet`: local pointer file written under the AgentLedger output directory
- `files`: generated `issue`, `markdown`, and `json` packet files to review/share
- `sharing`: explicit review/share file list, `feedback_fields`, and
  keep-private reminders
- `raw_evidence_copied`: always false
- `handoff_exit_code`: exit code from the wrapped alpha handoff command
- `handoff`: embedded `agentledger.alpha_handoff.v1` share-safe payload
- `public_summary`: the same path-free summary exposed by the embedded handoff
- `validation`: file existence and local absolute path leak checks
- `next_actions`
- `errors`
- `pointer_errors`: non-fatal errors encountered while writing the latest packet pointer

The `pack-alpha` command output is a local operator summary and may contain
local output paths so the operator can find the files.
`agentledger-alpha-issue.md` is a copy-ready GitHub issue/comment draft built
from `public_summary.markdown`; the generated handoff packet files remain the
deeper share-safe artifacts intended for review.

### `agentledger open-packet --format json`

Schema: `agentledger.open_packet.v1`

Use this to locate the latest share-safe alpha packet without parsing terminal
output from `pack-alpha`. The command reads
`.agentledger/latest-alpha-packet.json`, verifies the packet files still exist,
and prints the issue/comment draft plus Markdown/JSON packet paths.

Stable fields:

- `ok`: boolean, true when the pointer is readable and packet files exist
- `repo`: local repository path used for config lookup
- `out`: resolved AgentLedger output directory
- `latest_packet`: local pointer file read by the command
- `output_dir`: local directory containing the packet files
- `status`: latest pass/warn/block status from the packet
- `summary`
- `files`: generated `issue`, `markdown`, and `json` packet files to review/share
- `missing_files`: packet files named by the pointer that no longer exist
- `raw_evidence_copied`: always false for `pack-alpha` packets
- `packet`: embedded `agentledger.pack_alpha.v1` payload
- `errors`

### `agentledger support-packet --format json`

Schema: `agentledger.support_packet.v1`

Use this when a tester or wrapper needs to show exactly what to include in an
alpha support report without creating files or exposing raw local evidence.
The command prints environment/version facts, the report checklist, reviewed
files that may be shared after reading, commands to produce share-safe packets,
and the evidence that stays private by default.

Use `agentledger support-packet --format markdown` when a human needs the same
guidance as a sanitized, copy-ready issue/comment body. It is read-only and
does not copy raw `.agentledger` evidence.

Stable fields:

- `ok`: boolean
- `generated_at`
- `agentledger_version`
- `platform`
- `python_version`
- `shell`
- `out`: relative output label used in example commands, or
  `<agentledger-output>` when an absolute path was supplied
- `out_redacted`: whether the requested output label was replaced
- `local_paths_included`: always false
- `raw_evidence_copied`: always false
- `include`: report fields to include, such as command used, platform/version
  details, reviewed files, and redacted errors
- `review_files`: packet/export files to review before sharing
- `keep_private`: raw evidence, bundles, transcripts, temp workspaces, signing
  keys, private paths, source, credentials, tokens, and secrets to keep private
- `suggested_commands`: safe try, inspect, share-safe packet, copy-ready
  Markdown, and machine-readable checklist commands
- `issue_template`: copy/paste skeleton labels
- `privacy_note`: short sharing reminder
- `errors`: human-readable error list

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

### `agentledger review --format json [--output <path>]`

Schema: `agentledger.review.v1`

Use this when an agent or reviewer needs policy status plus direct evidence
paths, recent-run context, and latest-vs-previous comparison.

Stable fields:

- `status`
- `ok`
- `summary`
- `run_dir`
- `command_exit_code`
- `paths`: `markdown`, `json`, `html`, and optional `zip`
- `history`: recent run summaries from the selected output folder, including
  `out`, requested `limit`, `runs`, and non-blocking `errors`
- `comparison`: latest-vs-previous comparison with `available`, `current_run`,
  `previous_run`, embedded `agentledger.compare.v1` payload, and non-blocking
  `errors`
- `check`: embedded `agentledger.check.v1` payload
- `output`: resolved review output path when `--output` is used, otherwise
  `null`
- `review_exit_code`

Each history run includes the same summary fields as
`agentledger history --format json`, plus `current` to mark the reviewed run.
Pass `--history-limit 0` to return an empty history list.
When a previous run exists in the same output folder, `comparison.compare`
matches the `agentledger compare --format json` shape.
For human handoffs, use `agentledger review --format markdown --output <path>`
to write the same compact review as a Markdown file.

### `agentledger inspect-bundle --format json <bundle.zip>`

Schema: `agentledger.inspect_bundle.v1`

Use this to triage portable evidence bundles without a signing key before full
verification or sharing. The command parses report metadata, manifest status,
signature metadata, and a lightweight review status. It never prints raw HMAC
signature values.

Stable fields:

- `ok`: boolean; true only when the inspection review status is `pass`
- `bundle`: resolved zip path
- `readable`: whether the zip could be opened
- `manifest`: bundle manifest member, schema, digest algorithm, file count, run
  id, validity, and manifest errors
- `signature`: signature member, `status`, verification flag, schema,
  algorithm, signed manifest member, and signed manifest digest; the raw HMAC
  value is intentionally omitted
- `reports`: zip members for JSON, Markdown, and HTML reports, plus missing
  report notices
- `review`: `status`, `summary`, blockers, warnings, command, exit code,
  changed files, test framework, privacy mode, and artifact counts
- `errors`: blocking issue list
- `next_actions`: concrete follow-up steps

Signature status values are `not_present`, `present_unverified`, `invalid`, or
`multiple`. Use `verify-bundle --signature-key-file` to verify an HMAC
signature.

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

### `agentledger signing-key --format json --key-file <key>`

Schema: `agentledger.signing_key.v1`

Use this to check shared signing-key file safety before signing bundles. The
command reports file metadata and git hygiene status only; it does not print
the key or a digest of the key.

Stable fields:

- `ok`: boolean
- `key_file`: resolved key-file path
- `repo`: resolved target repository path
- `git_root`: resolved git root when available
- `exists`: whether the key path exists
- `file`: whether the key path is a regular file
- `size_bytes`: trimmed key length, or `null` when unavailable
- `empty`: whether the trimmed key is empty, or `null` when unavailable
- `inside_repo`: whether the key path is under the target git root
- `ignored_by_git`: whether git ignore rules cover the key, or `null` when not
  checked
- `tracked_by_git`: whether git already tracks the key, or `null` when not
  checked
- `warnings`: non-blocking hygiene warnings
- `errors`: blocking issues such as missing, empty, tracked, or unignored keys
- `next_actions`: concrete follow-up steps

### `agentledger sign-bundle --format json <bundle.zip> --key-file <key>`

Schema: `agentledger.sign_bundle.v1`

Use this to add or replace a shared-key HMAC-SHA256 signature on a portable
evidence bundle while returning machine-readable signing metadata.

Stable fields:

- `ok`: boolean
- `bundle`: input bundle path
- `signed_bundle`: output bundle path
- `signature`: signature member, schema, algorithm, signed manifest member, and
  signed manifest SHA-256 digest; the raw HMAC value is intentionally omitted
- `errors`: human-readable error list

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

### `scripts/release_command_index.py --format json`

Schema: `agentledger.release_command_index.v1`

Use this to generate the ordered release-day command flow with stable temp
artifact names, required placeholders, and evidence-handling reminders.

Stable fields:

- `version`
- `release_label`
- `tag`
- `release_date`
- `repository`
- `artifacts`: expected temp paths for release notes, release checks, post-release output, and evidence packets
- `placeholders`: values that must be replaced before publishing
- `do_not_commit`
- `sections`: ordered release sections with purpose, commands, and notes

### `scripts/check_release_process.py --format json`

Schema: `agentledger.release_process_check.v1`

Use this to verify `docs/release-process.md` matches the generated release
command index before a release branch or handoff moves forward.

Stable fields:

- `ok`: boolean
- `status`: `ready` or `failed`
- `version`
- `release_label`
- `release_date`
- `repository`
- `doc`
- `index_schema_version`
- `summary`: total, passed, and failed check counts
- `checks`: ordered schema, artifact, placeholder, handling, and command checks
- `errors`
- `next_actions`

### `scripts/release_readiness_report.py --format json`

Schema: `agentledger.release_readiness_report.v1`

Use this to run a fast local release preflight before the full release-check
script. It checks release metadata, release-process documentation alignment,
release notes source, `git diff --check`, tracked private artifact guardrails,
and dirty working tree status without building wheels or running pytest/smoke.

Stable fields:

- `ok`: boolean
- `status`: `ready`, `ready_with_warnings`, or `failed`
- `repo`
- `branch`
- `head`
- `repository`
- `package_version`
- `project_version`
- `release_label`
- `release_date`
- `require_clean_git`
- `working_tree_dirty`
- `release_metadata`: embedded `agentledger.release_metadata_check.v1` payload
- `release_process`: embedded `agentledger.release_process_check.v1` payload
- `summary`: total, passed, warnings, and failed check counts
- `checks`: ordered release and git preflight checks
- `errors`
- `warnings`
- `next_actions`

### `scripts/rehearse_release.py`

Schema: `agentledger.release_rehearsal.v1`

Use this to dry-run release prep, draft release notes outside the repo, collect
target command index and release preflight artifacts, run the release readiness
check, and write a local release-day checklist.

Stable fields:

- `ok`: boolean
- `status`
- `repo`
- `package_version`
- `release_version`
- `release_date`
- `output_dir`
- `draft_release_notes`
- `release_command_index_json`
- `release_command_index_markdown`
- `release_metadata_json`
- `release_readiness_json`
- `release_readiness_markdown`
- `release_check_json`
- `release_check_summary`
- `release_check_log`
- `summary_json`
- `summary_markdown`
- `manifest_json`
- `steps`: release rehearsal steps with `name`, `status`, and `detail`

### `release-rehearsal-manifest.json`

Schema: `agentledger.release_rehearsal_manifest.v1`

Written by `scripts/rehearse_release.py` into the selected rehearsal output
directory. Use this to audit the generated local rehearsal files without
opening each one by hand.

Stable fields:

- `ok`: boolean
- `status`
- `generated_at`
- `repo`
- `branch`
- `head`
- `package_version`
- `release_version`
- `release_date`
- `output_dir`
- `manifest_json`
- `artifact_count`
- `artifacts`: generated rehearsal files with `kind`, relative `file`, `bytes`,
  `sha256`, and `handling`
- `handling`: storage and do-not-commit guidance; the manifest records that it
  excludes itself from the hash list

### `scripts/verify_release_rehearsal.py --format json`

Schema: `agentledger.release_rehearsal_manifest_verify.v1`

Use this to verify a saved release rehearsal output directory from its
`release-rehearsal-manifest.json` file without rerunning the rehearsal. By
default it checks files next to the manifest, so a rehearsal folder can be moved
as a unit; pass `--output-dir` to verify a different artifact directory.

Stable fields:

- `ok`: boolean
- `status`: `ready` or `failed`
- `checked_at`
- `manifest_json`
- `output_dir`
- `manifest_schema_version`
- `package_version`
- `release_version`
- `release_date`
- `branch`
- `head`
- `artifact_count`
- `verified_artifacts`
- `errors`

### `scripts/release_rehearsal_receipt.py --format json`

Schema: `agentledger.release_rehearsal_receipt.v1`

Use this after verifying a release rehearsal manifest to produce a compact
human handoff with key generated artifacts, the embedded rehearsal verifier
result, the release artifact doctor result, and the exact next
`scripts/prepare_release.py` commands.

Stable fields:

- `ok`: boolean
- `status`: `ready` or `blocked`
- `created_at`
- `manifest_json`
- `output_dir`
- `package_version`
- `release_version`
- `release_date`
- `branch`
- `head`
- `artifact_count`
- `verified_artifacts`
- `key_artifacts`: important rehearsal artifacts with `kind`, `file`, `path`,
  `bytes`, and `sha256`
- `verification`: embedded `agentledger.release_rehearsal_manifest_verify.v1`
  payload
- `doctor`: embedded `agentledger.release_artifact_doctor.v1` payload when the
  manifest provides a package version
- `errors`
- `next_commands`: exact follow-up commands when the receipt is ready
- `next_actions`
- `handling`: do-not-commit and storage guidance from the manifest

### `scripts/release-check.ps1 -JsonOutput <path>`

Schema: `agentledger.release_check.v1`

Use this to run the local release readiness gate and write a machine-readable
handoff for CI, release notes finalization, and post-release evidence packets.

Stable fields:

- `ok`: boolean
- `status`
- `repo`
- `branch`
- `head`
- `agentledger_version`
- `package_version`
- `require_clean_git`
- `skip_editable_install`
- `working_tree_dirty`
- `wheel`
- `release_metadata`: embedded `agentledger.release_metadata_check.v1` payload
- `release_process`: embedded `agentledger.release_process_check.v1` payload
- `steps`: release readiness steps with status, seconds, and optional error
- `error`

### `scripts/release_artifact_doctor.py --format json`

Schema: `agentledger.release_artifact_doctor.v1`

Use this before release rehearsal handoff, final notes, post-release checks, or
lower-level evidence packet generation to confirm required release artifacts
exist, have the expected schema, match the requested version, and are safe to
use.

Stable fields:

- `ok`: boolean
- `status`: `ready` or `blocked`
- `version`
- `release_label`
- `stage`: `rehearsal`, `final-notes`, `post-release`, or `evidence-packet`
- `checks`: artifact and validation checks with name, status, detail, and optional path
- `next_actions`: deduplicated operator actions for blocked checks

### `scripts/check_github_release.py --format json`

Schema: `agentledger.github_release_check.v1`

Use this after publishing to validate the GitHub release tag, prerelease/draft
state, release URL, publish-ready body, and published timestamp.

Stable fields:

- `ok`: boolean
- `status`
- `repository`
- `version`
- `release_label`
- `tag`
- `release`: URL, draft/prerelease state, target commit, and timestamps
- `checks`: individual release checks with name, status, and detail
- `errors`

### `scripts/release_evidence_packet.py --json-output <path>`

Schema: `agentledger.release_evidence_packet.v1`

Use this to build a public-safe release handoff from validated release-check
JSON, rendered release-check Markdown, final release notes, and GitHub release
check JSON. It records validation status and artifact names only; it does not
bundle private `.agentledger/` evidence or release notes bodies.

Stable fields:

- `ok`: boolean
- `status`
- `version`
- `release_label`
- `tag`
- `repository`
- `release_url`
- `private_evidence_included`
- `release_check`: branch, head, clean-git status, step counts, metadata counts, and release-process counts
- `github_release_check`: check counts, draft/prerelease status, and publish timestamp
- `artifacts`: validated artifact names, not artifact bodies
- `handling`

### `scripts/post_release_check.py`

Schema: `agentledger.post_release_check.v1`

Use this after publishing when you want one command to run the GitHub release
check and build the public-safe evidence packet under one output directory.

Stable fields:

- `ok`: boolean
- `status`
- `version`
- `tag`
- `repository`
- `output_dir`
- `github_release_check_json`
- `github_release_check_markdown`
- `release_evidence_packet_json`
- `release_evidence_packet_markdown`
- `summary_json`
- `summary_markdown`
- `errors`

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
- `fix_first`: concise ordered actions to clear blockers before rerunning alpha
- `next_actions`: human-readable next action list
- `errors`: machine-readable alpha pass errors

## Evidence Handling

JSON output may contain local paths and command summaries. Do not commit or
upload `.agentledger/` folders, zip bundles, signing keys, or CI temp JSON files
unless a reviewer has checked the contents and explicitly needs them.
