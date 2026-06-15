$ErrorActionPreference = "Stop"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

. (Join-Path $PSScriptRoot "ensure-git.ps1") -Quiet

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$root = Join-Path $env:TEMP "agentledger-release-dry-run-$([guid]::NewGuid())"
$wheelhouse = Join-Path $root "wheelhouse"
$venv = Join-Path $root ".venv"
$repo = Join-Path $root "repo"
$out = Join-Path $root "ledger"
$packAlphaDir = Join-Path $root "agentledger-alpha-packet"
$originalLocation = Get-Location
$script:InstalledPython = $null

function Test-IsUnderPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Candidate,
        [Parameter(Mandatory = $true)]
        [string] $Root
    )

    $candidateFull = [System.IO.Path]::GetFullPath($Candidate)
    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([char[]] @("\", "/"))
    return (
        $candidateFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase) -or
        $candidateFull.StartsWith("$rootFull\", [System.StringComparison]::OrdinalIgnoreCase)
    )
}

function Remove-RepoBuildPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RelativePath
    )

    $target = Join-Path $repoRoot $RelativePath
    if (-not (Test-IsUnderPath -Candidate $target -Root $repoRoot)) {
        throw "Refusing to remove path outside repository: $target"
    }
    if (Test-Path -LiteralPath $target) {
        Remove-Item -Recurse -Force -LiteralPath $target
    }
}

function Clear-BuildOutput {
    Remove-RepoBuildPath "build"
    Remove-RepoBuildPath "dist"
    Remove-RepoBuildPath "agentledger.egg-info"
    Remove-RepoBuildPath "src\agentledger.egg-info"
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $File,
        [string[]] $Arguments = @()
    )

    & $File @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$File $Arguments failed with code $LASTEXITCODE"
    }
}

function Invoke-InstalledAgentLedger {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    $agentLedgerArguments = @("-m", "agentledger") + $Arguments
    Invoke-CheckedCommand -File $script:InstalledPython -Arguments $agentLedgerArguments
}

try {
    Set-Location -LiteralPath $repoRoot
    New-Item -ItemType Directory -Path $wheelhouse | Out-Null
    New-Item -ItemType Directory -Path $repo | Out-Null

    Write-Host "== Clean build output =="
    Clear-BuildOutput

    Write-Host ""
    Write-Host "== Build wheel =="
    Invoke-CheckedCommand "python" @("-m", "pip", "wheel", "--no-deps", "--wheel-dir", $wheelhouse, $repoRoot)
    $wheels = @(Get-ChildItem -LiteralPath $wheelhouse -Filter "agentledger-*.whl")
    if ($wheels.Count -ne 1) {
        throw "Expected exactly one AgentLedger wheel, found $($wheels.Count)"
    }
    $wheel = $wheels[0].FullName
    Write-Host "Wheel: $($wheels[0].Name)"

    Write-Host ""
    Write-Host "== Install built wheel =="
    Invoke-CheckedCommand "python" @("-m", "venv", $venv)
    $script:InstalledPython = Join-Path $venv "Scripts\python.exe"
    Invoke-CheckedCommand $script:InstalledPython @("-m", "pip", "install", "--no-deps", $wheel)
    Invoke-CheckedCommand $script:InstalledPython @("-m", "agentledger", "--version")
    Invoke-CheckedCommand $script:InstalledPython @("-m", "agentledger", "--help")

    Write-Host ""
    Write-Host "== Create temp git repo =="
    Set-Location -LiteralPath $repo
    Invoke-CheckedCommand "git" @("init")
    Invoke-CheckedCommand "git" @("config", "user.email", "agentledger-release-dry-run@example.local")
    Invoke-CheckedCommand "git" @("config", "user.name", "AgentLedger Release Dry Run")
    Set-Content -LiteralPath (Join-Path $repo "README.md") -Value "# Release Dry Run`r`n" -Encoding UTF8
    Invoke-CheckedCommand "git" @("add", "README.md")
    Invoke-CheckedCommand "git" @("commit", "-m", "initial")

    Write-Host ""
    Write-Host "== Installed-package smoke flow =="
    Invoke-InstalledAgentLedger @(
        "run",
        "--repo",
        $repo,
        "--out",
        $out,
        "--no-repomori",
        "--no-jester",
        "--no-tokometer",
        "--",
        $script:InstalledPython,
        "-c",
        "from pathlib import Path; Path('note.txt').write_text('installed dry run')"
    )
    Invoke-InstalledAgentLedger @("open-latest", "--out", $out)
    Invoke-InstalledAgentLedger @("open-latest", "--format", "json", "--out", $out)
    Invoke-InstalledAgentLedger @("history", "--out", $out)
    Invoke-InstalledAgentLedger @("status", "--out", $out, "--allow-warnings")
    Invoke-InstalledAgentLedger @("status", "--format", "json", "--out", $out, "--allow-warnings")

    $run = (Get-Content (Join-Path $out "latest.txt") -Raw).Trim()
    Invoke-InstalledAgentLedger @("inspect-report", "--format", "json", $run)
    Invoke-InstalledAgentLedger @("verify-bundle", "${run}.zip")
    Invoke-InstalledAgentLedger @("verify-bundle", "${run}.zip", "--format", "json")
    Invoke-InstalledAgentLedger @("pack-alpha", "--format", "json", "--out", $out, "--output-dir", $packAlphaDir)

    Invoke-InstalledAgentLedger @(
        "run",
        "--repo",
        $repo,
        "--out",
        $out,
        "--no-repomori",
        "--no-jester",
        "--no-tokometer",
        "--",
        $script:InstalledPython,
        "-c",
        "from pathlib import Path; Path('note.txt').write_text('installed dry run updated'); Path('second.txt').write_text('second capture')"
    )
    $run2 = (Get-Content (Join-Path $out "latest.txt") -Raw).Trim()
    Invoke-InstalledAgentLedger @("compare", "--format", "json", $run, $run2)

    Write-Host ""
    Write-Host "AgentLedger release dry run passed."
    Write-Host "Installed wheel: $([System.IO.Path]::GetFileName($wheel))"
    Write-Host "Temporary output was isolated under $root and will be removed before exit."
}
finally {
    Set-Location -LiteralPath $originalLocation
    try {
        Clear-BuildOutput
    }
    finally {
        if (Test-Path -LiteralPath $root) {
            Remove-Item -Recurse -Force -LiteralPath $root
        }
    }
}
