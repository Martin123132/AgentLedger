$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$root = Join-Path $env:TEMP "agentledger-install-check-$([guid]::NewGuid())"
$venv = Join-Path $root ".venv"

try {
    New-Item -ItemType Directory -Path $root | Out-Null

    python -m venv --system-site-packages $venv
    $python = Join-Path $venv "Scripts\python.exe"
    $agentledger = Join-Path $venv "Scripts\agentledger.exe"

    & $python -m pip install --no-build-isolation --no-deps --no-index $repoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed with code $LASTEXITCODE"
    }

    & $agentledger --version
    if ($LASTEXITCODE -ne 0) {
        throw "agentledger --version failed with code $LASTEXITCODE"
    }

    & $python -m agentledger --version
    if ($LASTEXITCODE -ne 0) {
        throw "python -m agentledger --version failed with code $LASTEXITCODE"
    }

    & $agentledger --help | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "agentledger --help failed with code $LASTEXITCODE"
    }

    Write-Host "AgentLedger install check passed."
}
finally {
    if (Test-Path -LiteralPath $root) {
        Remove-Item -Recurse -Force -LiteralPath $root
    }
}
