$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$root = Join-Path $env:TEMP "agentledger-install-check-$([guid]::NewGuid())"
$venv = Join-Path $root ".venv"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

try {
    Write-Host "AgentLedger install check"
    Write-Host "- Source checkout: $repoRoot"
    Write-Host "- Temporary workspace: $root"

    Write-Host "== Create temporary virtual environment =="
    New-Item -ItemType Directory -Path $root | Out-Null

    python -m venv --system-site-packages $venv
    $python = Join-Path $venv "Scripts\python.exe"
    $agentledger = Join-Path $venv "Scripts\agentledger.exe"
    Write-Host "- Python: $python"

    Write-Host "== Check build backend =="
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
        Write-Host "- Installing setuptools and wheel into the temporary environment."
        & $python -m pip install "setuptools>=68" wheel
        if ($LASTEXITCODE -ne 0) {
            throw "build tool install failed with code $LASTEXITCODE"
        }
    }

    Write-Host "== Install AgentLedger from local checkout =="
    & $python -m pip install --no-build-isolation --no-deps $repoRoot
    if ($LASTEXITCODE -ne 0) {
        throw "pip install failed with code $LASTEXITCODE"
    }

    Write-Host "== Verify console script =="
    & $agentledger --version
    if ($LASTEXITCODE -ne 0) {
        throw "agentledger --version failed with code $LASTEXITCODE"
    }

    Write-Host "== Verify module entry point =="
    & $python -m agentledger --version
    if ($LASTEXITCODE -ne 0) {
        throw "python -m agentledger --version failed with code $LASTEXITCODE"
    }

    Write-Host "== Verify help command =="
    & $agentledger --help | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "agentledger --help failed with code $LASTEXITCODE"
    }

    Write-Host "AgentLedger install check passed."
    Write-Host "- Temporary workspace will be removed: $root"
}
finally {
    if (Test-Path -LiteralPath $root) {
        Remove-Item -Recurse -Force -LiteralPath $root
    }
}
