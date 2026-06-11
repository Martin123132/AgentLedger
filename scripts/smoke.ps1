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

$root = Join-Path $env:TEMP "agentledger-smoke-$([guid]::NewGuid())"
$originalLocation = Get-Location
$repo = Join-Path $root "repo"
$out = Join-Path $root "ledger"

try {
    New-Item -ItemType Directory -Path $repo | Out-Null
    Set-Location $repo

    git init | Out-Null
    git config user.email "agentledger-smoke@example.local" | Out-Null
    git config user.name "AgentLedger Smoke" | Out-Null
    Set-Content -Path "README.md" -Value "# Smoke Demo`r`n"
    git add README.md | Out-Null
    git commit -m "initial" | Out-Null

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
    Invoke-AgentLedger @("history", "--out", $out)

    $run = (Get-Content (Join-Path $out "latest.txt") -Raw).Trim()
    Invoke-AgentLedger @("inspect-report", "--format", "json", $run)
    Invoke-AgentLedger @("verify-bundle", "${run}.zip")

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
