#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

mkdir -p "${REPO_ROOT}/config/webui" "${REPO_ROOT}/results" "${REPO_ROOT}/logs" "${REPO_ROOT}/docker/ssh"

if [[ -z "${MC_NETPROBE_SSH_DIR:-}" ]]; then
  if [[ -d "${HOME}/.ssh" ]]; then
    export MC_NETPROBE_SSH_DIR="${HOME}/.ssh"
  else
    export MC_NETPROBE_SSH_DIR="${REPO_ROOT}/docker/ssh"
  fi
fi

export MC_NETPROBE_WEBUI_PORT="${MC_NETPROBE_WEBUI_PORT:-8765}"

cd "${REPO_ROOT}"
docker compose up --build -d

echo "mc-netprobe Web UI is starting in Docker."
echo "URL: http://127.0.0.1:${MC_NETPROBE_WEBUI_PORT}"
echo "SSH directory mounted from: ${MC_NETPROBE_SSH_DIR}"
