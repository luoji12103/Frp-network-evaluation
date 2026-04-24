#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_FILE="${REPO_ROOT}/docker-compose.staging.yml"

RUNTIME_ROOT="${STAGING_RUNTIME_ROOT:-/root/server/mc-netprobe-panel-staging}"
ENV_DIR="${RUNTIME_ROOT}/env"
ENV_FILE="${STAGING_ENV_FILE:-${ENV_DIR}/staging.env}"
WEBUI_PORT="${MC_NETPROBE_STAGING_WEBUI_PORT:-18765}"
ADMIN_USERNAME="${MC_NETPROBE_ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${MC_NETPROBE_ADMIN_PASSWORD:-change-me}"
RELEASE_VERSION="${MC_NETPROBE_RELEASE_VERSION:-1.1.0}"
BUILD_REF="${MC_NETPROBE_BUILD_REF:-$(git -C "${REPO_ROOT}" rev-parse --short=12 HEAD 2>/dev/null || echo unknown)}"
INCLUDE_ACTIVE_BLOCKER="${STAGING_INCLUDE_ACTIVE_BLOCKER:-0}"

mkdir -p \
  "${RUNTIME_ROOT}/data" \
  "${RUNTIME_ROOT}/config/agent" \
  "${RUNTIME_ROOT}/results" \
  "${RUNTIME_ROOT}/logs" \
  "${ENV_DIR}"

touch "${ENV_FILE}"

upsert_env() {
  local key="$1"
  local value="$2"
  local escaped="${value//\\/\\\\}"
  escaped="${escaped//&/\\&}"
  escaped="${escaped//|/\\|}"
  if grep -q "^${key}=" "${ENV_FILE}"; then
    sed -i "s|^${key}=.*|${key}=${escaped}|" "${ENV_FILE}"
  else
    printf '%s=%s\n' "${key}" "${value}" >> "${ENV_FILE}"
  fi
}

upsert_env "STAGING_RUNTIME_ROOT" "${RUNTIME_ROOT}"
upsert_env "STAGING_ENV_FILE" "${ENV_FILE}"
upsert_env "MC_NETPROBE_STAGING_WEBUI_PORT" "${WEBUI_PORT}"
upsert_env "MC_NETPROBE_ADMIN_USERNAME" "${ADMIN_USERNAME}"
upsert_env "MC_NETPROBE_ADMIN_PASSWORD" "${ADMIN_PASSWORD}"
upsert_env "MC_NETPROBE_RELEASE_VERSION" "${RELEASE_VERSION}"
upsert_env "MC_NETPROBE_BUILD_REF" "${BUILD_REF}"

docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d --build panel panel-control-bridge

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${WEBUI_PORT}/api/v1/version" >/dev/null; then
    break
  fi
  sleep 2
done

SEED_CMD=(
  python
  -m
  controller.staging_seed
  --db-path
  /app/data/monitor.db
  --env-path
  /app/env/staging.env
)
if [[ "${INCLUDE_ACTIVE_BLOCKER}" == "1" ]]; then
  SEED_CMD+=(--include-active-blocker)
fi

docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" run --rm panel "${SEED_CMD[@]}"
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" --profile agents up -d client-sim relay-sim server-sim

docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" exec -T panel python - <<'PY'
import json
import time

from controller.panel_store import PanelStore

deadline = time.time() + 120
expected = {"client-sim", "relay-sim", "server-sim"}
store = PanelStore("data/monitor.db")

while time.time() < deadline:
    nodes = {item["node_name"]: item for item in store.list_nodes()}
    ready = {
        name: {
            "paired": bool(nodes.get(name, {}).get("paired")),
            "push": str(nodes.get(name, {}).get("connectivity", {}).get("push", {}).get("state")),
            "pull": str(nodes.get(name, {}).get("connectivity", {}).get("pull", {}).get("state")),
        }
        for name in expected
    }
    if all(ready[name]["paired"] and ready[name]["push"] == "ok" for name in expected):
        print(json.dumps(ready, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    time.sleep(2)

print(json.dumps(ready, ensure_ascii=False, indent=2))
raise SystemExit("Timed out waiting for staging sim agents to pair and report healthy push connectivity")
PY

docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" ps

cat <<EOF
Staging panel is ready.
URL: http://127.0.0.1:${WEBUI_PORT}
Public board: http://127.0.0.1:${WEBUI_PORT}/
Admin login:  http://127.0.0.1:${WEBUI_PORT}/login
Runtime root: ${RUNTIME_ROOT}
Env file:     ${ENV_FILE}
Build ref:    ${BUILD_REF}
EOF
