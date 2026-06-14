param(
    [string] $Out = ".agentledger",
    [switch] $SkipEditableInstall
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ensure-git.ps1") -Quiet

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$originalLocation = Get-Location

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Label,
        [Parameter(Mandatory = $true)]
        [string] $File,
        [string[]] $Arguments = @()
    )

    Write-Host ""
    Write-Host "== $Label =="
    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with code $LASTEXITCODE"
    }
}

function Invoke-CapturedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Label,
        [Parameter(Mandatory = $true)]
        [string] $File,
        [string[]] $Arguments = @()
    )

    Write-Host ""
    Write-Host "== $Label =="
    $output = & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        $output | ForEach-Object { Write-Host $_ }
        throw "$Label failed with code $LASTEXITCODE"
    }
    $output | ForEach-Object { Write-Host $_ }
    return $output
}

try {
    Set-Location -LiteralPath $repoRoot

    if (-not $SkipEditableInstall) {
        Invoke-CheckedCommand "Install editable package" "python" @("-m", "pip", "install", "-e", ".[dev]")
    }

    $versionOutput = Invoke-CapturedCommand "Check AgentLedger version" "python" @("-m", "agentledger", "--version")
    $doctorOutput = Invoke-CapturedCommand "Check local readiness" "python" @("-m", "agentledger", "doctor", "--repo", ".")

    Invoke-CheckedCommand "Run install check" "powershell" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/install-check.ps1")
    Invoke-CheckedCommand "Run smoke check" "powershell" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/smoke.ps1")

    Invoke-CheckedCommand "Capture pytest run" "python" @(
        "-m",
        "agentledger",
        "run",
        "--repo",
        ".",
        "--out",
        $Out,
        "--no-repomori",
        "--no-jester",
        "--no-tokometer",
        "--",
        "python",
        "-m",
        "pytest"
    )

    Invoke-CheckedCommand "Show latest run paths" "python" @("-m", "agentledger", "open-latest", "--out", $Out)
    Invoke-CheckedCommand "Show run history" "python" @("-m", "agentledger", "history", "--out", $Out)

    $latestFile = Join-Path $Out "latest.txt"
    if (-not (Test-Path -LiteralPath $latestFile)) {
        throw "Latest run pointer not found: $latestFile"
    }

    $latestRun = (Get-Content -LiteralPath $latestFile -Raw).Trim()
    Invoke-CheckedCommand "Inspect latest report" "python" @("-m", "agentledger", "inspect-report", $latestRun)
    Invoke-CheckedCommand "Check latest report" "python" @("-m", "agentledger", "check", "--repo", ".", $latestRun)
    Invoke-CheckedCommand "Verify latest bundle" "python" @("-m", "agentledger", "verify-bundle", "$latestRun.zip")

    $pythonVersion = (& python --version) -join " "
    $gitVersion = (& git --version) -join " "
    $doctorSummary = ($doctorOutput | Select-Object -First 1)
    $versionSummary = ($versionOutput | Select-Object -First 1)

    Write-Host ""
    Write-Host "== Alpha complete =="
    Write-Host "Send back this summary:"
    Write-Host "- OS: $([System.Environment]::OSVersion.VersionString)"
    Write-Host "- Python: $pythonVersion"
    Write-Host "- Git: $gitVersion"
    Write-Host "- AgentLedger: $versionSummary"
    Write-Host "- Doctor: $doctorSummary"
    Write-Host "- Latest run: $latestRun"
    Write-Host "- Bundle verified: $latestRun.zip"
    Write-Host "- First confusing command, if any: <fill in>"
    Write-Host "- Report clarity: <clear / unclear + notes>"
    Write-Host "- Optional local feedback: python -m agentledger feedback --out $Out --note ""First confusing thing: ..."""
    Write-Host ""
    Write-Host "Do not send or commit .agentledger folders, zip bundles, secrets, or sensitive evidence unless explicitly requested."
    Write-Host "Use docs/alpha-feedback-template.md for fuller notes."
}
finally {
    Set-Location -LiteralPath $originalLocation
}
