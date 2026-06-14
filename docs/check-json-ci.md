# Consuming Check JSON in CI

`agentledger check --format json` is the machine-readable companion to the
human report. Use it when CI, a bot, or another agent needs a stable summary of
whether a captured run is safe to accept.

Prefer the command exit code for gating:

- `0`: pass
- `1`: warn
- `2`: block

Use the JSON fields for summaries, annotations, and follow-up routing:

- `ok`: `true` only when status is `pass`
- `summary`: one-line human summary
- `rule_counts`: pass/warn/block totals
- `warning_rules`: compact list of warning rule ids and messages
- `blocking_rules`: compact list of blocking rule ids and messages
- `rules`: full ordered rule list

Keep evidence local by default. Do not upload `.agentledger/` folders or zip
bundles from CI unless a reviewer explicitly needs them and the contents have
been checked.

## Bash Example

This example captures a pytest run, writes check JSON to the runner temp folder,
prints the concise summary, and preserves AgentLedger's exit code.

```bash
python -m agentledger run --repo . --out .agentledger --privacy-mode summary -- python -m pytest
run="$(cat .agentledger/latest.txt | tr -d '\r\n')"
json_path="$RUNNER_TEMP/agentledger-check.json"

set +e
python -m agentledger check --format json --repo . "$run" > "$json_path"
check_status=$?
set -e

python - "$json_path" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8-sig"))
print(f"AgentLedger check: {payload['status']} - {payload['summary']}")
for rule in payload["blocking_rules"]:
    print(f"BLOCK {rule['id']}: {rule['message']}")
for rule in payload["warning_rules"]:
    print(f"WARN {rule['id']}: {rule['message']}")
PY

exit "$check_status"
```

Add `--allow-warnings` when CI should fail only for block-level issues.

## PowerShell Example

```powershell
python -m agentledger run --repo . --out .agentledger --privacy-mode summary -- python -m pytest
$run = (Get-Content .agentledger\latest.txt -Raw).Trim()
$jsonPath = Join-Path $env:RUNNER_TEMP "agentledger-check.json"

python -m agentledger check --format json --repo . $run > $jsonPath
$checkStatus = $LASTEXITCODE

@'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8-sig"))
print(f"AgentLedger check: {payload['status']} - {payload['summary']}")
for rule in payload["blocking_rules"]:
    print(f"BLOCK {rule['id']}: {rule['message']}")
for rule in payload["warning_rules"]:
    print(f"WARN {rule['id']}: {rule['message']}")
'@ | python - $jsonPath

exit $checkStatus
```

## Agent Handoff Pattern

When another agent is continuing the work, include the compact check summary in
the handoff:

```text
AgentLedger status: warn
Summary: 2 warnings; review before accepting.
Blocking rules: none
Warning rules: test_evidence, repo_state
Latest report: .agentledger/<run-id>/agentledger-report.md
```

The receiving agent should inspect `blocking_rules` first, then
`warning_rules`, then the Markdown or HTML report. The full evidence bundle
should stay local unless sharing is intentional.
