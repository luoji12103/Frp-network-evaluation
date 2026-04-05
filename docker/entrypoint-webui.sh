#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/config/webui /app/results /app/logs /home/app/.ssh
chmod 700 /home/app/.ssh || true

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec python -m controller.webui \
  --host "${MC_NETPROBE_WEBUI_HOST:-0.0.0.0}" \
  --port "${MC_NETPROBE_WEBUI_PORT:-8765}"
