param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^\d{4}-\d{2}-\d{2}$")]
    [string]$RunDate,
    [switch]$Execute
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Runner = Join-Path $PSScriptRoot "run_trader.ps1"
$KoreaTimeZone = [TimeZoneInfo]::FindSystemTimeZoneById("Korea Standard Time")
$KstStart = [DateTime]::ParseExact(
    "$RunDate 09:05:00",
    "yyyy-MM-dd HH:mm:ss",
    [Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::Unspecified
)
$UtcStart = [TimeZoneInfo]::ConvertTimeToUtc($KstStart, $KoreaTimeZone)
$LocalStart = $UtcStart.ToLocalTime()

if ($LocalStart -le [DateTime]::Now) {
    throw "The calculated start time has already passed: $LocalStart"
}

$ExecuteArgument = if ($Execute) { " -Execute" } else { "" }
$ActionArguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Runner`" -RunDate $RunDate$ExecuteArgument"
$Action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $ActionArguments -WorkingDirectory $RepoRoot
$Trigger = New-ScheduledTaskTrigger -Once -At $LocalStart
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 7)
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Limited
$TaskName = "KIS-Samsung-Mock-$($RunDate.Replace('-', ''))"

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "KIS mock-only Samsung trader for $RunDate KST" `
    -Force | Out-Null

Write-Host "Registered: $TaskName"
Write-Host "Local start time: $LocalStart"
Write-Host "KST target window: $RunDate 09:10-15:30"
if (-not $Execute) {
    Write-Warning "Dry-run task registered. Add -Execute only after preflight succeeds."
}
