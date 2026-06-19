$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$EnvPath = Join-Path $RepoRoot ".env"
$RuntimeDir = Join-Path $RepoRoot ".runtime"
$ReadyFlag = Join-Path $RuntimeDir "secrets_ready.flag"

function Read-SecretText {
    param([Parameter(Mandatory = $true)][string]$Prompt)

    $secure = Read-Host -Prompt $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

function Assert-SingleLineValue {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        throw "$Name cannot be empty."
    }
    if ($Value -match "[\r\n]") {
        throw "$Name must be a single-line value."
    }
}

try {
    Write-Host "KIS mock-trading credentials" -ForegroundColor Cyan
    Write-Host "Nothing you type will be displayed or uploaded."
    Write-Host "Use the 10-digit mock account, including the 2-digit product code."
    Write-Host ""

    $account = Read-SecretText "Mock account (example: 12345678-01)"
    $appKey = Read-SecretText "App Key"
    $appSecret = Read-SecretText "App Secret"

    Assert-SingleLineValue -Name "Account" -Value $account
    Assert-SingleLineValue -Name "App Key" -Value $appKey
    Assert-SingleLineValue -Name "App Secret" -Value $appSecret

    $accountDigits = $account -replace "\D", ""
    if ($accountDigits.Length -ne 10) {
        throw "The mock account must contain exactly 10 digits."
    }

    $lines = @(
        "GH_ACCOUNT=$($accountDigits.Substring(0, 8))-$($accountDigits.Substring(8, 2))"
        "GH_APPKEY=$appKey"
        "GH_APPSECRET=$appSecret"
        "POLL_INTERVAL_SECONDS=180"
        "MONITOR_INTERVAL_SECONDS=180"
        "VERIFICATION_DELAY_SECONDS=30"
        "PRICE_OFFSET_KRW=1000"
        "PRICE_TICK_KRW=100"
        "ORDER_QUANTITY=3"
        "MAX_ORDER_PAIRS_PER_DAY=0"
        "REQUEST_MIN_INTERVAL_SECONDS=0.6"
    )

    [IO.File]::WriteAllLines($EnvPath, $lines, [Text.UTF8Encoding]::new($false))
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
    [IO.File]::WriteAllText($ReadyFlag, [DateTimeOffset]::Now.ToString("O"), [Text.UTF8Encoding]::new($false))

    $account = $null
    $appKey = $null
    $appSecret = $null
    $lines = $null

    Write-Host ""
    Write-Host "Saved locally. You may close this window." -ForegroundColor Green
    Start-Sleep -Seconds 2
}
catch {
    Write-Host ""
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Close this window and ask Codex to try again."
    Read-Host "Press Enter to close"
    exit 1
}
