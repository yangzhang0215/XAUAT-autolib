param(
  [string]$TaskName = "XAUAT-Libspace-Reserve-Python",
  [string]$PyLauncher = "py -3",
  [string]$TriggerTime = "07:00"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$CliScript = Join-Path $RepoRoot "python\cli.py"

if (-not (Test-Path $CliScript)) {
  throw "Python CLI not found: $CliScript"
}

$Command = "cmd.exe /c `"cd /d `"$RepoRoot`" && $PyLauncher python\cli.py reserve-once`""
schtasks /Create /F /SC DAILY /TN $TaskName /TR $Command /ST $TriggerTime | Out-Host
Write-Host "Scheduled task registered: $TaskName"
