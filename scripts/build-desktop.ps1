param(
    [string] $Python = "python",
    [string] $OutputDir,
    [switch] $SkipInstaller
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
if (-not $OutputDir) {
    $OutputDir = Join-Path $repoRoot "dist\desktop"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
$workRoot = Join-Path $env:TEMP "agentledger-desktop-build-$([guid]::NewGuid())"
$env:PYINSTALLER_CONFIG_DIR = Join-Path $env:TEMP "pyinstaller"
$entry = Join-Path $PSScriptRoot "desktop_entry.py"
$icon = Join-Path $workRoot "agentledger.ico"
$iss = Join-Path $repoRoot "packaging\windows\AgentLedger.iss"
$versionMatch = [regex]::Match((Get-Content (Join-Path $repoRoot "pyproject.toml") -Raw), '(?m)^version = "([^"]+)"\r?$')
if (-not $versionMatch.Success) {
    throw "Unable to read project version."
}
$version = $versionMatch.Groups[1].Value
$alphaMatch = [regex]::Match($version, '^(\d+\.\d+\.\d+)a\d+$')
$releaseVersion = if ($alphaMatch.Success) { "$($alphaMatch.Groups[1].Value)-alpha" } else { $version }

try {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    New-Item -ItemType Directory -Path $workRoot -Force | Out-Null

    & $Python (Join-Path $repoRoot "scripts\write_desktop_icon.py") --output $icon
    if ($LASTEXITCODE -ne 0) {
        throw "Desktop icon generation failed with code $LASTEXITCODE"
    }

    & $Python -m PyInstaller --version | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is unavailable. Install the desktop extra with: python -m pip install -e `".[desktop]`""
    }

    & $Python -m PyInstaller `
        --noconfirm `
        --clean `
        --onefile `
        --windowed `
        --name AgentLedger `
        --icon $icon `
        --add-data "$icon;." `
        --paths (Join-Path $repoRoot "src") `
        --distpath $OutputDir `
        --workpath (Join-Path $workRoot "work") `
        --specpath (Join-Path $workRoot "spec") `
        $entry
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed with code $LASTEXITCODE"
    }

    $exe = Join-Path $OutputDir "AgentLedger.exe"
    & $exe --smoke-test
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged desktop smoke test failed with code $LASTEXITCODE"
    }

    $portableRoot = Join-Path $workRoot "portable"
    New-Item -ItemType Directory -Path $portableRoot | Out-Null
    Copy-Item -LiteralPath $exe -Destination (Join-Path $portableRoot "AgentLedger.exe")
    Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination $portableRoot
    Copy-Item -LiteralPath (Join-Path $repoRoot "COMMERCIAL.md") -Destination $portableRoot
    $portable = Join-Path $OutputDir "AgentLedger-$releaseVersion-windows-x64-portable.zip"
    Compress-Archive -Path (Join-Path $portableRoot "*") -DestinationPath $portable -Force

    $installer = $null
    if (-not $SkipInstaller) {
        $iscc = @(
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
        ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
        if (-not $iscc) {
            throw "Inno Setup 6 was not found. Install it or pass -SkipInstaller for a portable-only build."
        }
        & $iscc "/DAppVersion=$releaseVersion" "/DSourceExe=$exe" "/DOutputDir=$OutputDir" "/DRepoRoot=$repoRoot" $iss
        if ($LASTEXITCODE -ne 0) {
            throw "Inno Setup build failed with code $LASTEXITCODE"
        }
        $installer = Join-Path $OutputDir "AgentLedger-$releaseVersion-windows-x64-setup.exe"
    }

    $commit = (& git -C $repoRoot rev-parse HEAD 2>$null)
    $manifestArgs = @(
        (Join-Path $repoRoot "scripts\write_desktop_manifest.py"),
        "--version", $version,
        "--executable", $exe,
        "--portable", $portable,
        "--source-commit", $commit,
        "--output", (Join-Path $OutputDir "agentledger-desktop-manifest.json")
    )
    if ($installer) {
        $manifestArgs += @("--installer", $installer)
    }
    & $Python @manifestArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Desktop manifest generation failed with code $LASTEXITCODE"
    }

    Copy-Item -LiteralPath (Join-Path $repoRoot "LICENSE") -Destination $OutputDir -Force
    Copy-Item -LiteralPath (Join-Path $repoRoot "COMMERCIAL.md") -Destination $OutputDir -Force
    Write-Host "AgentLedger desktop build ready: $OutputDir"
}
finally {
    $resolvedTemp = [System.IO.Path]::GetFullPath($env:TEMP) + [System.IO.Path]::DirectorySeparatorChar
    $resolvedWork = [System.IO.Path]::GetFullPath($workRoot)
    if ($resolvedWork.StartsWith($resolvedTemp, [System.StringComparison]::OrdinalIgnoreCase)) {
        Remove-Item -LiteralPath $resolvedWork -Recurse -Force -ErrorAction SilentlyContinue
    }
}
