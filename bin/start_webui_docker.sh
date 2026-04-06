#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

mkdir -p "${REPO_ROOT}/data" "${REPO_ROOT}/config/agent" "${REPO_ROOT}/results" "${REPO_ROOT}/logs"

export MC_NETPROBE_WEBUI_PORT="${MC_NETPROBE_WEBUI_PORT:-8765}"

cd "${REPO_ROOT}"
docker compose up --build -d

echo "mc-netprobe Panel is starting in Docker."
echo "URL: http://127.0.0.1:${MC_NETPROBE_WEBUI_PORT}"
echo "Public board: http://127.0.0.1:${MC_NETPROBE_WEBUI_PORT}/"
echo "Admin login:  http://127.0.0.1:${MC_NETPROBE_WEBUI_PORT}/login"
echo "If MC_NETPROBE_ADMIN_PASSWORD is unset, read ./data/admin-password.txt after the first start."
