param(
    [Parameter(Mandatory = $true)]
    [string]$RunDate,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Virtual environment not found. Follow RUNBOOK_KR.md first: $Python"
}
if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot ".env"))) {
    throw ".env not found. Configure mock credentials before running."
}

$TraderArgs = @(
    (Join-Path $RepoRoot "main.py"),
    "--run-date", $RunDate,
    "--wait-for-open"
)
if ($Execute) {
    $TraderArgs += "--execute"
}

Push-Location $RepoRoot
try {
    & $Python @TraderArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
