$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ensure-git.ps1") -Quiet

function Invoke-AgentLedger {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    & python -m agentledger @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "agentledger $Arguments exited with code $LASTEXITCODE"
    }
}

function Invoke-AgentLedgerJsonCheck {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Run,
        [Parameter(Mandatory = $true)]
        [string] $OutputPath
    )

    $json = & python -m agentledger check --format json --allow-warnings $Run
    $exitCode = $LASTEXITCODE
    $json | Set-Content -LiteralPath $OutputPath -Encoding UTF8
    if ($exitCode -ne 0) {
        throw "agentledger check --format json exited with code $exitCode"
    }

    @'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8-sig"))
required = {
    "schema_version",
    "status",
    "ok",
    "summary",
    "rule_counts",
    "warning_rules",
    "blocking_rules",
    "rules",
}
missing = sorted(required - payload.keys())
if missing:
    raise SystemExit(f"Missing check JSON fields: {', '.join(missing)}")
if payload["schema_version"] != "agentledger.check.v1":
    raise SystemExit(f"Unexpected check schema: {payload['schema_version']}")
if payload["status"] not in {"pass", "warn"}:
    raise SystemExit(f"Unexpected smoke check status: {payload['status']}")
counts = payload["rule_counts"]
if counts["total"] != len(payload["rules"]):
    raise SystemExit("rule_counts.total does not match rules length")
if counts["warn"] != len(payload["warning_rules"]):
    raise SystemExit("rule_counts.warn does not match warning_rules length")
if counts["block"] != len(payload["blocking_rules"]):
    raise SystemExit("rule_counts.block does not match blocking_rules length")
print(f"AgentLedger check JSON: {payload['status']} - {payload['summary']}")
'@ | python - $OutputPath
    if ($LASTEXITCODE -ne 0) {
        throw "check JSON validation failed"
    }
}

$root = Join-Path $env:TEMP "agentledger-smoke-$([guid]::NewGuid())"
$originalLocation = Get-Location
$repo = Join-Path $root "repo"
$out = Join-Path $root "ledger"
$checkJson = Join-Path $root "agentledger-check.json"
$feedbackExportMarkdown = Join-Path $root "agentledger-feedback.md"
$feedbackExportJson = Join-Path $root "agentledger-feedback.json"
$signatureKey = Join-Path $root "agentledger-signing-key.txt"

try {
    New-Item -ItemType Directory -Path $repo | Out-Null
    Set-Location $repo

    git init | Out-Null
    git config user.email "agentledger-smoke@example.local" | Out-Null
    git config user.name "AgentLedger Smoke" | Out-Null
    Set-Content -Path "README.md" -Value "# Smoke Demo`r`n"
    git add README.md | Out-Null
    git commit -m "initial" | Out-Null
    Set-Content -LiteralPath $signatureKey -Value "agentledger-smoke-signing-key-0123456789" -Encoding UTF8

    Invoke-AgentLedger @("contracts")
    Invoke-AgentLedger @("contracts", "--format", "json")

    Invoke-AgentLedger @(
        "run",
        "--repo",
        $repo,
        "--out",
        $out,
        "--no-repomori",
        "--no-jester",
        "--no-tokometer",
        "--",
        "python",
        "-c",
        "from pathlib import Path; Path('note.txt').write_text('hello')"
    )

    Invoke-AgentLedger @("open-latest", "--out", $out)
    Invoke-AgentLedger @("open-latest", "--format", "json", "--out", $out)
    Invoke-AgentLedger @("history", "--out", $out)
    Invoke-AgentLedger @("status", "--out", $out, "--allow-warnings")
    Invoke-AgentLedger @("status", "--format", "json", "--out", $out, "--allow-warnings")
    Invoke-AgentLedger @("feedback", "--out", $out, "--note", "Smoke feedback note.", "--category", "friction", "--severity", "low")
    Invoke-AgentLedger @("feedback", "--out", $out, "--list")
    Invoke-AgentLedger @("feedback", "--format", "json", "--out", $out, "--list")
    Invoke-AgentLedger @("feedback-summary", "--out", $out)
    Invoke-AgentLedger @("feedback-summary", "--format", "json", "--out", $out)
    Invoke-AgentLedger @("feedback-export", "--out", $out, "--output", $feedbackExportMarkdown)
    Invoke-AgentLedger @("feedback-export", "--format", "json", "--out", $out, "--output", $feedbackExportJson, "--output-format", "json")

    $run = (Get-Content (Join-Path $out "latest.txt") -Raw).Trim()
    Invoke-AgentLedger @("inspect-report", "--format", "json", $run)
    Invoke-AgentLedger @("check", "--allow-warnings", $run)
    Invoke-AgentLedger @("review", "--out", $out, "--allow-warnings")
    Invoke-AgentLedger @("review", "--format", "json", "--out", $out, "--allow-warnings", "--history-limit", "1")
    Invoke-AgentLedgerJsonCheck -Run $run -OutputPath $checkJson
    Invoke-AgentLedger @("inspect-bundle", "${run}.zip")
    Invoke-AgentLedger @("inspect-bundle", "${run}.zip", "--format", "json")
    Invoke-AgentLedger @("verify-bundle", "${run}.zip")
    Invoke-AgentLedger @("verify-bundle", "${run}.zip", "--format", "json")
    Invoke-AgentLedger @("signing-key", "--repo", $repo, "--key-file", $signatureKey, "--format", "json")
    Invoke-AgentLedger @("sign-bundle", "${run}.zip", "--key-file", $signatureKey)
    Invoke-AgentLedger @("verify-bundle", "${run}.zip", "--signature-key-file", $signatureKey)
    Invoke-AgentLedger @("verify-bundle", "${run}.zip", "--format", "json", "--signature-key-file", $signatureKey)

    Invoke-AgentLedger @(
        "run",
        "--repo",
        $repo,
        "--out",
        $out,
        "--no-repomori",
        "--no-jester",
        "--no-tokometer",
        "--",
        "python",
        "-c",
        "from pathlib import Path; Path('note.txt').write_text('hello again'); Path('second.txt').write_text('there')"
    )

    $run2 = (Get-Content (Join-Path $out "latest.txt") -Raw).Trim()
    Invoke-AgentLedger @("compare", "--format", "json", $run, $run2)
}
finally {
    Set-Location -LiteralPath $originalLocation
    if (Test-Path -LiteralPath $root) {
        Remove-Item -Recurse -Force -LiteralPath $root
    }
}
