$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$paths = @(
  (Join-Path $repoRoot "data"),
  (Join-Path $repoRoot "config\\agent"),
  (Join-Path $repoRoot "results"),
  (Join-Path $repoRoot "logs")
)
foreach ($path in $paths) {
  if (-not (Test-Path $path)) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
  }
}

if (-not $env:MC_NETPROBE_WEBUI_PORT) {
  $env:MC_NETPROBE_WEBUI_PORT = "8765"
}

Push-Location $repoRoot
try {
  docker compose up --build -d
} finally {
  Pop-Location
}

Write-Host "mc-netprobe Panel is starting in Docker."
Write-Host "URL: http://127.0.0.1:$($env:MC_NETPROBE_WEBUI_PORT)"
