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
BRIDGE_LABEL="com.mc-netprobe.server.control-bridge"

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
BRIDGE_PLIST_PATH="${PLIST_DIR}/${BRIDGE_LABEL}.plist"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_PATH="${REPO_ROOT}/logs/server-agent.launchd.log"
BRIDGE_LOG_PATH="${REPO_ROOT}/logs/server-control-bridge.launchd.log"
DOMAIN_TARGET="gui/$(id -u)"
SERVICE_TARGET="${DOMAIN_TARGET}/${LABEL}"
BRIDGE_SERVICE_TARGET="${DOMAIN_TARGET}/${BRIDGE_LABEL}"
CONTROL_PORT="$((LISTEN_PORT + 1))"

resolve_listen_host() {
  local config_candidate="$1"
  if [[ -f "${config_candidate}" ]]; then
    "${PYTHON_BIN}" - "$config_candidate" <<'PY'
from pathlib import Path
import sys
import yaml

path = Path(sys.argv[1])
loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
if isinstance(loaded, dict) and loaded.get("listen_host"):
    print(str(loaded["listen_host"]))
else:
    print("0.0.0.0")
PY
  else
    echo "0.0.0.0"
  fi
}

LISTEN_HOST="$(resolve_listen_host "${REPO_ROOT}/${CONFIG_PATH}")"

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
  --listen-host "${LISTEN_HOST}" \
  --listen-port "${LISTEN_PORT}" \
  --control-port "${CONTROL_PORT}" \
  --config "${CONFIG_PATH}" \
  --label "${LABEL}"

"${PYTHON_BIN}" "${REPO_ROOT}/agents/launchd_control_bridge.py" \
  --repo-root "${REPO_ROOT}" \
  --home-dir "${HOME}" \
  --python-bin "${PYTHON_BIN}" \
  --bridge-host "${LISTEN_HOST}" \
  --bridge-port "${CONTROL_PORT}" \
  --agent-config "${CONFIG_PATH}" \
  --agent-label "${LABEL}" \
  --bridge-label "${BRIDGE_LABEL}" \
  --bridge-log-path "${BRIDGE_LOG_PATH}"

plutil -lint "${PLIST_PATH}"
plutil -lint "${BRIDGE_PLIST_PATH}"

reload_service() {
  local plist_path="$1"
  local service_target="$2"
  local load_method="bootstrap"
  launchctl bootout "${service_target}" >/dev/null 2>&1 || true
  if ! launchctl bootstrap "${DOMAIN_TARGET}" "${plist_path}" >/dev/null 2>&1; then
    load_method="load"
  fi

  if [[ "${load_method}" == "bootstrap" ]]; then
    if ! launchctl kickstart -k "${service_target}" >/dev/null 2>&1; then
      load_method="load"
    fi
  fi

  if [[ "${load_method}" == "load" ]]; then
    echo "launchctl bootstrap/kickstart failed for ${service_target}; falling back to unload/load." >&2
    launchctl unload "${plist_path}" >/dev/null 2>&1 || true
    launchctl load "${plist_path}"
  fi
}

reload_service "${PLIST_PATH}" "${SERVICE_TARGET}"
reload_service "${BRIDGE_PLIST_PATH}" "${BRIDGE_SERVICE_TARGET}"

echo "Installed launchd agent and control bridge"
echo "  plist: ${PLIST_PATH}"
echo "  bridge plist: ${BRIDGE_PLIST_PATH}"
echo "  label: ${LABEL}"
echo "  bridge label: ${BRIDGE_LABEL}"
echo "  logs: ${LOG_PATH}"
echo "  bridge logs: ${BRIDGE_LOG_PATH}"
echo "  listen host: ${LISTEN_HOST}"
echo "  control port: ${CONTROL_PORT}"
echo "Next checks:"
echo "  plutil -lint \"${PLIST_PATH}\""
echo "  plutil -lint \"${BRIDGE_PLIST_PATH}\""
echo "  launchctl print ${SERVICE_TARGET}"
echo "  launchctl print ${BRIDGE_SERVICE_TARGET}"
echo "  tail -n 50 \"${LOG_PATH}\""
echo "  tail -n 50 \"${BRIDGE_LOG_PATH}\""
echo "  curl http://127.0.0.1:${LISTEN_PORT}/api/v1/health"
