#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/config/agent /app/results /app/logs /app/data

if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec python -m controller.webui \
  --host "${MC_NETPROBE_WEBUI_HOST:-0.0.0.0}" \
  --port "${MC_NETPROBE_WEBUI_PORT:-8765}" \
  --db-path "${MC_NETPROBE_PANEL_DB_PATH:-data/monitor.db}"
