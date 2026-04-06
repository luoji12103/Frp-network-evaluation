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
5. Wait for the agent to appear as `online`, `push-only`, or `heartbeat-degraded`.

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
- Agent traffic:
- `POST /api/v1/agents/pair`
- `POST /api/v1/agents/heartbeat`

Compatibility health endpoint:

- `GET /api/state` (public-safe snapshot)

## Agent API

Implemented agent endpoints:

- `GET /api/v1/status`
- `POST /api/v1/pair`
- `POST /api/v1/heartbeat`
- `POST /api/v1/jobs/run`
- `GET /api/v1/results/{run_id}`

## Testing

```bash
source .venv/bin/activate
python -m pytest -q
```

Current automated coverage includes:

- panel defaults and pairing
- heartbeat job leasing and completion
- agent direct task execution and cached result lookup
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
