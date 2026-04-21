param(
  [Parameter(Mandatory = $true)][string]$PanelUrl,
  [Parameter(Mandatory = $true)][string]$PairCode,
  [Parameter(Mandatory = $true)][string]$NodeName,
  [string]$Role = "client",
  [int]$ListenPort = 9870,
  [string]$ConfigPath = "config/agent/client.yaml",
  [string]$PythonBin = "python"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$fullConfig = Join-Path $repoRoot $ConfigPath
$logDir = Join-Path $repoRoot "logs"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $fullConfig) | Out-Null
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$controlPort = $ListenPort + 1
$agentLog = Join-Path $logDir "client-agent.log"
$bridgeLog = Join-Path $logDir "client-control-bridge.log"
$argument = "-m agents.service --config `"$fullConfig`" --panel-url `"$PanelUrl`" --pair-code `"$PairCode`" --node-name `"$NodeName`" --role `"$Role`" --runtime-mode native-windows --listen-host 0.0.0.0 --listen-port $ListenPort --control-port $controlPort"
$bridgeArgument = "-m controller.control_bridge --mode node --adapter windows-task --host 0.0.0.0 --port $controlPort --agent-config `"$fullConfig`" --task-name `"mc-netprobe-client-agent`" --log-path `"$bridgeLog`""
$taskName = "mc-netprobe-client-agent"
$bridgeTaskName = "mc-netprobe-client-control-bridge"

$action = New-ScheduledTaskAction -Execute $PythonBin -Argument $argument -WorkingDirectory $repoRoot
$bridgeAction = New-ScheduledTaskAction -Execute $PythonBin -Argument $bridgeArgument -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "mc-netprobe persistent client agent" -Force | Out-Null
Register-ScheduledTask -TaskName $bridgeTaskName -Action $bridgeAction -Trigger $trigger -Settings $settings -Description "mc-netprobe control bridge for client agent" -Force | Out-Null
Start-ScheduledTask -TaskName $taskName
Start-ScheduledTask -TaskName $bridgeTaskName

Write-Host "Installed scheduled task: $taskName"
Write-Host "Installed scheduled task: $bridgeTaskName"
