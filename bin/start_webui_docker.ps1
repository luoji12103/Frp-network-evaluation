$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$paths = @(
  (Join-Path $repoRoot "config\\webui"),
  (Join-Path $repoRoot "results"),
  (Join-Path $repoRoot "logs"),
  (Join-Path $repoRoot "docker\\ssh")
)
foreach ($path in $paths) {
  if (-not (Test-Path $path)) {
    New-Item -ItemType Directory -Path $path -Force | Out-Null
  }
}

if (-not $env:MC_NETPROBE_SSH_DIR) {
  if (Test-Path "$HOME\\.ssh") {
    $env:MC_NETPROBE_SSH_DIR = "$HOME\\.ssh"
  } else {
    $env:MC_NETPROBE_SSH_DIR = (Join-Path $repoRoot "docker\\ssh")
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

Write-Host "mc-netprobe Web UI is starting in Docker."
Write-Host "URL: http://127.0.0.1:$($env:MC_NETPROBE_WEBUI_PORT)"
Write-Host "SSH directory mounted from: $($env:MC_NETPROBE_SSH_DIR)"
