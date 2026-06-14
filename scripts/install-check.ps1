$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$root = Join-Path $env:TEMP "agentledger-install-check-$([guid]::NewGuid())"
$venv = Join-Path $root ".venv"

try {
    New-Item -ItemType Directory -Path $root | Out-Null

    python -m venv --system-site-packages $venv
    $python = Join-Path $venv "Scripts\python.exe"
    $agentledger = Join-Path $venv "Scripts\agentledger.exe"

    $backendProbe = @(
        "import importlib",
        "import sys",
        "",
        "try:",
        "    importlib.import_module('setuptools.build_meta')",
        "except Exception:",
        "    sys.exit(1)",
        "sys.exit(0)"
    ) -join "`n"
    & $python -c $backendProbe 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $python -m pip install "setuptools>=68" wheel
        if ($LASTEXITCODE -ne 0) {
            throw "build tool install failed with code $LASTEXITCODE"
        }
    }

    & $python -m pip install --no-build-isolation --no-deps $repoRoot
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
