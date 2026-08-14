# Register a Windows Task Scheduler job: daily prospect search at 9:00 AM Eastern.
#
# Run PowerShell as Administrator from the repo root:
#   powershell -ExecutionPolicy Bypass -File scripts\register_scheduled_task.ps1
#
# Optional: pass a custom repo path
#   powershell -ExecutionPolicy Bypass -File scripts\register_scheduled_task.ps1 -RepoPath "C:\path\to\ClientsUS"

param(
    [string]$RepoPath = (Split-Path -Parent $PSScriptRoot),
    [string]$TaskName = "ClientsUS-DailyProspectSearch"
)

$BatPath = Join-Path $RepoPath "scripts\run_daily_search.bat"
if (-not (Test-Path $BatPath)) {
    Write-Error "Batch file not found: $BatPath"
    exit 1
}

$Action = New-ScheduledTaskAction -Execute $BatPath -WorkingDirectory $RepoPath
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries

# Eastern time (handles EST/EDT automatically on supported Windows versions)
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Daily search for US website/software/mobile development opportunities (ClientsUS)" `
    -Force

schtasks /Change /TN $TaskName /TZ "Eastern Standard Time" 2>$null

Write-Host "Scheduled task '$TaskName' registered."
Write-Host "  Runs daily at 9:00 AM Eastern"
Write-Host "  Script: $BatPath"
Write-Host "  Logs:   $(Join-Path $RepoPath 'logs\daily_search.log')"
Write-Host ""
Write-Host "Open Task Scheduler to verify, or run manually:"
Write-Host "  schtasks /Run /TN $TaskName"
