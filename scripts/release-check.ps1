param(
    [switch] $SkipEditableInstall,
    [switch] $RequireCleanGit
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ensure-git.ps1") -Quiet

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$root = Join-Path $env:TEMP "agentledger-release-check-$([guid]::NewGuid())"
$wheelhouse = Join-Path $root "wheelhouse"
$originalLocation = Get-Location
$results = New-Object System.Collections.Generic.List[object]
$workingTreeDirty = $false

function Invoke-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Label,
        [Parameter(Mandatory = $true)]
        [scriptblock] $Script
    )

    Write-Host ""
    Write-Host "== $Label =="
    $timer = [System.Diagnostics.Stopwatch]::StartNew()
    & $Script
    $timer.Stop()
    $results.Add([pscustomobject]@{
        Step = $Label
        Seconds = [math]::Round($timer.Elapsed.TotalSeconds, 1)
    }) | Out-Null
    Write-Host "OK: $Label ($([math]::Round($timer.Elapsed.TotalSeconds, 1))s)"
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

function Get-ProjectVersion {
    $text = Get-Content -LiteralPath (Join-Path $repoRoot "pyproject.toml") -Raw
    $inProject = $false
    foreach ($line in ($text -split "`r?`n")) {
        if ($line -match '^\[project\]\s*$') {
            $inProject = $true
            continue
        }
        if ($inProject -and $line -match '^\[') {
            break
        }
        if ($inProject -and $line -match '^version\s*=\s*"([^"]+)"') {
            return $Matches[1]
        }
    }
    throw "Could not find [project] version in pyproject.toml"
}

function Get-PackageVersion {
    $text = Get-Content -LiteralPath (Join-Path $repoRoot "src/agentledger/__init__.py") -Raw
    if ($text -match '__version__\s*=\s*"([^"]+)"') {
        return $Matches[1]
    }
    throw "Could not find agentledger.__version__"
}

function Test-WheelMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Wheel,
        [Parameter(Mandatory = $true)]
        [string] $ExpectedVersion
    )

    @'
import configparser
from email.parser import Parser
import sys
from zipfile import ZipFile

wheel_path = sys.argv[1]
expected_version = sys.argv[2]

with ZipFile(wheel_path) as archive:
    members = {
        name: archive.read(name)
        for name in archive.namelist()
        if not name.endswith("/")
    }

def member(filename):
    matches = [name for name in members if name.endswith(f".dist-info/{filename}")]
    if len(matches) != 1:
        raise SystemExit(f"Expected one {filename}, found {len(matches)}")
    return matches[0]

metadata = Parser().parsestr(members[member("METADATA")].decode("utf-8"))
if metadata["Name"] != "agentledger":
    raise SystemExit(f"Unexpected wheel name: {metadata['Name']}")
if metadata["Version"] != expected_version:
    raise SystemExit(f"Wheel version {metadata['Version']} != {expected_version}")
if metadata["Requires-Python"] != ">=3.10":
    raise SystemExit(f"Unexpected Requires-Python: {metadata['Requires-Python']}")
if metadata["Summary"] != "Local-first black box recorder for AI coding agents.":
    raise SystemExit(f"Unexpected summary: {metadata['Summary']}")

entry_points = configparser.ConfigParser()
entry_points.read_string(members[member("entry_points.txt")].decode("utf-8"))
script_target = entry_points["console_scripts"].get("agentledger")
if script_target != "agentledger.cli:main":
    raise SystemExit(f"Unexpected console entry point: {script_target}")

wheel_text = members[member("WHEEL")].decode("utf-8")
if "Root-Is-Purelib: true" not in wheel_text:
    raise SystemExit("Wheel is not marked pure Python")
if "Tag: py3-none-any" not in wheel_text:
    raise SystemExit("Wheel is not tagged py3-none-any")
member("RECORD")

print(f"Wheel metadata OK: agentledger {expected_version}")
'@ | python - $Wheel $ExpectedVersion
    if ($LASTEXITCODE -ne 0) {
        throw "Wheel metadata validation failed"
    }
}

try {
    Set-Location -LiteralPath $repoRoot
    New-Item -ItemType Directory -Path $wheelhouse | Out-Null

    $projectVersion = Get-ProjectVersion
    $packageVersion = Get-PackageVersion
    $branch = (& git branch --show-current) -join ""
    $head = (& git rev-parse --short HEAD) -join ""

    if (-not $SkipEditableInstall) {
        Invoke-Step "Install editable package" {
            Invoke-CheckedCommand "python" @("-m", "pip", "install", "-e", ".[dev]")
        }
    }

    Invoke-Step "Check release versions" {
        if ($projectVersion -ne $packageVersion) {
            throw "pyproject.toml version $projectVersion does not match agentledger.__version__ $packageVersion"
        }

        $versionOutput = (& python -m agentledger --version) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            throw "python -m agentledger --version failed with code $LASTEXITCODE"
        }
        if ($versionOutput -notmatch [regex]::Escape($projectVersion)) {
            throw "CLI version output does not include $projectVersion"
        }

        Write-Host "Version: $projectVersion"
    }

    Invoke-Step "Check git hygiene" {
        Invoke-CheckedCommand "git" @("diff", "--check")

        $trackedGenerated = & git ls-files ".agentledger" "*.zip" ".agentledger-signing-key*" "agentledger-signing-key*"
        if ($LASTEXITCODE -ne 0) {
            throw "git ls-files failed with code $LASTEXITCODE"
        }
        if ($trackedGenerated) {
            $trackedGenerated | ForEach-Object { Write-Host $_ }
            throw "Generated evidence or signing-key files are tracked"
        }

        $status = & git status --short --untracked-files=all
        if ($LASTEXITCODE -ne 0) {
            throw "git status failed with code $LASTEXITCODE"
        }
        if ($RequireCleanGit -and $status) {
            $status | ForEach-Object { Write-Host $_ }
            throw "Working tree is not clean"
        }
        $script:workingTreeDirty = [bool] $status
        if ($status) {
            Write-Host "Working tree has changes; rerun with -RequireCleanGit before tagging."
        }
        else {
            Write-Host "Working tree clean."
        }
    }

    Invoke-Step "Build wheel" {
        Invoke-CheckedCommand "python" @("-m", "pip", "wheel", "--no-deps", "--wheel-dir", $wheelhouse, $repoRoot)
        $wheels = Get-ChildItem -LiteralPath $wheelhouse -Filter "agentledger-*.whl"
        if ($wheels.Count -ne 1) {
            throw "Expected exactly one AgentLedger wheel, found $($wheels.Count)"
        }
        $script:wheelPath = $wheels[0].FullName
        Write-Host "Wheel: $($wheels[0].Name)"
    }

    Invoke-Step "Validate wheel metadata" {
        Test-WheelMetadata -Wheel $script:wheelPath -ExpectedVersion $projectVersion
    }

    Invoke-Step "Run pytest" {
        Invoke-CheckedCommand "python" @("-m", "pytest")
    }

    Invoke-Step "Run install check" {
        Invoke-CheckedCommand "powershell" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/install-check.ps1")
    }

    Invoke-Step "Run smoke check" {
        Invoke-CheckedCommand "powershell" @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/smoke.ps1")
    }

    Write-Host ""
    Write-Host "== Release readiness summary =="
    Write-Host "Branch: $branch"
    Write-Host "HEAD: $head"
    Write-Host "Version: $projectVersion"
    Write-Host "Wheel: $([System.IO.Path]::GetFileName($script:wheelPath))"
    foreach ($result in $results) {
        Write-Host "- $($result.Step): passed in $($result.Seconds)s"
    }
    if ($script:workingTreeDirty -and -not $RequireCleanGit) {
        Write-Host "Result: checks passed; clean checkout still required before tagging."
        Write-Host "Before tagging, rerun with -RequireCleanGit from a clean checkout."
    }
    else {
        Write-Host "Result: ready for alpha release review."
    }
}
finally {
    Set-Location -LiteralPath $originalLocation
    if (Test-Path -LiteralPath $root) {
        Remove-Item -Recurse -Force -LiteralPath $root
    }
}
