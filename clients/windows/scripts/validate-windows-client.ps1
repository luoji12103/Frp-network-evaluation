$ErrorActionPreference = "Stop"

$service = Get-Service -Name mc-netprobe-client
Write-Host "Service: $($service.Status)"

$agentRule = Get-NetFirewallRule -DisplayName "mc-netprobe-client-agent-9870" -ErrorAction SilentlyContinue
if (-not $agentRule) {
  throw "Missing firewall rule mc-netprobe-client-agent-9870"
}
Write-Host "Firewall rule: $($agentRule.DisplayName)"

$processes = Get-Process | Where-Object { $_.ProcessName -match "python|mc-netprobe" }
Write-Host "Related process count: $($processes.Count)"

$configPath = "C:\ProgramData\mc-netprobe\client\config\agent\client.yaml"
$logsPath = "C:\ProgramData\mc-netprobe\client\logs"
if (-not (Test-Path $configPath)) { throw "Missing config: $configPath" }
if (-not (Test-Path $logsPath)) { throw "Missing logs directory: $logsPath" }

Write-Host "Validation complete"
