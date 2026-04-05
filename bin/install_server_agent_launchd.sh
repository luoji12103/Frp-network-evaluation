#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
PANEL_URL=""
PAIR_CODE=""
NODE_NAME="server"
ROLE="server"
LISTEN_PORT="9870"
CONFIG_PATH="${CONFIG_PATH:-config/agent/server.yaml}"
RUNTIME_MODE="native-macos"
LABEL="com.mc-netprobe.server.agent"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --panel-url) PANEL_URL="$2"; shift 2 ;;
    --pair-code) PAIR_CODE="$2"; shift 2 ;;
    --node-name) NODE_NAME="$2"; shift 2 ;;
    --role) ROLE="$2"; shift 2 ;;
    --listen-port) LISTEN_PORT="$2"; shift 2 ;;
    --config) CONFIG_PATH="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "${PANEL_URL}" || -z "${PAIR_CODE}" ]]; then
  echo "--panel-url and --pair-code are required" >&2
  exit 1
fi

PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${PLIST_DIR}/${LABEL}.plist"
mkdir -p "${PLIST_DIR}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cat > "${PLIST_PATH}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>-m</string>
    <string>agents.service</string>
    <string>--config</string>
    <string>${REPO_ROOT}/${CONFIG_PATH}</string>
    <string>--panel-url</string>
    <string>${PANEL_URL}</string>
    <string>--pair-code</string>
    <string>${PAIR_CODE}</string>
    <string>--node-name</string>
    <string>${NODE_NAME}</string>
    <string>--role</string>
    <string>${ROLE}</string>
    <string>--runtime-mode</string>
    <string>${RUNTIME_MODE}</string>
    <string>--listen-host</string>
    <string>0.0.0.0</string>
    <string>--listen-port</string>
    <string>${LISTEN_PORT}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${REPO_ROOT}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${REPO_ROOT}/logs/server-agent.launchd.log</string>
  <key>StandardErrorPath</key>
  <string>${REPO_ROOT}/logs/server-agent.launchd.log</string>
</dict>
</plist>
PLIST

mkdir -p "${REPO_ROOT}/logs"
launchctl unload "${PLIST_PATH}" >/dev/null 2>&1 || true
launchctl load "${PLIST_PATH}"

echo "Installed launchd agent: ${PLIST_PATH}"
