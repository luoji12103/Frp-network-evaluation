# Windows Client Tray and Service Design

Date: 2026-04-26
Branch base: `origin/feat/saas-webui-rewrite` at `21dc1bb3d0c0`
Target branch: `codex/windows-client-tray-service`

## Summary

The Windows client will ship as a portable x64 zip for Windows 10 and Windows 11. The zip is an installer/launcher package, not the final runtime location. On first initialization, an elevated helper copies the runtime to `C:\ProgramData\mc-netprobe\client`, registers a Windows Service, configures firewall rules, starts the service, and verifies pairing with the panel.

The user-facing desktop experience is a Tauri/Rust tray app. The always-on background runtime is a single Rust Windows Service supervisor. The service starts and monitors the existing Python agent and node control bridge as hidden child processes using an embedded Python runtime bundled in the zip. The tray communicates with the service through Windows Named Pipes and provides status, initialization, service controls, and shortcuts to config, logs, and the panel.

## Goals

- Provide a Windows client that starts before user login through a system-level Windows Service.
- Keep normal operation free of command-line windows.
- Include Python and dependencies so users do not need to install Python or manage `PATH`.
- Support a tray icon for status and quick operations after user login.
- Support first-run initialization through a guided UI and advanced YAML editing.
- Automatically configure Windows Firewall rules for the required ports.
- Preserve the existing panel-agent JSON contracts and current `agents.service` behavior.
- Keep the first implementation focused enough to deliver and validate on Windows 10/11 x64.

## Non-Goals

- No MSI installer in the first version.
- No auto-updater in the first version.
- No arm64 build in the first version.
- No full desktop control console in the first version.
- No multi-profile or multi-node management in the first version.
- No production code signing requirement in the first version.
- No backend panel API changes solely for the Windows client.

## Existing Context

The current Windows install path is script-based:

- `bin/install_client_agent.ps1` creates two Scheduled Tasks: `mc-netprobe-client-agent` and `mc-netprobe-client-control-bridge`.
- The agent runs `python -m agents.service` with `runtime_mode=native-windows`.
- The node control bridge runs `python -m controller.control_bridge --mode node --adapter windows-task`.
- The panel already consumes agent pair, heartbeat, job dispatch, result lookup, and control bridge runtime/actions contracts.

This design replaces the Scheduled Task background model for the new Windows client. Existing scripts can remain for compatibility and debugging, but the new production path is a Rust Windows Service supervisor.

## Runtime Architecture

The runtime has three layers.

```text
User session
  mc-netprobe-tray.exe
    - tray menu
    - initialization wizard
    - config/log/panel shortcuts
    - Named Pipe client

System service session
  mc-netprobe-service.exe
    - Windows Service entrypoint
    - Named Pipe server
    - starts and monitors child processes
    - writes supervisor logs and status snapshots

Embedded Python runtime
  python\python.exe -m agents.service
  python\python.exe -m controller.control_bridge
```

The service supervisor is the only persistent background owner. It starts and monitors:

- Agent process:
  `python\python.exe -m agents.service --config C:\ProgramData\mc-netprobe\client\config\agent\client.yaml`
- Control bridge process:
  `python\python.exe -m controller.control_bridge --mode node --adapter windows-service-supervisor --host <host> --port <port> --agent-config <client.yaml> --log-path <control-bridge.log>`

The `windows-service-supervisor` adapter is a new control bridge adapter for this architecture. It should report and control the Rust supervisor-managed child processes through the supervisor's local control surface instead of controlling Scheduled Tasks. The existing `windows-task` adapter remains available for legacy script installs. The control bridge remains the panel-facing HTTP contract; the Rust supervisor remains the process owner.

## Installation and Runtime Layout

The zip layout is:

```text
mc-netprobe-client-windows-x64.zip
  mc-netprobe-tray.exe
  mc-netprobe-service.exe
  mc-netprobe-elevate.exe
  python\
  repo\
  templates\
    client.yaml
    client-app.yaml
  README-WINDOWS.md
```

The initialized runtime layout is:

```text
C:\ProgramData\mc-netprobe\client\
  app\
    mc-netprobe-tray.exe
    mc-netprobe-service.exe
    mc-netprobe-elevate.exe
    python\
    repo\
  config\
    agent\client.yaml
    client-app.yaml
  logs\
    agent.log
    control-bridge.log
    supervisor.log
  state\
    supervisor-status.json
```

The service points only at files under `C:\ProgramData\mc-netprobe\client`. After initialization, moving or deleting the original zip extraction directory must not break the service.

## First-Run Initialization

When `mc-netprobe-tray.exe` starts and detects that the runtime is not initialized, it opens a small Tauri initialization window. The wizard collects:

- Panel URL.
- Pair code.
- Node name.
- Listen port, default `9870`.
- Advertise URL, either auto-derived or manually entered.
- Advanced option to expose the control bridge beyond localhost, disabled by default.

After confirmation, the tray launches `mc-netprobe-elevate.exe` through UAC. The elevated helper:

1. Creates `C:\ProgramData\mc-netprobe\client`.
2. Copies the zip runtime into `app\`.
3. Writes `config\agent\client.yaml`.
4. Writes `config\client-app.yaml`.
5. Registers `mc-netprobe-client` as a Windows Service with Automatic startup.
6. Creates the Windows Firewall rule for the agent listen port.
7. Optionally creates the control bridge firewall rule if the advanced option is enabled.
8. Starts the service.
9. Verifies the service health, local agent health, pairing, and heartbeat.

If initialization fails after partial work, the helper records enough state for retry and rollback. A failed initialization must not leave a misleading "healthy" tray state.

## Configuration

The primary agent config remains YAML and keeps the existing agent field names:

```yaml
panel_url: http://panel-host:8765
node_name: client-1
role: client
runtime_mode: native-windows
listen_host: 0.0.0.0
listen_port: 9870
advertise_url: http://client-host-or-tailnet-ip:9870
control_port: 9871
control_url: http://127.0.0.1:9871
node_token: null
pair_code: null
protocol_version: "1"
agent_version: "1"
```

`client-app.yaml` stores Windows-client-specific settings such as service name, log paths, firewall rule names, restart policy, and whether the control bridge is externally exposed. These settings are internal to the Windows client and do not change the panel-agent contract.

The tray provides both:

- Guided reconfiguration for common fields.
- `Open Config File` for advanced direct YAML edits.

After editing YAML, users can restart the service from the tray.

## Firewall Policy

Default firewall behavior:

- Create an inbound allow rule for the agent listen port.
- Bind the control bridge to `127.0.0.1` and do not create an external inbound rule.

Advanced behavior:

- If the user explicitly enables remote control bridge access, bind the bridge to the configured host and create a separate inbound rule for the control bridge port.
- The UI must label this as a higher-risk option because the control bridge can start, stop, restart, and tail logs for the local agent runtime.

Firewall rule names should be stable and scoped:

- `mc-netprobe-client-agent-9870`
- `mc-netprobe-client-control-bridge-9871`

## Tray UX

The tray app is a user-session control surface, not the background owner.

Menu items:

- `Status: <state>` where state is `Uninitialized`, `Starting`, `Running`, `Degraded`, `Stopped`, or `Error`.
- `Initialize / Reconfigure`.
- `Start Service`.
- `Stop Service`.
- `Restart Service`.
- `Open Config File`.
- `Open Logs Folder`.
- `Open Panel`.
- `Copy Diagnostics`.
- `Quit Tray`.

The tray should auto-start at user login so users can see status and access shortcuts. The service itself must start at boot independently of the tray.

## Service Supervisor Behavior

The supervisor is responsible for:

- Starting the agent and control bridge without console windows.
- Redirecting stdout/stderr to log files.
- Monitoring child process exits.
- Applying bounded restart policy.
- Publishing status over a Named Pipe.
- Writing `state\supervisor-status.json` for diagnostics.
- Redacting secrets in diagnostics.

Restart policy:

- Restart a crashed child process up to 5 times in 10 minutes.
- If the limit is exceeded, mark the runtime as `Degraded` or `Error` and stop restarting that child until manual restart.
- Do not spin indefinitely if Python, config, or port binding is broken.

## Named Pipe IPC

The tray communicates with the service through a Windows Named Pipe, for example:

```text
\\.\pipe\mc-netprobe-client-service
```

Supported commands:

- `status`
- `start`
- `stop`
- `restart`
- `open_diagnostics_snapshot`
- `validate_config`

The pipe ACL should allow:

- `SYSTEM`
- local `Administrators`
- the current interactive user who initialized the client

The IPC payload should be versioned JSON. The first version can be simple request/response messages with command name, request id, and structured result or error.

## Security

- Pair codes are used only during initialization or explicit re-pairing.
- After successful pairing, the agent config stores `node_token` and clears `pair_code`.
- `Copy Diagnostics` must redact `node_token`, `pair_code`, passwords, and authorization headers.
- The service runs as `LocalSystem` by default unless implementation proves a lower-privilege service account is practical.
- Control bridge external exposure is disabled by default.
- Named Pipe access is restricted to local trusted principals.
- All privileged operations are centralized in the elevated helper or service, not in the normal tray process.

## Error Handling

The user-facing error model should be operational, not stack-trace-first.

Required errors:

- UAC denied: explain that initialization requires administrator approval and allow retry.
- Port occupied: show the occupied port and allow choosing another port.
- Firewall rule failed: show the rule name, command category, and log location.
- Service install failed: show service name and supervisor log path.
- Agent failed to start: show agent log path.
- Pair failed: show panel URL, node name, and safe error detail; keep draft config.
- Heartbeat failed: show last error and keep service running.
- Child process crash loop: mark degraded and expose `Copy Diagnostics`.

## Packaging and Build

The build produces a zip named:

```text
mc-netprobe-client-windows-x64-<version>-<build-ref>.zip
```

Build inputs:

- Tauri/Rust tray app.
- Rust Windows Service supervisor.
- Elevated helper executable.
- Embedded Python runtime for x64 Windows.
- Python dependencies from `requirements.txt`.
- Repository Python modules required by `agents.service`, `controller.control_bridge`, and probes.
- Config templates and README.

The first version can be built manually or in CI, but the output must be reproducible enough for staging validation.

## Testing and Acceptance

Automated test coverage:

- Rust unit tests for path resolution, command construction, redaction, status transitions, and IPC message parsing.
- Static packaging tests for required zip entries.
- Python contract tests to ensure existing agent, heartbeat, direct job, result lookup, and control bridge contracts still pass.
- Tests for Windows config templates and firewall/service command generation.

Manual or Windows-runner validation:

1. On Windows 10 x64 and Windows 11 x64, unzip and start `mc-netprobe-tray.exe`.
2. Complete initialization with UAC.
3. Verify `mc-netprobe-client` service exists and startup type is Automatic.
4. Reboot before user login and verify the service starts.
5. Log in and verify tray status shows running.
6. Verify no command-line windows appear.
7. Verify Windows Firewall allows the agent listen port.
8. Pair with staging panel and verify heartbeat online.
9. Run a panel-dispatched job and verify result completion.
10. Use tray shortcuts to open config, logs, and panel.
11. Restart service from tray and verify recovery.
12. Confirm `Copy Diagnostics` redacts secrets.

Panel staging acceptance:

- The Windows client appears as `role=client`, `runtime_mode=native-windows`.
- Pair, heartbeat, job dispatch, result lookup, and runtime status work with the existing panel API.
- No backend business JSON API changes are required.

## Branch and Development Environment

Development starts from `origin/feat/saas-webui-rewrite` after `git fetch`.

The Linux dev server worktree is:

```text
/root/server/Frp-network-evaluation-windows-client
```

The branch is:

```text
codex/windows-client-tray-service
```

Implementation should happen on this branch and not in the production worktree or staging debug worktree.

## Open Decisions Resolved

- Distribution: portable zip.
- Privilege model: one-time elevated initialization.
- Tray technology: Tauri/Rust.
- Python runtime: bundled.
- Background model: Windows Service.
- Runtime location: `C:\ProgramData\mc-netprobe\client`.
- Initialization: wizard and YAML advanced editing.
- Firewall policy: default agent-only, advanced control bridge exposure.
- Service model: single Rust supervisor service.
- IPC: Windows Named Pipe.
- Supported Windows versions: Windows 10/11 x64.
