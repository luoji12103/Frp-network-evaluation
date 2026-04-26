param(
  [string]$BuildRef = "dev",
  [string]$Version = "0.1.0",
  [string]$PythonRuntime = "python",
  [string]$OutputDir = "clients/windows/dist"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$distRoot = Join-Path $repoRoot $OutputDir
$stage = Join-Path $distRoot "stage"
$zipName = "mc-netprobe-client-windows-x64-$Version-$BuildRef.zip"
$zipPath = Join-Path $distRoot $zipName

Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "python") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "repo") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "templates") | Out-Null

Copy-Item (Join-Path $repoRoot "clients/windows/templates/*") (Join-Path $stage "templates") -Recurse -Force
Copy-Item (Join-Path $repoRoot "clients/windows/README-WINDOWS.md") (Join-Path $stage "README-WINDOWS.md") -Force
Copy-Item (Join-Path $repoRoot "target/release/mc-netprobe-tray.exe") (Join-Path $stage "mc-netprobe-tray.exe") -Force
Copy-Item (Join-Path $repoRoot "target/release/mc-netprobe-service.exe") (Join-Path $stage "mc-netprobe-service.exe") -Force
Copy-Item (Join-Path $repoRoot "target/release/mc-netprobe-elevate.exe") (Join-Path $stage "mc-netprobe-elevate.exe") -Force
Copy-Item $PythonRuntime (Join-Path $stage "python") -Recurse -Force

foreach ($path in @("agents", "controller", "probes", "exporters", "requirements.txt")) {
  Copy-Item (Join-Path $repoRoot $path) (Join-Path $stage "repo") -Recurse -Force
}

Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath
Write-Host $zipPath
