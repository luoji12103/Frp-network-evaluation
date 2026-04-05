# mc-netprobe

`mc-netprobe` is a Python 3.11+ network evaluation toolkit for Minecraft deployments behind FRP.

It focuses on three kinds of measurements:

- end-to-end client to `mc_public`
- segmented path checks (`client -> relay`, `relay -> server`)
- load-driven latency inflation while `iperf3` is saturating the path

## Supported runtime targets

- Windows 10/11 as a formal `client` node
- macOS as `client` or `server`
- Ubuntu/Debian as `relay`

Windows is supported as a runtime client, not only as a development machine.

## Repository layout

The project keeps a strict separation of responsibilities:

- `probes/`: parsing and measurement logic
- `agents/`: single-task wrappers used locally or over SSH
- `controller/`: orchestration and remote execution
- `exporters/`: `raw.json`, `summary.csv`, `report.html`
- `config/`: example YAML inputs

## Quick start

### Windows PowerShell

```powershell
.\bin\bootstrap_windows.ps1
python main.py --topology config/topology.example.yaml --thresholds config/thresholds.example.yaml --scenarios config/scenarios.example.yaml
```

### macOS

```bash
bash bin/bootstrap_mac.sh
python3 main.py --topology config/topology.example.yaml --thresholds config/thresholds.example.yaml --scenarios config/scenarios.example.yaml
```

### Linux

```bash
bash bin/bootstrap_linux.sh
python3 main.py --topology config/topology.example.yaml --thresholds config/thresholds.example.yaml --scenarios config/scenarios.example.yaml
```

## Web UI

If you want a single page to manage the three-node test architecture and trigger runs without editing YAML manually, start the built-in Web UI.

### Windows

```powershell
.\bin\start_webui.ps1
```

### macOS / Linux

```bash
bash bin/start_webui.sh
```

Then open `http://127.0.0.1:8765`.

The Web UI lets you:

- configure client / relay / server connection details
- save a reusable YAML-backed topology
- trigger a background test run
- watch recent runs and open `report.html` directly from the browser

## Docker one-click startup

If you want the Web UI and Python runtime fully containerized, use Docker Compose.

Prerequisite: Docker Desktop or the Docker daemon must already be running before you start the helper script.

### Windows PowerShell

```powershell
.\bin\start_webui_docker.ps1
```

### macOS / Linux

```bash
bash bin/start_webui_docker.sh
```

This will:

- build the container image
- start the Web UI with `docker compose up --build -d`
- persist Web UI config in `config/webui/`
- persist run artifacts in `results/`
- persist runtime logs in `logs/`
- mount an SSH directory so the container can reach your remote nodes

Default URL:

```text
http://127.0.0.1:8765
```

### SSH keys inside the container

By default the helper script tries to mount your normal SSH directory:

- Windows: `%USERPROFILE%\.ssh`
- macOS / Linux: `~/.ssh`

If you want to use a dedicated directory instead, set:

```text
MC_NETPROBE_SSH_DIR
```

before running the helper script.

If you do not want to mount your normal SSH directory, you can also place keys in:

```text
docker/ssh/
```

The Compose service exposes the Web UI only. The actual test traffic still runs against your configured client / relay / server nodes through SSH and direct TCP connectivity.

## Beginner quickstart scripts

For a real three-machine test, start from these role-specific scripts instead of editing YAML by hand.

### 1. Mac server

```bash
bash bin/start_server_mac.sh
```

This script will:

- check `sshd`, `iperf3`, and the local Minecraft port
- optionally let you input a Minecraft startup command and run it in the background
- write a shareable summary to `config/generated/server-mac.generated.yaml`

### 2. Relay Linux / FRPS host

```bash
bash bin/start_relay_linux.sh
```

This script will:

- check `sshd`, `frps`, and the public FRP ports
- optionally let you input an `frps` startup command
- write a shareable summary to `config/generated/relay-linux.generated.yaml`

### 3. Windows client

```powershell
.\bin\start_client_windows.ps1
```

This script will:

- ask for relay/server/public entry information if it is still missing
- generate `config/topology.quickstart.yaml`
- optionally launch a full test immediately from the Windows client

The quickstart scripts are designed for small-step manual setup. If an IP, username, path, or port is not known yet, they will prompt for it.

## Configuration

### `config/topology.example.yaml`

Defines:

- `nodes.client`
- `nodes.relay`
- `nodes.server`
- `services.relay_probe`
- `services.mc_public`
- `services.iperf_public`
- `services.mc_local`
- `services.iperf_local`

Each node must define:

- `role`
- `host`
- `os` with one of `windows`, `macos`, `linux`

Remote nodes additionally need:

- `ssh_user`
- `ssh_port`
- `project_root`
- `python_bin`

For local debug you can mark nodes as `local: true`.

## Notes

- `iperf3` is required for throughput and load-inflation probes.
- If `iperf3` is missing, the run still completes and records the failure clearly in `raw.json`.
- Windows system snapshots intentionally report `load_avg_* = null` with `unsupported_on_windows` metadata.

## Agent examples

```bash
python -m agents.agent_client --task ping --host 127.0.0.1 --count 4 --json
python -m agents.agent_server --task start_iperf_server --port 5201 --one-off --json
python -m agents.agent_relay --task tcp_probe --host 192.168.1.20 --port 25565 --attempts 6 --json
```

## Output

Every run creates a dedicated directory:

```text
results/run-YYYYMMDD-HHMMSS/
```

And writes:

- `raw.json`
- `summary.csv`
- `report.html`

## Local skill

The repository-local `skill/codex-change-trace` skill has been copied into the Codex skills directory.
Restart Codex to pick it up in a new session.

## Handoff

If you want to continue development and testing on a Linux server, see:

- `docs/HANDOFF-LINUX.md`
