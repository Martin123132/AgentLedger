param(
    [switch] $Quiet
)

$ErrorActionPreference = "Stop"

function Find-AgentLedgerGit {
    $existing = Get-Command git -ErrorAction SilentlyContinue
    if ($existing) {
        return $existing.Source
    }

    $candidateDirs = @()

    if ($env:ProgramFiles) {
        $candidateDirs += Join-Path $env:ProgramFiles "Git\cmd"
    }

    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    if ($programFilesX86) {
        $candidateDirs += Join-Path $programFilesX86 "Git\cmd"
    }

    if ($env:LocalAppData) {
        $desktopRoot = Join-Path $env:LocalAppData "GitHubDesktop"
        if (Test-Path -LiteralPath $desktopRoot) {
            $desktopGitDirs = Get-ChildItem -LiteralPath $desktopRoot -Directory -Filter "app-*" -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName "resources\app\git\cmd" }
            $candidateDirs += $desktopGitDirs
        }
    }

    foreach ($dir in $candidateDirs) {
        if (-not $dir) {
            continue
        }

        $gitExe = Join-Path $dir "git.exe"
        if (Test-Path -LiteralPath $gitExe) {
            $env:Path = "$dir;$env:Path"
            return $gitExe
        }
    }

    throw "git was not found on PATH or in common Windows install locations. Install Git for Windows or GitHub Desktop, then retry."
}

$gitPath = Find-AgentLedgerGit
if (-not $Quiet) {
    Write-Host "Using git: $gitPath"
}
