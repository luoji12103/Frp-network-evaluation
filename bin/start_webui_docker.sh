#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

mkdir -p "${REPO_ROOT}/data" "${REPO_ROOT}/config/agent" "${REPO_ROOT}/results" "${REPO_ROOT}/logs"

export MC_NETPROBE_WEBUI_PORT="${MC_NETPROBE_WEBUI_PORT:-8765}"
export MC_NETPROBE_RELEASE_VERSION="${MC_NETPROBE_RELEASE_VERSION:-1.0}"
if [[ -z "${MC_NETPROBE_BUILD_REF:-}" ]]; then
  if command -v git >/dev/null 2>&1 && git -C "${REPO_ROOT}" rev-parse --short=12 HEAD >/dev/null 2>&1; then
    export MC_NETPROBE_BUILD_REF="$(git -C "${REPO_ROOT}" rev-parse --short=12 HEAD)"
  else
    export MC_NETPROBE_BUILD_REF="unknown"
  fi
fi

cd "${REPO_ROOT}"
docker compose up --build -d

echo "mc-netprobe Panel is starting in Docker."
echo "URL: http://127.0.0.1:${MC_NETPROBE_WEBUI_PORT}"
echo "Public board: http://127.0.0.1:${MC_NETPROBE_WEBUI_PORT}/"
echo "Admin login:  http://127.0.0.1:${MC_NETPROBE_WEBUI_PORT}/login"
echo "Version:      ${MC_NETPROBE_RELEASE_VERSION} (${MC_NETPROBE_BUILD_REF})"
echo "If MC_NETPROBE_ADMIN_PASSWORD is unset, read ./data/admin-password.txt after the first start."
