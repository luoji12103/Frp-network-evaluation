#!/usr/bin/env bash
set -euo pipefail

if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux is required for this helper." >&2
  exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
SESSION_NAME="${MC_NETPROBE_AGENT_SESSION:-mc-netprobe-agent}"

tmux has-session -t "${SESSION_NAME}" 2>/dev/null && tmux kill-session -t "${SESSION_NAME}"
tmux new-session -d -s "${SESSION_NAME}" "${PYTHON_BIN} -m agents.service $*"

echo "Started agent in tmux session: ${SESSION_NAME}"
