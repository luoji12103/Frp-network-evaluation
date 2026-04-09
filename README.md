# mc-netprobe

`mc-netprobe` is a persistent monitoring toolkit for Minecraft + FRP network paths.

The repository now uses a `Panel + Agent` architecture:

- `panel`: central FastAPI dashboard, scheduler, history store, and report exporter
- `agent`: long-lived node process that runs probes locally and reports back to the panel
- `probes`: reusable cross-platform measurements for ping, TCP, throughput, and system snapshots

The panel no longer stores SSH credentials or private keys.

## Architecture

The monitoring topology is still the same logical three-role setup:

- `client`: Windows game client node
- `relay`: Linux FRP relay / public entry node
- `server`: macOS game server node

What changed is the execution model:

- The panel schedules work and aggregates results.
- Each node runs a local agent.
- Agents either receive direct pull-mode jobs from the panel or fetch queued jobs through heartbeat.
- Panel-managed pull addresses and agent-advertised runtime addresses are now tracked separately:
  - `configured_pull_url`: admin-configured pull target
  - `advertised_pull_url`: runtime-reported agent address
  - `effective_pull_url`: panel uses `configured_pull_url` first, then falls back to `advertised_pull_url`
- A separate lifecycle control plane now exists alongside the probe plane:
  - probe plane: pair / heartbeat / direct jobs / cached results
  - control plane: runtime sync, log tail, and host-supervised start / stop / restart
- Panel lifecycle control is Docker-first for strong operations. Native panel deployments expose read-only runtime plus scheduler control, and can tail logs when a stable local log file exists.

## Main Capabilities

- Continuous node health and network monitoring
- Threshold-based alerts
- Historical metric storage in SQLite
- Manual full-run execution from the panel
- Exported `raw.json`, `summary.csv`, and `report.html` for each completed run
- Mixed deployment model:
  - Linux relay: Docker agent
  - macOS server: native persistent agent
  - Windows client: native persistent agent

## Runtime Requirements

- Python 3.11+
- `iperf3`
- `ping`
- Docker + Docker Compose Plugin for the Linux relay or central panel container

## Install Dependencies

### Linux

```bash
bash bin/bootstrap_linux.sh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

### macOS

```bash
bash bin/bootstrap_mac.sh
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

### Windows

```powershell
.\bin\bootstrap_windows.ps1
python -m pip install -r requirements-dev.txt
```

## Start The Panel

### Native

```bash
source .venv/bin/activate
bash bin/start_webui.sh
```

Optional but recommended for native observability:

```bash
mkdir -p logs
bash bin/start_webui.sh >> logs/panel-native.log 2>&1
```

If `logs/panel-native.log` exists, the admin runtime view can expose native log tailing without a separate host bridge.

Open:

```text
http://127.0.0.1:8765
```

- Public board: `/`
- Admin login: `/login`
- Admin panel: `/admin`

### Docker

```bash
bash bin/start_webui_docker.sh
```

This starts the central panel container and persists:

- `./data`
- `./config/agent`
- `./results`
- `./logs`

The Docker stack also starts `panel-control-bridge`, which is the only component allowed to issue restart / stop / tail-log operations against the panel container.

## Admin Authentication

The public board is open at `/` and only shows network quality information.

The management UI is protected:

- `/login`: admin sign-in
- `/admin`: protected management page

Credentials come from either:

- `MC_NETPROBE_ADMIN_USERNAME` and `MC_NETPROBE_ADMIN_PASSWORD`
- or an auto-generated password stored at `data/admin-password.txt` with default username `admin`

For Docker, the simplest setup is:

```bash
export MC_NETPROBE_ADMIN_USERNAME=admin
export MC_NETPROBE_ADMIN_PASSWORD='change-me'
docker compose up --build -d
```

## Pair Nodes

The operator flow is:

1. Open `/admin` and sign in.
2. Save one card for each role: `client`, `relay`, `server`.
3. Click `生成配对命令`.
4. Run the generated command on the target node.
5. Wait for the agent to appear as `online`, `push-only`, or `pull-only`.

The panel stores:

- node metadata
- pair code hashes
- node token hashes
- schedules
- runs
- history
- alerts

The panel does not store:

- SSH usernames
- SSH private keys
- system passwords

## Runtime Control Plane

The admin UI now has a dedicated runtime-control surface.

- Nodes expose runtime summaries, supervisor state, push / pull connectivity, and lifecycle action history.
- The panel exposes runtime state, scheduler pause / resume, and deployment-aware lifecycle controls.
- Dangerous actions still require confirmation.
- Native panel mode is intentionally read-only for host lifecycle operations unless a panel control bridge is configured.

### Operations Workflow

- The management page now keeps action history and action detail on the same screen.
- The management page also keeps an `Operations focus` stack driven by backend runtime diagnostics, so active runs and node communication issues are visible without digging through logs first.
- Clicking an action opens normalized detail fields: target, actor, transport, failure summary, request / response snapshot, log excerpt, and runtime / supervisor snapshot.
- Lifecycle actions are serialized per target. If a node or the panel already has a `queued` or `running` action, the next action is rejected and the UI jumps to the active action.
- Nodes now expose structured connectivity diagnostics: `connectivity.diagnostic_code`, `connectivity.attention_level`, `connectivity.summary`, `connectivity.recommended_step`, plus per-channel `push.code` / `pull.code`.
- `GET /api/v1/admin/runtime` now also returns the current `active_run` and an `attention` summary list; the admin UI uses that payload to disable duplicate full-run launches and jump to the already-running run.
- Active runs now expose structured queue diagnostics through `progress.latest_queue_job`, so queued dispatches, leases, timeouts, completions, and ignored late completions are visible without reading raw job rows.
- Active runs also expose `progress.current_blocker` and `progress.headline`, so the backend can distinguish the current blocking step from older failures and the UI can reuse one canonical summary in the run list, run detail, and operations focus.
- Node runtime cards can surface `run_attention` when the active run is currently blocked on that node, and the same signal is mirrored into `runtime.details.active_run_*` for backend-driven UI decisions.
- Run event timeline items now carry backend-generated `summary`, `severity`, and `code` fields, which keeps queue and probe event explanations consistent between the API and WebUI.
- Native panel log tailing checks these locations in order:
  - `MC_NETPROBE_PANEL_LOG_FILE`
  - `logs/panel-native.log`
  - `logs/panel.log`
  - `logs/webui.log`
- Running run details now auto-refresh in the admin UI and surface current phase, latest event, event count, latest dispatched probe, latest queued job state, and the latest structured failure code / recovery hint when a phase degrades.

## Relay Agent On Linux Docker

The recommended relay deployment is Docker:

```bash
PANEL_URL="http://panel-host:8765" \
PAIR_CODE="<from-panel>" \
NODE_NAME="relay-1" \
ROLE="relay" \
RUNTIME_MODE="docker-linux" \
AGENT_PORT="9870" \
docker compose -f docker/relay-agent.compose.yml up -d --build
```

This relay stack starts two services:

- `relay-agent`: probe and heartbeat worker
- `relay-control-bridge`: allowlisted lifecycle bridge for runtime sync, log tail, start / stop / restart

## Server Agent On macOS

Recommended default:

```bash
bash bin/install_server_agent_launchd.sh \
  --panel-url "http://panel-host:8765" \
  --pair-code "<from-panel>" \
  --node-name "server-1" \
  --role "server" \
  --listen-port 9870
```

The installer now:

- validates `launchctl`, `plutil`, and the configured `PYTHON_BIN`
- writes `~/Library/LaunchAgents/com.mc-netprobe.server.agent.plist`
- writes `~/Library/LaunchAgents/com.mc-netprobe.server.control-bridge.plist`
- writes agent logs to `logs/server-agent.launchd.log`
- writes control bridge logs to `logs/server-control-bridge.launchd.log`
- prefers `bootout/bootstrap/kickstart` and falls back to `unload/load`

Recommended post-install checks:

```bash
plutil -lint ~/Library/LaunchAgents/com.mc-netprobe.server.agent.plist
plutil -lint ~/Library/LaunchAgents/com.mc-netprobe.server.control-bridge.plist
launchctl print gui/$(id -u)/com.mc-netprobe.server.agent
launchctl print gui/$(id -u)/com.mc-netprobe.server.control-bridge
tail -n 50 logs/server-agent.launchd.log
tail -n 50 logs/server-control-bridge.launchd.log
curl http://127.0.0.1:9870/api/v1/health
```

The full `/api/v1/status` payload is now token-protected and is intended for panel pull checks with `X-Node-Token`.

Simple fallback:

```bash
bash bin/start_agent_tmux.sh \
  --config config/agent/server.yaml \
  --panel-url "http://panel-host:8765" \
  --pair-code "<from-panel>" \
  --node-name "server-1" \
  --role server \
  --runtime-mode native-macos \
  --listen-port 9870
```

## Client Agent On Windows

Recommended default:

```powershell
powershell -ExecutionPolicy Bypass -File bin/install_client_agent.ps1 `
  -PanelUrl "http://panel-host:8765" `
  -PairCode "<from-panel>" `
  -NodeName "client-1" `
  -Role "client" `
  -ListenPort 9870
```

The installer creates both:

- `mc-netprobe-client-agent`
- `mc-netprobe-client-control-bridge`

## Panel API

Implemented panel endpoints:

- Public:
  - `GET /api/v1/public-dashboard`
- Admin session required:
  - `GET /api/v1/dashboard`
  - `POST /api/v1/dashboard`
  - `POST /api/v1/nodes`
  - `GET /api/v1/nodes/{id}`
  - `POST /api/v1/nodes/{id}/pair-code`
  - `POST /api/v1/runs`
  - `GET /api/v1/history`
  - `GET /api/v1/admin/runtime`
  - `GET /api/v1/admin/actions`
  - `GET /api/v1/admin/actions/{action_id}`
  - `POST /api/v1/admin/nodes/{node_id}/actions`
  - `POST /api/v1/admin/panel/actions`
  - `GET /api/v1/admin/runs/{run_id}/events`
- Agent traffic:
- `POST /api/v1/agents/pair`
- `POST /api/v1/agents/heartbeat`

Current communication model:

- `POST /api/v1/nodes` uses `configured_pull_url`
- dashboard node payloads expose explicit `endpoints` and `connectivity` objects
- `POST /api/v1/agents/pair` accepts `pair_code + identity + endpoint + capabilities`
- `POST /api/v1/agents/heartbeat` accepts `endpoint + runtime_status + completed_jobs`
- admin runtime payloads expose explicit `runtime` and `supervisor` objects
- node endpoint payloads expose `control_bridge_url` when a host bridge is available

Compatibility health endpoint:

- `GET /api/state` (public-safe snapshot)

## Agent API

Implemented agent endpoints:

- `GET /api/v1/health`
- `GET /api/v1/status` with `X-Node-Token`
- `POST /api/v1/pair`
- `POST /api/v1/heartbeat`
- `POST /api/v1/jobs/run` with `X-Node-Token`
- `GET /api/v1/results/{run_id}` with `X-Node-Token`

## Control Bridge API

Both node bridges and the optional panel bridge expose the same local contract:

- `GET /api/v1/control/runtime`
- `POST /api/v1/control/actions`

Auth headers depend on the target:

- node bridge: `X-Node-Token`
- panel bridge: `X-Control-Token`

## Testing

```bash
.venv/bin/python -m pytest -q tests/test_control_bridge.py tests/test_control_actions.py
.venv/bin/python -m pytest -q tests/test_launchd.py tests/test_agent_service.py tests/test_quickstart.py
.venv/bin/python -m pytest -q
```

Current automated coverage includes:

- panel defaults and pairing
- heartbeat job leasing and completion
- agent direct task execution and cached result lookup
- lifecycle control actions, confirmation flow, and control bridge transport
- composite full-run persistence
- probe parsing and exporters

## Legacy One-Shot CLI

The old one-shot YAML CLI still exists for local debugging:

```bash
python main.py \
  --topology config/topology.example.yaml \
  --thresholds config/thresholds.example.yaml \
  --scenarios config/scenarios.example.yaml
```

It is no longer the primary deployment path.

## Handoff

- `docs/HANDOFF-LINUX.md`
