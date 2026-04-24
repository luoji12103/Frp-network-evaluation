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
RESET_RUNTIME="${STAGING_RESET_RUNTIME:-1}"
PAUSE_SCHEDULER="${STAGING_PAUSE_SCHEDULER:-1}"

ensure_runtime_layout() {
  mkdir -p \
    "${RUNTIME_ROOT}/data" \
    "${RUNTIME_ROOT}/config/agent" \
    "${RUNTIME_ROOT}/results" \
    "${RUNTIME_ROOT}/logs" \
    "${ENV_DIR}"
  touch "${ENV_FILE}"
}

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

write_runtime_env() {
  upsert_env "STAGING_RUNTIME_ROOT" "${RUNTIME_ROOT}"
  upsert_env "STAGING_ENV_FILE" "${ENV_FILE}"
  upsert_env "MC_NETPROBE_STAGING_WEBUI_PORT" "${WEBUI_PORT}"
  upsert_env "MC_NETPROBE_ADMIN_USERNAME" "${ADMIN_USERNAME}"
  upsert_env "MC_NETPROBE_ADMIN_PASSWORD" "${ADMIN_PASSWORD}"
  upsert_env "MC_NETPROBE_RELEASE_VERSION" "${RELEASE_VERSION}"
  upsert_env "MC_NETPROBE_BUILD_REF" "${BUILD_REF}"
}

compose() {
  docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" "$@"
}

pause_scheduler_via_admin_api() {
  compose exec -T panel python - <<'PY'
import http.cookiejar
import json
import os
import time
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8765"
USERNAME = os.environ["MC_NETPROBE_ADMIN_USERNAME"]
PASSWORD = os.environ["MC_NETPROBE_ADMIN_PASSWORD"]

jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def request(method: str, path: str, *, form: dict[str, str] | None = None, json_body: dict[str, object] | None = None) -> tuple[int, object]:
    headers = {"Accept": "application/json, text/html;q=0.9"}
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif json_body is not None:
        body = json.dumps(json_body).encode("utf-8")
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    with opener.open(req, timeout=15) as response:
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return response.status, json.loads(raw.decode("utf-8") or "{}")
        return response.status, raw.decode("utf-8")


request(
    "POST",
    "/login",
    form={
        "username": USERNAME,
        "password": PASSWORD,
        "next": "/admin",
    },
)

status, runtime_payload = request("GET", "/api/v1/admin/runtime")
if status != 200:
    raise SystemExit(f"Unable to authenticate against admin runtime API (status={status})")

panel_runtime = (((runtime_payload or {}).get("panel") or {}).get("runtime") or {})
details = (panel_runtime.get("details") or {}) if isinstance(panel_runtime, dict) else {}
if details.get("scheduler_paused"):
    print("Scheduler already paused.")
    raise SystemExit(0)

status, action_payload = request(
    "POST",
    "/api/v1/admin/panel/actions",
    json_body={"action": "pause_scheduler", "actor": "staging-bootstrap"},
)
if status != 200:
    raise SystemExit(f"Pause scheduler request failed (status={status}): {action_payload}")

if isinstance(action_payload, dict) and action_payload.get("confirmation_required"):
    token = action_payload.get("confirmation_token")
    if not token:
        raise SystemExit("Pause scheduler confirmation token was not returned")
    status, action_payload = request(
        "POST",
        "/api/v1/admin/panel/actions",
        json_body={
            "action": "pause_scheduler",
            "actor": "staging-bootstrap",
            "confirmation_token": str(token),
        },
    )
    if status != 200:
        raise SystemExit(f"Pause scheduler confirmation failed (status={status}): {action_payload}")

deadline = time.time() + 30
while time.time() < deadline:
    status, runtime_payload = request("GET", "/api/v1/admin/runtime")
    if status != 200:
        time.sleep(1)
        continue
    panel_runtime = (((runtime_payload or {}).get("panel") or {}).get("runtime") or {})
    details = (panel_runtime.get("details") or {}) if isinstance(panel_runtime, dict) else {}
    if details.get("scheduler_paused"):
        print(json.dumps({"scheduler_paused": True, "checked_at": panel_runtime.get("checked_at")}, ensure_ascii=False))
        raise SystemExit(0)
    time.sleep(1)

raise SystemExit("Timed out waiting for scheduler to pause")
PY
}

ensure_runtime_layout
write_runtime_env

if [[ "${RESET_RUNTIME}" == "1" ]]; then
  compose down --remove-orphans || true
  rm -rf "${RUNTIME_ROOT}"
  ensure_runtime_layout
  write_runtime_env
fi

compose up -d --build panel panel-control-bridge

for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:${WEBUI_PORT}/api/v1/version" >/dev/null; then
    break
  fi
  sleep 2
done

if [[ "${PAUSE_SCHEDULER}" == "1" ]]; then
  pause_scheduler_via_admin_api
fi

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

compose run --rm panel "${SEED_CMD[@]}"
compose --profile agents up -d client-sim relay-sim server-sim

compose exec -T panel python - <<'PY'
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

compose ps

cat <<EOF
Staging panel is ready.
URL: http://127.0.0.1:${WEBUI_PORT}
Public board: http://127.0.0.1:${WEBUI_PORT}/
Admin login:  http://127.0.0.1:${WEBUI_PORT}/login
Runtime root: ${RUNTIME_ROOT}
Env file:     ${ENV_FILE}
Build ref:    ${BUILD_REF}
Runtime reset: ${RESET_RUNTIME}
Scheduler paused: ${PAUSE_SCHEDULER}
EOF
