param(
    [string] $Out = ".agentledger",
    [string] $JsonOutput,
    [switch] $SkipEditableInstall
)

$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "ensure-git.ps1") -Quiet

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$repoRootPath = $repoRoot.Path
$originalLocation = Get-Location
$startedAt = [DateTimeOffset]::UtcNow.ToString("o")
$script:alphaExitCode = 0
$script:skipAlphaRemainder = $false
$script:alphaSummaryWriteNextAction = "Choose a writable alpha summary path, then run scripts/alpha.ps1 again."

function Resolve-AlphaPath {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }
    return Join-Path $repoRootPath $Path
}

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

function Invoke-CapturedCommandResult {
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
    $exitCode = $LASTEXITCODE
    $output | ForEach-Object { Write-Host $_ }
    return [pscustomobject]@{
        ExitCode = $exitCode
        Output = @($output)
    }
}

function Add-AlphaSummaryWriteError {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary] $Payload,
        [Parameter(Mandatory = $true)]
        [string] $Message
    )

    $errors = @()
    if ($Payload.Contains("errors") -and $null -ne $Payload["errors"]) {
        $errors += @($Payload["errors"])
    }
    if ($errors -notcontains $Message) {
        $errors += $Message
    }

    $nextActions = @()
    if ($Payload.Contains("next_actions") -and $null -ne $Payload["next_actions"]) {
        $nextActions += @($Payload["next_actions"])
    }
    if ($nextActions -notcontains $script:alphaSummaryWriteNextAction) {
        $nextActions += $script:alphaSummaryWriteNextAction
    }

    $Payload["ok"] = $false
    $Payload["status_exit_code"] = 2
    $Payload["errors"] = @($errors)
    $Payload["next_actions"] = @($nextActions)
}

function Write-AlphaSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Path,
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary] $Payload
    )

    $summaryParent = Split-Path -Parent $Path
    if ($summaryParent) {
        New-Item -ItemType Directory -Force -Path $summaryParent | Out-Null
    }
    $Payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Get-ResolvedAlphaSummaryPath {
    $summaryPath = $JsonOutput
    if (-not $summaryPath) {
        $summaryPath = Join-Path $Out "alpha-summary.json"
    }
    return Resolve-AlphaPath -Path $summaryPath
}

function New-EmptyAlphaFeedback {
    return [ordered]@{
        total_entries = 0
        returned_entries = 0
        runs_with_feedback = 0
        latest_run_entries = 0
        categories = [ordered]@{}
        severities = [ordered]@{}
        errors = @()
    }
}

function Get-DoctorRepairActions {
    param(
        [Parameter(Mandatory = $true)]
        [object] $DoctorPayload
    )

    $actions = @()
    foreach ($check in @($DoctorPayload.checks)) {
        if ($check.ok -eq $true -or $check.required -ne $true) {
            continue
        }
        $name = if ($check.name) { [string] $check.name } else { "unknown" }
        $hint = if ($check.hint) { ([string] $check.hint).Trim() } else { "" }
        if ($hint -and $hint -ne "No action needed.") {
            $actions += "Fix ${name}: $hint"
        }
    }
    $actions += "After fixing required setup, run scripts/alpha.ps1 again."
    return @($actions)
}

function Get-DoctorSetupErrors {
    param(
        [Parameter(Mandatory = $true)]
        [object] $DoctorPayload
    )

    $errors = @()
    foreach ($check in @($DoctorPayload.checks)) {
        if ($check.ok -eq $true -or $check.required -ne $true) {
            continue
        }
        $name = if ($check.name) { [string] $check.name } else { "unknown" }
        $detail = if ($check.detail) { [string] $check.detail } else { "required check failed" }
        $errors += "Required doctor check failed: ${name} - $detail"
    }
    if ($errors.Count -eq 0) {
        $errors += "Doctor check did not report ready."
    }
    return @($errors)
}

function Write-AlphaBlockedSummary {
    param(
        [Parameter(Mandatory = $true)]
        [string] $SummaryPath,
        [Parameter(Mandatory = $true)]
        [object] $DoctorPayload,
        [Parameter(Mandatory = $true)]
        [string[]] $DoctorOutput,
        [Parameter(Mandatory = $true)]
        [string] $VersionSummary
    )

    $doctorSummary = ($DoctorOutput | Select-Object -First 1)
    if (-not $doctorSummary) {
        $doctorSummary = "AgentLedger doctor: blocked (required setup needs attention)"
    }
    $pythonVersion = (& python --version) -join " "
    $gitVersion = (& git --version) -join " "
    $alphaSummary = [ordered]@{
        schema_version = "agentledger.alpha_summary.v1"
        ok = $false
        summary_file = $SummaryPath
        started_at = $startedAt
        ended_at = [DateTimeOffset]::UtcNow.ToString("o")
        repo = $repoRootPath
        out = (Resolve-AlphaPath -Path $Out)
        latest_run = $null
        bundle = $null
        agentledger_version = $VersionSummary
        python_version = $pythonVersion
        git_version = $gitVersion
        doctor = $doctorSummary
        status = "block"
        status_summary = "Required setup is blocked; fix doctor errors before running alpha again."
        status_exit_code = 2
        report_paths = [ordered]@{}
        feedback = (New-EmptyAlphaFeedback)
        next_actions = @(Get-DoctorRepairActions -DoctorPayload $DoctorPayload)
        errors = @(Get-DoctorSetupErrors -DoctorPayload $DoctorPayload)
    }

    $summaryWriteError = $null
    try {
        Write-AlphaSummary -Path $SummaryPath -Payload $alphaSummary
    }
    catch {
        $summaryWriteError = "Unable to write alpha summary ${SummaryPath}: $($_.Exception.Message)"
        Add-AlphaSummaryWriteError -Payload $alphaSummary -Message $summaryWriteError
    }

    Write-Host ""
    Write-Host "== Alpha blocked =="
    Write-Host "Doctor: $doctorSummary"
    if ($summaryWriteError) {
        Write-Host "Alpha summary JSON: not written"
        Write-Host "Alpha summary write error: $summaryWriteError"
    }
    else {
        Write-Host "Alpha summary JSON: $SummaryPath"
    }
    Write-Host "Next:"
    foreach ($action in @($alphaSummary["next_actions"])) {
        Write-Host "- $action"
    }
    Write-Host ""
    Write-Host "Do not send or commit .agentledger folders, zip bundles, secrets, or sensitive evidence unless explicitly requested."
}

function Invoke-CapturedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Label,
        [Parameter(Mandatory = $true)]
        [string] $File,
        [string[]] $Arguments = @()
    )

    $result = Invoke-CapturedCommandResult -Label $Label -File $File -Arguments $Arguments
    if ($result.ExitCode -ne 0) {
        throw "$Label failed with code $($result.ExitCode)"
    }
    return $result.Output
}

try {
    Set-Location -LiteralPath $repoRootPath

    if (-not $SkipEditableInstall) {
        Invoke-CheckedCommand "Install editable package" "python" @("-m", "pip", "install", "-e", ".[dev]")
    }

    $versionOutput = Invoke-CapturedCommand "Check AgentLedger version" "python" @("-m", "agentledger", "--version")
    $versionSummary = ($versionOutput | Select-Object -First 1)
    $doctorResult = Invoke-CapturedCommandResult "Check local readiness" "python" @("-m", "agentledger", "doctor", "--repo", ".")
    $doctorOutput = @($doctorResult.Output)
    $doctorJsonOutput = & python -m agentledger doctor --repo . --json
    $doctorPayload = $null
    try {
        $doctorPayload = ($doctorJsonOutput -join "`n") | ConvertFrom-Json
    }
    catch {
        if ($doctorResult.ExitCode -ne 0) {
            throw "Unable to parse doctor JSON after blocked setup: $($_.Exception.Message)"
        }
    }
    if ($doctorResult.ExitCode -ne 0) {
        if ($null -eq $doctorPayload) {
            throw "Check local readiness failed with code $($doctorResult.ExitCode)"
        }
        $resolvedSummaryPath = Get-ResolvedAlphaSummaryPath
        Write-AlphaBlockedSummary `
            -SummaryPath $resolvedSummaryPath `
            -DoctorPayload $doctorPayload `
            -DoctorOutput $doctorOutput `
            -VersionSummary $versionSummary
        $script:alphaExitCode = 2
        $script:skipAlphaRemainder = $true
    }

    if (-not $script:skipAlphaRemainder) {
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
    $statusOutput = Invoke-CapturedCommand "Show latest status" "python" @("-m", "agentledger", "status", "--repo", ".", "--out", $Out, "--allow-warnings")
    $statusJsonOutput = Invoke-CapturedCommand "Check latest status JSON" "python" @("-m", "agentledger", "status", "--repo", ".", "--out", $Out, "--format", "json", "--allow-warnings")
    $statusPayload = ($statusJsonOutput -join "`n") | ConvertFrom-Json

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
    $statusSummary = ($statusOutput | Select-Object -First 1)
    $endedAt = [DateTimeOffset]::UtcNow.ToString("o")
    $resolvedSummaryPath = Get-ResolvedAlphaSummaryPath
    $alphaSummary = [ordered]@{
        schema_version = "agentledger.alpha_summary.v1"
        ok = $true
        summary_file = $resolvedSummaryPath
        started_at = $startedAt
        ended_at = $endedAt
        repo = $repoRootPath
        out = (Resolve-AlphaPath -Path $Out)
        latest_run = $latestRun
        bundle = "$latestRun.zip"
        agentledger_version = $versionSummary
        python_version = $pythonVersion
        git_version = $gitVersion
        doctor = $doctorSummary
        status = $statusPayload.status
        status_summary = $statusPayload.check.summary
        status_exit_code = $statusPayload.status_exit_code
        report_paths = $statusPayload.paths
        feedback = $statusPayload.feedback
        next_actions = $statusPayload.next_actions
        errors = @()
    }
    $summaryWriteError = $null
    try {
        Write-AlphaSummary -Path $resolvedSummaryPath -Payload $alphaSummary
    }
    catch {
        $summaryWriteError = "Unable to write alpha summary ${resolvedSummaryPath}: $($_.Exception.Message)"
        Add-AlphaSummaryWriteError -Payload $alphaSummary -Message $summaryWriteError
        $script:alphaExitCode = 2
    }

    Write-Host ""
    if ($summaryWriteError) {
        Write-Host "== Alpha complete with summary write error =="
    }
    else {
        Write-Host "== Alpha complete =="
    }
    Write-Host "Send back this summary:"
    Write-Host "- OS: $([System.Environment]::OSVersion.VersionString)"
    Write-Host "- Python: $pythonVersion"
    Write-Host "- Git: $gitVersion"
    Write-Host "- AgentLedger: $versionSummary"
    Write-Host "- Doctor: $doctorSummary"
    Write-Host "- Status: $statusSummary"
    Write-Host "- Latest run: $latestRun"
    Write-Host "- Bundle verified: $latestRun.zip"
    if ($summaryWriteError) {
        Write-Host "- Alpha summary JSON: not written"
        Write-Host "- Alpha summary write error: $summaryWriteError"
    }
    else {
        Write-Host "- Alpha summary JSON: $resolvedSummaryPath"
    }
    Write-Host "- First confusing command, if any: <fill in>"
    Write-Host "- Report clarity: <clear / unclear + notes>"
    Write-Host "- Optional local feedback: python -m agentledger feedback --out $Out --note ""First confusing thing: ..."""
    Write-Host "- Optional feedback summary: python -m agentledger feedback-summary --out $Out"
    Write-Host ""
    Write-Host "Do not send or commit .agentledger folders, zip bundles, secrets, or sensitive evidence unless explicitly requested."
    Write-Host "Use docs/alpha-feedback-template.md for fuller notes."
    }
}
finally {
    Set-Location -LiteralPath $originalLocation
}

if ($script:alphaExitCode -ne 0) {
    exit $script:alphaExitCode
}
