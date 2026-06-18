param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^\d{8}$")]
    [string]$DateKst
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$RecordRelative = "records\trading_$DateKst.jsonl"
$Record = Join-Path $RepoRoot $RecordRelative

if (-not (Test-Path -LiteralPath $Record)) {
    throw "Trading record not found: $Record"
}
if (Select-String -LiteralPath $Record -Pattern 'authorization|appsecret|appkey|access_token|account_number') {
    throw "Sensitive-looking text found. Review the record manually before publishing."
}

Push-Location $RepoRoot
try {
    git add -- $RecordRelative
    git commit -m "Add KIS mock trading record for $DateKst"
    git push
}
finally {
    Pop-Location
}
