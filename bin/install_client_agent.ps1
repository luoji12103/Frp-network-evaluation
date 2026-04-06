$ErrorActionPreference = "Stop"

param(
  [Parameter(Mandatory = $true)][string]$PanelUrl,
  [Parameter(Mandatory = $true)][string]$PairCode,
  [Parameter(Mandatory = $true)][string]$NodeName,
  [string]$Role = "client",
  [int]$ListenPort = 9870,
  [string]$ConfigPath = "config/agent/client.yaml",
  [string]$PythonBin = "python"
)

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$fullConfig = Join-Path $repoRoot $ConfigPath
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $fullConfig) | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$argument = "-m agents.service --config `"$fullConfig`" --panel-url `"$PanelUrl`" --pair-code `"$PairCode`" --node-name `"$NodeName`" --role `"$Role`" --runtime-mode native-windows --listen-host 0.0.0.0 --listen-port $ListenPort"
$taskName = "mc-netprobe-client-agent"

$action = New-ScheduledTaskAction -Execute $PythonBin -Argument $argument -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "mc-netprobe persistent client agent" -Force | Out-Null
Start-ScheduledTask -TaskName $taskName

Write-Host "Installed scheduled task: $taskName"
