#!/usr/bin/env bash
set -euo pipefail

require_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "Required command not found: ${command_name}" >&2
    exit 1
  fi
}

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

require_command launchctl
require_command plutil
require_command "${PYTHON_BIN}"

PYTHON_BIN="$(command -v "${PYTHON_BIN}")"
PLIST_DIR="${HOME}/Library/LaunchAgents"
PLIST_PATH="${PLIST_DIR}/${LABEL}.plist"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_PATH="${REPO_ROOT}/logs/server-agent.launchd.log"
DOMAIN_TARGET="gui/$(id -u)"
SERVICE_TARGET="${DOMAIN_TARGET}/${LABEL}"

mkdir -p "${PLIST_DIR}" "${REPO_ROOT}/logs"

"${PYTHON_BIN}" "${REPO_ROOT}/agents/launchd.py" \
  --repo-root "${REPO_ROOT}" \
  --home-dir "${HOME}" \
  --python-bin "${PYTHON_BIN}" \
  --panel-url "${PANEL_URL}" \
  --pair-code "${PAIR_CODE}" \
  --node-name "${NODE_NAME}" \
  --role "${ROLE}" \
  --runtime-mode "${RUNTIME_MODE}" \
  --listen-host "0.0.0.0" \
  --listen-port "${LISTEN_PORT}" \
  --config "${CONFIG_PATH}" \
  --label "${LABEL}"

plutil -lint "${PLIST_PATH}"

if launchctl bootout "${SERVICE_TARGET}" >/dev/null 2>&1; then
  :
fi

LOAD_METHOD="bootstrap"
if ! launchctl bootstrap "${DOMAIN_TARGET}" "${PLIST_PATH}" >/dev/null 2>&1; then
  LOAD_METHOD="load"
fi

if [[ "${LOAD_METHOD}" == "bootstrap" ]]; then
  if ! launchctl kickstart -k "${SERVICE_TARGET}" >/dev/null 2>&1; then
    LOAD_METHOD="load"
  fi
fi

if [[ "${LOAD_METHOD}" == "load" ]]; then
  echo "launchctl bootstrap/kickstart failed; falling back to unload/load." >&2
  launchctl unload "${PLIST_PATH}" >/dev/null 2>&1 || true
  launchctl load "${PLIST_PATH}"
fi

echo "Installed launchd agent"
echo "  plist: ${PLIST_PATH}"
echo "  label: ${LABEL}"
echo "  logs: ${LOG_PATH}"
echo "  reload method: ${LOAD_METHOD}"
echo "Next checks:"
echo "  plutil -lint \"${PLIST_PATH}\""
echo "  launchctl print ${SERVICE_TARGET}"
echo "  tail -n 50 \"${LOG_PATH}\""
echo "  curl http://127.0.0.1:${LISTEN_PORT}/api/v1/status"
