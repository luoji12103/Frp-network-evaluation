# Windows Client Tray Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Windows 10/11 x64 client package with a Tauri tray, Rust Windows Service supervisor, embedded Python agent runtime, elevated initialization, firewall setup, and config/log shortcuts.

**Architecture:** Add a focused Windows client workspace under `clients/windows/`. Shared Rust core code owns paths, config, command construction, diagnostics redaction, IPC protocol, service/firewall command generation, and package layout checks. The Windows Service owns the agent/control-bridge child processes; the tray and Python control bridge talk to the service through a versioned local control command surface.

**Tech Stack:** Rust workspace, Tauri v2, Windows Service APIs, Windows Named Pipes, PowerShell packaging scripts, embedded CPython x64, existing Python `agents.service` and `controller.control_bridge`, pytest contract tests.

---

## Scope Check

This plan implements the accepted Windows client design as one product, but it keeps each subsystem independently testable:

- Rust shared core and protocol.
- Python control bridge adapter compatibility.
- Rust service supervisor.
- Elevated installer/helper.
- Tauri tray and initialization UI.
- Packaging and validation.

No panel business JSON API changes are planned. Existing script-based Windows Scheduled Task installation remains available for compatibility.

## File Structure

Create these Windows-client-specific files:

- `clients/windows/Cargo.toml` - Rust workspace root for Windows client crates.
- `clients/windows/crates/client-core/Cargo.toml` - shared Rust library manifest.
- `clients/windows/crates/client-core/src/lib.rs` - module exports.
- `clients/windows/crates/client-core/src/paths.rs` - runtime path resolution.
- `clients/windows/crates/client-core/src/config.rs` - `client-app.yaml` and agent config models.
- `clients/windows/crates/client-core/src/process_spec.rs` - Python agent/control bridge command construction.
- `clients/windows/crates/client-core/src/diagnostics.rs` - secret redaction and diagnostics payload.
- `clients/windows/crates/client-core/src/ipc.rs` - versioned IPC request/response types.
- `clients/windows/crates/client-core/src/service_plan.rs` - Windows service command model.
- `clients/windows/crates/client-core/src/firewall.rs` - firewall rule command model.
- `clients/windows/crates/mc-netprobe-service/Cargo.toml` - service supervisor executable manifest.
- `clients/windows/crates/mc-netprobe-service/src/main.rs` - CLI and Windows service entrypoint.
- `clients/windows/crates/mc-netprobe-service/src/supervisor.rs` - child process supervision and bounded restart policy.
- `clients/windows/crates/mc-netprobe-service/src/control.rs` - Named Pipe server and CLI client.
- `clients/windows/crates/mc-netprobe-elevate/Cargo.toml` - elevated helper executable manifest.
- `clients/windows/crates/mc-netprobe-elevate/src/main.rs` - elevated initialize/install command.
- `clients/windows/apps/tray/src-tauri/Cargo.toml` - Tauri tray Rust manifest.
- `clients/windows/apps/tray/src-tauri/tauri.conf.json` - Tauri app config.
- `clients/windows/apps/tray/src-tauri/src/main.rs` - tray app entrypoint.
- `clients/windows/apps/tray/ui/index.html` - initialization window shell.
- `clients/windows/apps/tray/ui/app.js` - initialization UI behavior.
- `clients/windows/templates/client.yaml` - agent config template.
- `clients/windows/templates/client-app.yaml` - Windows client config template.
- `clients/windows/scripts/package-windows-client.ps1` - zip packaging script.
- `clients/windows/scripts/validate-windows-client.ps1` - Windows smoke validation script.
- `clients/windows/README-WINDOWS.md` - user-facing Windows instructions.

Modify these existing files:

- `.gitignore` - ignore Windows client build artifacts.
- `controller/control_bridge.py` - add `windows-service-supervisor` adapter.
- `tests/test_control_bridge.py` - keep existing bridge contract coverage.

Create these tests:

- `tests/test_windows_client_templates.py` - config template shape and command generation expectations.
- `tests/test_windows_service_supervisor_adapter.py` - Python adapter subprocess behavior.
- `tests/test_windows_packaging_scripts.py` - packaging script static checks.
- Rust unit tests inside `clients/windows/crates/client-core/src/*.rs`.
- Rust unit tests inside `clients/windows/crates/mc-netprobe-service/src/supervisor.rs`.

---

### Task 1: Create Windows Rust Workspace and Core Path Model

**Files:**
- Create: `clients/windows/Cargo.toml`
- Create: `clients/windows/crates/client-core/Cargo.toml`
- Create: `clients/windows/crates/client-core/src/lib.rs`
- Create: `clients/windows/crates/client-core/src/paths.rs`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing path tests**

Create `clients/windows/crates/client-core/src/paths.rs` with this test-only skeleton first:

```rust
#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn program_data_layout_uses_stable_runtime_root() {
        let layout = ClientPaths::from_root(PathBuf::from(r"C:\ProgramData\mc-netprobe\client"));
        assert_eq!(layout.app_dir, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\app"));
        assert_eq!(layout.agent_config, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\config\agent\client.yaml"));
        assert_eq!(layout.client_config, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\config\client-app.yaml"));
        assert_eq!(layout.agent_log, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\logs\agent.log"));
        assert_eq!(layout.control_bridge_log, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\logs\control-bridge.log"));
        assert_eq!(layout.supervisor_log, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\logs\supervisor.log"));
        assert_eq!(layout.status_file, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\state\supervisor-status.json"));
    }

    #[test]
    fn default_runtime_root_is_program_data_client_dir() {
        let root = default_runtime_root();
        assert!(root.ends_with(r"mc-netprobe\client"));
    }
}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-client-core paths::tests::program_data_layout_uses_stable_runtime_root
```

Expected: fail because the workspace and `ClientPaths` do not exist.

- [ ] **Step 3: Add the Rust workspace manifests**

Create `clients/windows/Cargo.toml`:

```toml
[workspace]
members = ["crates/*"]
resolver = "2"

[workspace.package]
edition = "2021"
license = "MIT"
version = "0.1.0"

[workspace.dependencies]
anyhow = "1"
camino = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
serde_yaml = "0.9"
thiserror = "2"
time = { version = "0.3", features = ["formatting", "macros"] }
tracing = "0.1"
```

Create `clients/windows/crates/client-core/Cargo.toml`:

```toml
[package]
name = "mc-netprobe-client-core"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
anyhow.workspace = true
camino.workspace = true
serde.workspace = true
serde_json.workspace = true
serde_yaml.workspace = true
thiserror.workspace = true
time.workspace = true
```

Create `clients/windows/crates/client-core/src/lib.rs`:

```rust
pub mod paths;
```

- [ ] **Step 4: Implement the path model**

Replace `clients/windows/crates/client-core/src/paths.rs` with:

```rust
use std::path::PathBuf;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ClientPaths {
    pub root: PathBuf,
    pub app_dir: PathBuf,
    pub repo_dir: PathBuf,
    pub python_exe: PathBuf,
    pub agent_config: PathBuf,
    pub client_config: PathBuf,
    pub logs_dir: PathBuf,
    pub agent_log: PathBuf,
    pub control_bridge_log: PathBuf,
    pub supervisor_log: PathBuf,
    pub state_dir: PathBuf,
    pub status_file: PathBuf,
}

impl ClientPaths {
    pub fn from_root(root: PathBuf) -> Self {
        let app_dir = root.join("app");
        let logs_dir = root.join("logs");
        let state_dir = root.join("state");
        Self {
            repo_dir: app_dir.join("repo"),
            python_exe: app_dir.join("python").join("python.exe"),
            agent_config: root.join("config").join("agent").join("client.yaml"),
            client_config: root.join("config").join("client-app.yaml"),
            agent_log: logs_dir.join("agent.log"),
            control_bridge_log: logs_dir.join("control-bridge.log"),
            supervisor_log: logs_dir.join("supervisor.log"),
            status_file: state_dir.join("supervisor-status.json"),
            app_dir,
            logs_dir,
            state_dir,
            root,
        }
    }
}

pub fn default_runtime_root() -> PathBuf {
    std::env::var_os("PROGRAMDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(r"C:\ProgramData"))
        .join("mc-netprobe")
        .join("client")
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn program_data_layout_uses_stable_runtime_root() {
        let layout = ClientPaths::from_root(PathBuf::from(r"C:\ProgramData\mc-netprobe\client"));
        assert_eq!(layout.app_dir, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\app"));
        assert_eq!(layout.agent_config, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\config\agent\client.yaml"));
        assert_eq!(layout.client_config, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\config\client-app.yaml"));
        assert_eq!(layout.agent_log, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\logs\agent.log"));
        assert_eq!(layout.control_bridge_log, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\logs\control-bridge.log"));
        assert_eq!(layout.supervisor_log, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\logs\supervisor.log"));
        assert_eq!(layout.status_file, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\state\supervisor-status.json"));
    }

    #[test]
    fn default_runtime_root_is_program_data_client_dir() {
        let root = default_runtime_root();
        assert!(root.ends_with(r"mc-netprobe\client"));
    }
}
```

- [ ] **Step 5: Update ignored build artifacts**

Append to `.gitignore`:

```gitignore
clients/windows/target/
clients/windows/dist/
clients/windows/.tauri/
clients/windows/apps/tray/src-tauri/target/
```

- [ ] **Step 6: Run the tests**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-client-core
```

Expected: all `mc-netprobe-client-core` tests pass.

- [ ] **Step 7: Commit**

```bash
git add .gitignore clients/windows/Cargo.toml clients/windows/crates/client-core
git commit -m "feat(windows): add client core workspace"
```

---

### Task 2: Add Config Models, Templates, and Python Command Construction

**Files:**
- Create: `clients/windows/crates/client-core/src/config.rs`
- Create: `clients/windows/crates/client-core/src/process_spec.rs`
- Create: `clients/windows/templates/client.yaml`
- Create: `clients/windows/templates/client-app.yaml`
- Modify: `clients/windows/crates/client-core/src/lib.rs`
- Test: `tests/test_windows_client_templates.py`

- [ ] **Step 1: Write Python template tests**

Create `tests/test_windows_client_templates.py`:

```python
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CLIENT_TEMPLATE = ROOT / "clients" / "windows" / "templates" / "client.yaml"
APP_TEMPLATE = ROOT / "clients" / "windows" / "templates" / "client-app.yaml"


def test_windows_agent_template_uses_existing_agent_contract_fields() -> None:
    payload = yaml.safe_load(CLIENT_TEMPLATE.read_text(encoding="utf-8"))
    assert payload["role"] == "client"
    assert payload["runtime_mode"] == "native-windows"
    assert payload["listen_host"] == "0.0.0.0"
    assert payload["listen_port"] == 9870
    assert payload["control_port"] == 9871
    assert payload["protocol_version"] == "1"
    assert "node_token" in payload
    assert "pair_code" in payload


def test_windows_client_app_template_scopes_firewall_and_service_names() -> None:
    payload = yaml.safe_load(APP_TEMPLATE.read_text(encoding="utf-8"))
    assert payload["service_name"] == "mc-netprobe-client"
    assert payload["pipe_name"] == r"\\.\pipe\mc-netprobe-client-service"
    assert payload["firewall"]["agent_rule_prefix"] == "mc-netprobe-client-agent"
    assert payload["firewall"]["control_bridge_rule_prefix"] == "mc-netprobe-client-control-bridge"
    assert payload["control_bridge"]["expose_remote"] is False
```

- [ ] **Step 2: Run template tests to verify they fail**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
.venv/bin/python -m pytest tests/test_windows_client_templates.py -q
```

Expected: fail because templates do not exist.

- [ ] **Step 3: Add templates**

Create `clients/windows/templates/client.yaml`:

```yaml
panel_url: http://panel-host:8765
node_name: client-1
role: client
runtime_mode: native-windows
listen_host: 0.0.0.0
listen_port: 9870
advertise_url: null
control_port: 9871
control_url: http://127.0.0.1:9871
node_token: null
pair_code: null
protocol_version: "1"
agent_version: "1"
platform_name_override: null
```

Create `clients/windows/templates/client-app.yaml`:

```yaml
service_name: mc-netprobe-client
display_name: mc-netprobe Client
pipe_name: "\\\\.\\pipe\\mc-netprobe-client-service"
restart_policy:
  max_restarts: 5
  window_seconds: 600
firewall:
  agent_rule_prefix: mc-netprobe-client-agent
  control_bridge_rule_prefix: mc-netprobe-client-control-bridge
control_bridge:
  host: 127.0.0.1
  port: 9871
  expose_remote: false
paths:
  runtime_root: "C:\\ProgramData\\mc-netprobe\\client"
  agent_config: "C:\\ProgramData\\mc-netprobe\\client\\config\\agent\\client.yaml"
  logs_dir: "C:\\ProgramData\\mc-netprobe\\client\\logs"
```

- [ ] **Step 4: Add Rust config and process spec tests**

Create `clients/windows/crates/client-core/src/config.rs`:

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct FirewallConfig {
    pub agent_rule_prefix: String,
    pub control_bridge_rule_prefix: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ControlBridgeConfig {
    pub host: String,
    pub port: u16,
    pub expose_remote: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RestartPolicy {
    pub max_restarts: u32,
    pub window_seconds: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct WindowsClientConfig {
    pub service_name: String,
    pub display_name: String,
    pub pipe_name: String,
    pub restart_policy: RestartPolicy,
    pub firewall: FirewallConfig,
    pub control_bridge: ControlBridgeConfig,
}

impl WindowsClientConfig {
    pub fn from_yaml(text: &str) -> anyhow::Result<Self> {
        Ok(serde_yaml::from_str(text)?)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_client_app_yaml() {
        let config = WindowsClientConfig::from_yaml(
            r#"
service_name: mc-netprobe-client
display_name: mc-netprobe Client
pipe_name: "\\\\.\\pipe\\mc-netprobe-client-service"
restart_policy:
  max_restarts: 5
  window_seconds: 600
firewall:
  agent_rule_prefix: mc-netprobe-client-agent
  control_bridge_rule_prefix: mc-netprobe-client-control-bridge
control_bridge:
  host: 127.0.0.1
  port: 9871
  expose_remote: false
"#,
        )
        .expect("config parses");
        assert_eq!(config.service_name, "mc-netprobe-client");
        assert_eq!(config.restart_policy.max_restarts, 5);
        assert!(!config.control_bridge.expose_remote);
    }
}
```

Create `clients/windows/crates/client-core/src/process_spec.rs`:

```rust
use std::path::PathBuf;

use crate::paths::ClientPaths;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ProcessSpec {
    pub program: PathBuf,
    pub args: Vec<String>,
    pub working_dir: PathBuf,
    pub log_path: PathBuf,
}

pub fn agent_process(paths: &ClientPaths) -> ProcessSpec {
    ProcessSpec {
        program: paths.python_exe.clone(),
        args: vec![
            "-m".into(),
            "agents.service".into(),
            "--config".into(),
            paths.agent_config.to_string_lossy().to_string(),
        ],
        working_dir: paths.repo_dir.clone(),
        log_path: paths.agent_log.clone(),
    }
}

pub fn control_bridge_process(paths: &ClientPaths, host: &str, port: u16) -> ProcessSpec {
    ProcessSpec {
        program: paths.python_exe.clone(),
        args: vec![
            "-m".into(),
            "controller.control_bridge".into(),
            "--mode".into(),
            "node".into(),
            "--adapter".into(),
            "windows-service-supervisor".into(),
            "--host".into(),
            host.into(),
            "--port".into(),
            port.to_string(),
            "--agent-config".into(),
            paths.agent_config.to_string_lossy().to_string(),
            "--log-path".into(),
            paths.control_bridge_log.to_string_lossy().to_string(),
        ],
        working_dir: paths.repo_dir.clone(),
        log_path: paths.control_bridge_log.clone(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::paths::ClientPaths;
    use std::path::PathBuf;

    #[test]
    fn builds_agent_command_from_runtime_layout() {
        let paths = ClientPaths::from_root(PathBuf::from(r"C:\ProgramData\mc-netprobe\client"));
        let spec = agent_process(&paths);
        assert!(spec.program.ends_with(r"app\python\python.exe"));
        assert_eq!(spec.args[0..2], ["-m", "agents.service"]);
        assert!(spec.args.contains(&"--config".to_string()));
        assert_eq!(spec.working_dir, PathBuf::from(r"C:\ProgramData\mc-netprobe\client\app\repo"));
    }

    #[test]
    fn builds_control_bridge_command_with_service_supervisor_adapter() {
        let paths = ClientPaths::from_root(PathBuf::from(r"C:\ProgramData\mc-netprobe\client"));
        let spec = control_bridge_process(&paths, "127.0.0.1", 9871);
        assert_eq!(spec.args[0..2], ["-m", "controller.control_bridge"]);
        assert!(spec.args.contains(&"windows-service-supervisor".to_string()));
        assert!(spec.args.contains(&"9871".to_string()));
    }
}
```

Modify `clients/windows/crates/client-core/src/lib.rs`:

```rust
pub mod config;
pub mod paths;
pub mod process_spec;
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-client-core
.venv/bin/python -m pytest tests/test_windows_client_templates.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add clients/windows/crates/client-core clients/windows/templates tests/test_windows_client_templates.py
git commit -m "feat(windows): define client config and process specs"
```

---

### Task 3: Add Redaction, Diagnostics, and IPC Protocol Types

**Files:**
- Create: `clients/windows/crates/client-core/src/diagnostics.rs`
- Create: `clients/windows/crates/client-core/src/ipc.rs`
- Modify: `clients/windows/crates/client-core/src/lib.rs`

- [ ] **Step 1: Add diagnostics tests and implementation**

Create `clients/windows/crates/client-core/src/diagnostics.rs`:

```rust
use serde::{Deserialize, Serialize};

const SECRET_KEYS: [&str; 4] = ["node_token", "pair_code", "password", "authorization"];

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct DiagnosticsSnapshot {
    pub status: String,
    pub service_name: String,
    pub agent_log_tail: Vec<String>,
    pub control_bridge_log_tail: Vec<String>,
    pub supervisor_log_tail: Vec<String>,
    pub redacted_config: serde_json::Value,
}

pub fn redact_value(value: serde_json::Value) -> serde_json::Value {
    match value {
        serde_json::Value::Object(map) => serde_json::Value::Object(
            map.into_iter()
                .map(|(key, value)| {
                    let redacted = if SECRET_KEYS.iter().any(|secret| key.to_ascii_lowercase().contains(secret)) {
                        serde_json::Value::String("<redacted>".into())
                    } else {
                        redact_value(value)
                    };
                    (key, redacted)
                })
                .collect(),
        ),
        serde_json::Value::Array(items) => serde_json::Value::Array(items.into_iter().map(redact_value).collect()),
        other => other,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn redacts_nested_tokens_and_pair_codes() {
        let input = json!({
            "node_token": "secret",
            "nested": {
                "pair_code": "pair",
                "safe": "visible"
            },
            "items": [{"authorization": "Bearer abc"}]
        });
        let redacted = redact_value(input);
        assert_eq!(redacted["node_token"], "<redacted>");
        assert_eq!(redacted["nested"]["pair_code"], "<redacted>");
        assert_eq!(redacted["nested"]["safe"], "visible");
        assert_eq!(redacted["items"][0]["authorization"], "<redacted>");
    }
}
```

- [ ] **Step 2: Add IPC protocol tests and implementation**

Create `clients/windows/crates/client-core/src/ipc.rs`:

```rust
use serde::{Deserialize, Serialize};

pub const IPC_VERSION: u16 = 1;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ServiceCommand {
    Status,
    Start,
    Stop,
    Restart,
    ValidateConfig,
    OpenDiagnosticsSnapshot,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ServiceRequest {
    pub version: u16,
    pub request_id: String,
    pub command: ServiceCommand,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ServiceStatus {
    pub state: String,
    pub agent_state: String,
    pub control_bridge_state: String,
    pub last_error: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ServiceResponse {
    pub version: u16,
    pub request_id: String,
    pub ok: bool,
    pub status: Option<ServiceStatus>,
    pub error: Option<String>,
}

impl ServiceRequest {
    pub fn status(request_id: impl Into<String>) -> Self {
        Self { version: IPC_VERSION, request_id: request_id.into(), command: ServiceCommand::Status }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn serializes_status_request_as_versioned_json() {
        let request = ServiceRequest::status("req-1");
        let json = serde_json::to_string(&request).expect("json");
        assert!(json.contains("\"version\":1"));
        assert!(json.contains("\"command\":\"status\""));
        let decoded: ServiceRequest = serde_json::from_str(&json).expect("decode");
        assert_eq!(decoded, request);
    }
}
```

- [ ] **Step 3: Export new modules**

Modify `clients/windows/crates/client-core/src/lib.rs`:

```rust
pub mod config;
pub mod diagnostics;
pub mod ipc;
pub mod paths;
pub mod process_spec;
```

- [ ] **Step 4: Run core tests**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-client-core
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add clients/windows/crates/client-core
git commit -m "feat(windows): add diagnostics and ipc protocol"
```

---

### Task 4: Add Windows Service and Firewall Command Planning

**Files:**
- Create: `clients/windows/crates/client-core/src/service_plan.rs`
- Create: `clients/windows/crates/client-core/src/firewall.rs`
- Modify: `clients/windows/crates/client-core/src/lib.rs`

- [ ] **Step 1: Add service command planning implementation**

Create `clients/windows/crates/client-core/src/service_plan.rs`:

```rust
use std::path::Path;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ServiceInstallPlan {
    pub service_name: String,
    pub display_name: String,
    pub executable: String,
}

impl ServiceInstallPlan {
    pub fn sc_create_args(&self) -> Vec<String> {
        vec![
            "create".into(),
            self.service_name.clone(),
            format!("binPath= {}", self.executable),
            "start= auto".into(),
            format!("DisplayName= {}", self.display_name),
        ]
    }
}

pub fn service_executable(runtime_root: &Path) -> String {
    runtime_root.join("app").join("mc-netprobe-service.exe").to_string_lossy().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn service_install_plan_uses_automatic_start() {
        let plan = ServiceInstallPlan {
            service_name: "mc-netprobe-client".into(),
            display_name: "mc-netprobe Client".into(),
            executable: service_executable(&PathBuf::from(r"C:\ProgramData\mc-netprobe\client")),
        };
        let args = plan.sc_create_args();
        assert!(args.contains(&"mc-netprobe-client".to_string()));
        assert!(args.contains(&"start= auto".to_string()));
        assert!(args.iter().any(|arg| arg.contains("mc-netprobe-service.exe")));
    }
}
```

- [ ] **Step 2: Add firewall command planning implementation**

Create `clients/windows/crates/client-core/src/firewall.rs`:

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FirewallRulePlan {
    pub name: String,
    pub port: u16,
    pub enabled: bool,
}

impl FirewallRulePlan {
    pub fn netsh_args(&self) -> Vec<String> {
        vec![
            "advfirewall".into(),
            "firewall".into(),
            "add".into(),
            "rule".into(),
            format!("name={}", self.name),
            "dir=in".into(),
            "action=allow".into(),
            "protocol=TCP".into(),
            format!("localport={}", self.port),
        ]
    }
}

pub fn agent_rule(prefix: &str, port: u16) -> FirewallRulePlan {
    FirewallRulePlan { name: format!("{prefix}-{port}"), port, enabled: true }
}

pub fn control_bridge_rule(prefix: &str, port: u16, expose_remote: bool) -> FirewallRulePlan {
    FirewallRulePlan { name: format!("{prefix}-{port}"), port, enabled: expose_remote }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn agent_firewall_rule_is_enabled_and_scoped_to_port() {
        let rule = agent_rule("mc-netprobe-client-agent", 9870);
        assert_eq!(rule.name, "mc-netprobe-client-agent-9870");
        assert!(rule.enabled);
        assert!(rule.netsh_args().contains(&"localport=9870".to_string()));
    }

    #[test]
    fn control_bridge_rule_is_disabled_by_default() {
        let rule = control_bridge_rule("mc-netprobe-client-control-bridge", 9871, false);
        assert_eq!(rule.name, "mc-netprobe-client-control-bridge-9871");
        assert!(!rule.enabled);
    }
}
```

- [ ] **Step 3: Export modules**

Modify `clients/windows/crates/client-core/src/lib.rs`:

```rust
pub mod config;
pub mod diagnostics;
pub mod firewall;
pub mod ipc;
pub mod paths;
pub mod process_spec;
pub mod service_plan;
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-client-core
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add clients/windows/crates/client-core
git commit -m "feat(windows): plan service and firewall setup"
```

---

### Task 5: Add Python Control Bridge Adapter for Supervisor-Controlled Windows Runtime

**Files:**
- Modify: `controller/control_bridge.py`
- Create: `tests/test_windows_service_supervisor_adapter.py`

- [ ] **Step 1: Write the failing adapter tests**

Create `tests/test_windows_service_supervisor_adapter.py`:

```python
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from controller.control_bridge import BridgeActionError, WindowsServiceSupervisorAdapter


class FakeCompleted:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_windows_service_supervisor_adapter_reads_status(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], capture_output: bool, text: bool, check: bool) -> FakeCompleted:
        calls.append(command)
        return FakeCompleted(
            json.dumps(
                {
                    "ok": True,
                    "status": {
                        "state": "running",
                        "agent_state": "running",
                        "control_bridge_state": "running",
                        "last_error": None,
                    },
                }
            )
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = WindowsServiceSupervisorAdapter(
        control_exe=tmp_path / "mc-netprobe-service.exe",
        log_path=tmp_path / "control-bridge.log",
    )

    response = adapter.runtime()

    assert response.state == "running"
    assert response.supervisor.process_state == "running"
    assert calls[0][1:] == ["control", "status"]


def test_windows_service_supervisor_adapter_surfaces_control_errors(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command: list[str], capture_output: bool, text: bool, check: bool) -> FakeCompleted:
        return FakeCompleted("", "pipe unavailable", 1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = WindowsServiceSupervisorAdapter(
        control_exe=tmp_path / "mc-netprobe-service.exe",
        log_path=tmp_path / "control-bridge.log",
    )

    with pytest.raises(BridgeActionError) as error:
        adapter.runtime()

    assert error.value.code == "windows_supervisor_control_failed"
    assert "pipe unavailable" in error.value.message
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
.venv/bin/python -m pytest tests/test_windows_service_supervisor_adapter.py -q
```

Expected: fail because `WindowsServiceSupervisorAdapter` does not exist.

- [ ] **Step 3: Implement the adapter**

Modify `controller/control_bridge.py` after `WindowsTaskAdapter`:

```python
class WindowsServiceSupervisorAdapter(ControlAdapter):
    """Manage the Rust Windows Service supervisor through its local control CLI."""

    def __init__(self, control_exe: str | Path, log_path: str | Path) -> None:
        self.control_exe = str(Path(control_exe).expanduser())
        self.log_path = str(Path(log_path).expanduser())

    def runtime(self) -> BridgeActionResponse:
        payload = self._control("status")
        status = payload.get("status") or {}
        state = str(status.get("state") or "unknown").lower()
        process_state = "running" if state == "running" else "stopped"
        checked_at = now_iso()
        return BridgeActionResponse(
            state=process_state,
            human_summary=f"Windows service supervisor is {state}",
            runtime=RuntimeSummary(state=process_state, checked_at=checked_at, details=status),
            supervisor=SupervisorSummary(
                control_available=True,
                supervisor_state=state,
                process_state=process_state,
                log_location=self.log_path,
                checked_at=checked_at,
            ),
            log_location=self.log_path,
            raw_runtime=payload,
        )

    def start(self) -> BridgeActionResponse:
        self._control("start")
        return self.runtime()

    def stop(self) -> BridgeActionResponse:
        self._control("stop")
        return self.runtime()

    def restart(self) -> BridgeActionResponse:
        self._control("restart")
        return self.runtime()

    def tail_log(self, tail_lines: int) -> BridgeActionResponse:
        lines = _tail_file(self.log_path, tail_lines)
        return BridgeActionResponse(
            state="ok",
            human_summary=f"Read {len(lines)} log lines from {self.log_path}",
            runtime=RuntimeSummary(state="running", checked_at=now_iso()),
            supervisor=SupervisorSummary(control_available=True, log_location=self.log_path, checked_at=now_iso()),
            log_location=self.log_path,
            log_excerpt=lines,
        )

    def _control(self, command: str) -> dict[str, Any]:
        completed = subprocess.run(
            [self.control_exe, "control", command],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise BridgeActionError(
                "windows_supervisor_control_failed",
                completed.stderr.strip() or completed.stdout.strip() or "Supervisor control command failed",
            )
        try:
            payload = json.loads(completed.stdout.strip() or "{}")
        except json.JSONDecodeError as exc:
            raise BridgeActionError("windows_supervisor_control_parse_failed", str(exc)) from exc
        if not bool(payload.get("ok", True)):
            raise BridgeActionError("windows_supervisor_control_rejected", str(payload.get("error") or "Supervisor rejected command"))
        return payload
```

Modify `build_parser()` adapter choices:

```python
parser.add_argument("--adapter", choices=["launchd", "windows-task", "windows-service-supervisor", "docker-container"], required=True)
parser.add_argument("--control-exe", default=None)
```

Modify `build_adapter()` before the docker fallback:

```python
if args.adapter == "windows-service-supervisor":
    control_exe = args.control_exe or str(Path("app") / "mc-netprobe-service.exe")
    return WindowsServiceSupervisorAdapter(control_exe=control_exe, log_path=args.log_path)
```

- [ ] **Step 4: Run Python tests**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
.venv/bin/python -m pytest tests/test_windows_service_supervisor_adapter.py tests/test_control_bridge.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add controller/control_bridge.py tests/test_windows_service_supervisor_adapter.py
git commit -m "feat(windows): add service supervisor control bridge adapter"
```

---

### Task 6: Implement Service Supervisor Core with Bounded Restart Policy

**Files:**
- Create: `clients/windows/crates/mc-netprobe-service/Cargo.toml`
- Create: `clients/windows/crates/mc-netprobe-service/src/main.rs`
- Create: `clients/windows/crates/mc-netprobe-service/src/supervisor.rs`
- Create: `clients/windows/crates/mc-netprobe-service/src/control.rs`

- [ ] **Step 1: Add service crate manifest**

Create `clients/windows/crates/mc-netprobe-service/Cargo.toml`:

```toml
[package]
name = "mc-netprobe-service"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
anyhow.workspace = true
mc-netprobe-client-core = { path = "../client-core" }
serde.workspace = true
serde_json.workspace = true
thiserror.workspace = true
time.workspace = true
tracing.workspace = true

[target.'cfg(windows)'.dependencies]
windows-service = "0.8"
windows = { version = "0.58", features = ["Win32_Foundation", "Win32_System_Console", "Win32_System_Pipes", "Win32_System_Threading"] }
```

- [ ] **Step 2: Add restart policy tests and implementation**

Create `clients/windows/crates/mc-netprobe-service/src/supervisor.rs`:

```rust
use std::collections::VecDeque;
use std::time::{Duration, Instant};

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ChildState {
    Stopped,
    Running,
    Degraded(String),
}

#[derive(Debug)]
pub struct RestartLimiter {
    max_restarts: usize,
    window: Duration,
    attempts: VecDeque<Instant>,
}

impl RestartLimiter {
    pub fn new(max_restarts: usize, window: Duration) -> Self {
        Self { max_restarts, window, attempts: VecDeque::new() }
    }

    pub fn record_and_check(&mut self, now: Instant) -> bool {
        while let Some(front) = self.attempts.front().copied() {
            if now.duration_since(front) > self.window {
                self.attempts.pop_front();
            } else {
                break;
            }
        }
        if self.attempts.len() >= self.max_restarts {
            return false;
        }
        self.attempts.push_back(now);
        true
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SupervisorStatus {
    pub state: String,
    pub agent_state: String,
    pub control_bridge_state: String,
    pub last_error: Option<String>,
}

impl SupervisorStatus {
    pub fn running() -> Self {
        Self {
            state: "running".into(),
            agent_state: "running".into(),
            control_bridge_state: "running".into(),
            last_error: None,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn restart_limiter_allows_five_restarts_in_window_then_blocks() {
        let mut limiter = RestartLimiter::new(5, Duration::from_secs(600));
        let now = Instant::now();
        for offset in 0..5 {
            assert!(limiter.record_and_check(now + Duration::from_secs(offset)));
        }
        assert!(!limiter.record_and_check(now + Duration::from_secs(6)));
    }

    #[test]
    fn restart_limiter_recovers_after_window() {
        let mut limiter = RestartLimiter::new(1, Duration::from_secs(10));
        let now = Instant::now();
        assert!(limiter.record_and_check(now));
        assert!(!limiter.record_and_check(now + Duration::from_secs(1)));
        assert!(limiter.record_and_check(now + Duration::from_secs(11)));
    }
}
```

- [ ] **Step 3: Add control CLI response skeleton**

Create `clients/windows/crates/mc-netprobe-service/src/control.rs`:

```rust
use mc_netprobe_client_core::ipc::{ServiceResponse, ServiceStatus, IPC_VERSION};

pub fn offline_response(request_id: impl Into<String>, error: impl Into<String>) -> ServiceResponse {
    ServiceResponse {
        version: IPC_VERSION,
        request_id: request_id.into(),
        ok: false,
        status: None,
        error: Some(error.into()),
    }
}

pub fn status_response(request_id: impl Into<String>, status: ServiceStatus) -> ServiceResponse {
    ServiceResponse {
        version: IPC_VERSION,
        request_id: request_id.into(),
        ok: true,
        status: Some(status),
        error: None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn status_response_is_json_serializable() {
        let response = status_response(
            "req-1",
            ServiceStatus {
                state: "running".into(),
                agent_state: "running".into(),
                control_bridge_state: "running".into(),
                last_error: None,
            },
        );
        let json = serde_json::to_string(&response).expect("json");
        assert!(json.contains("\"ok\":true"));
        assert!(json.contains("\"state\":\"running\""));
    }
}
```

- [ ] **Step 4: Add service binary CLI**

Create `clients/windows/crates/mc-netprobe-service/src/main.rs`:

```rust
mod control;
mod supervisor;

use anyhow::Result;
use mc_netprobe_client_core::ipc::ServiceStatus;

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    if args.get(1).map(String::as_str) == Some("control") {
        let command = args.get(2).map(String::as_str).unwrap_or("status");
        let response = match command {
            "status" => control::status_response(
                "cli",
                ServiceStatus {
                    state: "stopped".into(),
                    agent_state: "unknown".into(),
                    control_bridge_state: "unknown".into(),
                    last_error: Some("service control pipe is not connected in this build step".into()),
                },
            ),
            "start" | "stop" | "restart" => control::offline_response("cli", format!("{command} requires the Windows service runtime")),
            other => control::offline_response("cli", format!("unsupported command: {other}")),
        };
        println!("{}", serde_json::to_string(&response)?);
        return Ok(());
    }
    #[cfg(windows)]
    {
        println!("mc-netprobe Windows service entrypoint");
    }
    #[cfg(not(windows))]
    {
        println!("mc-netprobe service can only run as a Windows Service on Windows");
    }
    Ok(())
}
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-service
```

Expected: all tests pass on Linux. This task adds the cross-platform supervisor core; Task 11 adds the Windows-only service runtime behind `#[cfg(windows)]`.

- [ ] **Step 6: Commit**

```bash
git add clients/windows/crates/mc-netprobe-service
git commit -m "feat(windows): add service supervisor core"
```

---

### Task 7: Add Elevated Helper for Runtime Copy, Service Install, and Firewall Plans

**Files:**
- Create: `clients/windows/crates/mc-netprobe-elevate/Cargo.toml`
- Create: `clients/windows/crates/mc-netprobe-elevate/src/main.rs`
- Test: core tests from Task 4

- [ ] **Step 1: Add elevated helper manifest**

Create `clients/windows/crates/mc-netprobe-elevate/Cargo.toml`:

```toml
[package]
name = "mc-netprobe-elevate"
edition.workspace = true
license.workspace = true
version.workspace = true

[dependencies]
anyhow.workspace = true
mc-netprobe-client-core = { path = "../client-core" }
serde.workspace = true
serde_json.workspace = true
```

- [ ] **Step 2: Add helper CLI skeleton**

Create `clients/windows/crates/mc-netprobe-elevate/src/main.rs`:

```rust
use anyhow::{bail, Result};
use mc_netprobe_client_core::firewall::{agent_rule, control_bridge_rule};
use mc_netprobe_client_core::paths::ClientPaths;
use mc_netprobe_client_core::service_plan::{service_executable, ServiceInstallPlan};

fn main() -> Result<()> {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("plan-install") => print_install_plan(),
        Some("initialize") => {
            println!("initialization requires Windows elevated runtime");
            Ok(())
        }
        Some(other) => bail!("unsupported elevated command: {other}"),
        None => bail!("expected command: plan-install or initialize"),
    }
}

fn print_install_plan() -> Result<()> {
    let paths = ClientPaths::from_root(mc_netprobe_client_core::paths::default_runtime_root());
    let service = ServiceInstallPlan {
        service_name: "mc-netprobe-client".into(),
        display_name: "mc-netprobe Client".into(),
        executable: service_executable(&paths.root),
    };
    let agent_firewall = agent_rule("mc-netprobe-client-agent", 9870);
    let bridge_firewall = control_bridge_rule("mc-netprobe-client-control-bridge", 9871, false);
    let payload = serde_json::json!({
        "service_sc_args": service.sc_create_args(),
        "agent_firewall_args": agent_firewall.netsh_args(),
        "control_bridge_firewall_enabled": bridge_firewall.enabled,
    });
    println!("{}", serde_json::to_string_pretty(&payload)?);
    Ok(())
}
```

- [ ] **Step 3: Run helper command**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
cargo run --manifest-path clients/windows/Cargo.toml -p mc-netprobe-elevate -- plan-install
```

Expected: JSON output includes `service_sc_args`, `agent_firewall_args`, and `"control_bridge_firewall_enabled": false`.

- [ ] **Step 4: Commit**

```bash
git add clients/windows/crates/mc-netprobe-elevate
git commit -m "feat(windows): add elevated install helper shell"
```

---

### Task 8: Scaffold Tauri Tray App and Initialization UI

**Files:**
- Modify: `clients/windows/Cargo.toml`
- Create: `clients/windows/apps/tray/src-tauri/Cargo.toml`
- Create: `clients/windows/apps/tray/src-tauri/tauri.conf.json`
- Create: `clients/windows/apps/tray/src-tauri/src/main.rs`
- Create: `clients/windows/apps/tray/ui/index.html`
- Create: `clients/windows/apps/tray/ui/app.js`

- [ ] **Step 1: Add Tauri manifest**

Create `clients/windows/apps/tray/src-tauri/Cargo.toml`:

```toml
[package]
name = "mc-netprobe-tray"
edition.workspace = true
license.workspace = true
version.workspace = true

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
anyhow.workspace = true
mc-netprobe-client-core = { path = "../../../crates/client-core" }
serde.workspace = true
serde_json.workspace = true
tauri = { version = "2", features = ["tray-icon"] }
tauri-plugin-opener = "2"
```

- [ ] **Step 2: Add Tauri config**

Create `clients/windows/apps/tray/src-tauri/tauri.conf.json`:

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "mc-netprobe Client",
  "version": "0.1.0",
  "identifier": "com.mc-netprobe.client",
  "build": {
    "frontendDist": "../ui",
    "devUrl": null
  },
  "app": {
    "windows": [
      {
        "title": "mc-netprobe Client Setup",
        "width": 720,
        "height": 560,
        "visible": false
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": false,
    "targets": []
  }
}
```

- [ ] **Step 3: Add tray crate to the workspace**

Modify `clients/windows/Cargo.toml`:

```toml
[workspace]
members = [
  "crates/*",
  "apps/tray/src-tauri",
]
resolver = "2"
```

Keep the existing `[workspace.package]` and `[workspace.dependencies]` sections unchanged.

- [ ] **Step 4: Add tray Rust entrypoint**

Create `clients/windows/apps/tray/src-tauri/src/main.rs`:

```rust
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;

#[tauri::command]
fn service_status_label() -> String {
    "Uninitialized".to_string()
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![service_status_label])
        .setup(|app| {
            let initialize = MenuItem::with_id(app, "initialize", "Initialize / Reconfigure", true, None::<&str>)?;
            let restart = MenuItem::with_id(app, "restart", "Restart Service", true, None::<&str>)?;
            let open_config = MenuItem::with_id(app, "open_config", "Open Config File", true, None::<&str>)?;
            let open_logs = MenuItem::with_id(app, "open_logs", "Open Logs Folder", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "Quit Tray", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&initialize, &restart, &open_config, &open_logs, &quit])?;
            let _tray = TrayIconBuilder::new().menu(&menu).tooltip("mc-netprobe Client").build(app)?;
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("failed to run mc-netprobe tray");
}
```

- [ ] **Step 5: Add initialization UI**

Create `clients/windows/apps/tray/ui/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>mc-netprobe Client Setup</title>
    <style>
      body { font-family: Segoe UI, sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }
      main { max-width: 680px; margin: 0 auto; padding: 24px; }
      label { display: block; margin: 14px 0; font-weight: 600; }
      input { box-sizing: border-box; width: 100%; min-height: 40px; margin-top: 6px; padding: 8px 10px; }
      button { min-height: 40px; padding: 8px 14px; border: 0; border-radius: 8px; background: #0f172a; color: white; }
      .hint { color: #475569; font-size: 14px; }
    </style>
  </head>
  <body>
    <main>
      <h1>mc-netprobe Client Setup</h1>
      <p class="hint">Initialize this Windows client and pair it with the panel.</p>
      <label>Panel URL <input id="panelUrl" value="http://panel-host:8765"></label>
      <label>Pair Code <input id="pairCode" autocomplete="off"></label>
      <label>Node Name <input id="nodeName" value="client-1"></label>
      <label>Listen Port <input id="listenPort" type="number" value="9870"></label>
      <label><input id="exposeControlBridge" type="checkbox"> Expose control bridge remotely</label>
      <button id="initialize">Initialize</button>
      <pre id="status"></pre>
    </main>
    <script src="./app.js"></script>
  </body>
</html>
```

Create `clients/windows/apps/tray/ui/app.js`:

```javascript
const statusEl = document.getElementById('status');
document.getElementById('initialize').addEventListener('click', () => {
  const payload = {
    panelUrl: document.getElementById('panelUrl').value,
    pairCode: document.getElementById('pairCode').value,
    nodeName: document.getElementById('nodeName').value,
    listenPort: Number(document.getElementById('listenPort').value),
    exposeControlBridge: document.getElementById('exposeControlBridge').checked,
  };
  statusEl.textContent = JSON.stringify(payload, null, 2);
});
```

- [ ] **Step 6: Run cargo checks**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
cargo check --manifest-path clients/windows/Cargo.toml -p mc-netprobe-tray
```

Expected: crate checks. If Linux lacks WebKit/Tauri system dependencies, record the missing package message and run `cargo check -p mc-netprobe-client-core -p mc-netprobe-service -p mc-netprobe-elevate` before committing.

- [ ] **Step 7: Commit**

```bash
git add clients/windows/Cargo.toml clients/windows/apps/tray
git commit -m "feat(windows): scaffold tauri tray setup ui"
```

---

### Task 9: Add Packaging and Static Script Tests

**Files:**
- Create: `clients/windows/scripts/package-windows-client.ps1`
- Create: `clients/windows/scripts/validate-windows-client.ps1`
- Create: `tests/test_windows_packaging_scripts.py`
- Create: `clients/windows/README-WINDOWS.md`

- [ ] **Step 1: Write static packaging tests**

Create `tests/test_windows_packaging_scripts.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = ROOT / "clients" / "windows" / "scripts" / "package-windows-client.ps1"
VALIDATE_SCRIPT = ROOT / "clients" / "windows" / "scripts" / "validate-windows-client.ps1"
README = ROOT / "clients" / "windows" / "README-WINDOWS.md"


def test_package_script_names_expected_zip_entries() -> None:
    text = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    for entry in [
        "mc-netprobe-tray.exe",
        "mc-netprobe-service.exe",
        "mc-netprobe-elevate.exe",
        "python",
        "repo",
        "templates",
    ]:
        assert entry in text


def test_validate_script_checks_service_firewall_and_no_console_window_claim() -> None:
    text = VALIDATE_SCRIPT.read_text(encoding="utf-8")
    assert "Get-Service -Name mc-netprobe-client" in text
    assert "Get-NetFirewallRule" in text
    assert "Get-Process" in text


def test_windows_readme_documents_program_data_runtime() -> None:
    text = README.read_text(encoding="utf-8")
    assert "C:\\ProgramData\\mc-netprobe\\client" in text
    assert "Open Config File" in text
    assert "Open Logs Folder" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
.venv/bin/python -m pytest tests/test_windows_packaging_scripts.py -q
```

Expected: fail because scripts and README do not exist.

- [ ] **Step 3: Add package script**

Create `clients/windows/scripts/package-windows-client.ps1`:

```powershell
param(
  [string]$BuildRef = "dev",
  [string]$Version = "0.1.0",
  [string]$PythonRuntime = "python",
  [string]$OutputDir = "clients/windows/dist"
)

$ErrorActionPreference = "Stop"
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$distRoot = Join-Path $repoRoot $OutputDir
$stage = Join-Path $distRoot "stage"
$zipName = "mc-netprobe-client-windows-x64-$Version-$BuildRef.zip"
$zipPath = Join-Path $distRoot $zipName

Remove-Item -Recurse -Force $stage -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $stage | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "python") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "repo") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $stage "templates") | Out-Null

Copy-Item (Join-Path $repoRoot "clients/windows/templates/*") (Join-Path $stage "templates") -Recurse -Force
Copy-Item (Join-Path $repoRoot "clients/windows/README-WINDOWS.md") (Join-Path $stage "README-WINDOWS.md") -Force
Copy-Item (Join-Path $repoRoot "target/release/mc-netprobe-tray.exe") (Join-Path $stage "mc-netprobe-tray.exe") -Force
Copy-Item (Join-Path $repoRoot "target/release/mc-netprobe-service.exe") (Join-Path $stage "mc-netprobe-service.exe") -Force
Copy-Item (Join-Path $repoRoot "target/release/mc-netprobe-elevate.exe") (Join-Path $stage "mc-netprobe-elevate.exe") -Force
Copy-Item $PythonRuntime (Join-Path $stage "python") -Recurse -Force

foreach ($path in @("agents", "controller", "probes", "exporters", "requirements.txt")) {
  Copy-Item (Join-Path $repoRoot $path) (Join-Path $stage "repo") -Recurse -Force
}

Remove-Item -Force $zipPath -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $zipPath
Write-Host $zipPath
```

- [ ] **Step 4: Add validation script**

Create `clients/windows/scripts/validate-windows-client.ps1`:

```powershell
$ErrorActionPreference = "Stop"

$service = Get-Service -Name mc-netprobe-client
Write-Host "Service: $($service.Status)"

$agentRule = Get-NetFirewallRule -DisplayName "mc-netprobe-client-agent-9870" -ErrorAction SilentlyContinue
if (-not $agentRule) {
  throw "Missing firewall rule mc-netprobe-client-agent-9870"
}
Write-Host "Firewall rule: $($agentRule.DisplayName)"

$processes = Get-Process | Where-Object { $_.ProcessName -match "python|mc-netprobe" }
Write-Host "Related process count: $($processes.Count)"

$configPath = "C:\ProgramData\mc-netprobe\client\config\agent\client.yaml"
$logsPath = "C:\ProgramData\mc-netprobe\client\logs"
if (-not (Test-Path $configPath)) { throw "Missing config: $configPath" }
if (-not (Test-Path $logsPath)) { throw "Missing logs directory: $logsPath" }

Write-Host "Validation complete"
```

- [ ] **Step 5: Add README**

Create `clients/windows/README-WINDOWS.md`:

```markdown
# mc-netprobe Windows Client

This package targets Windows 10/11 x64.

## First Run

1. Unzip `mc-netprobe-client-windows-x64-<version>-<build-ref>.zip`.
2. Run `mc-netprobe-tray.exe`.
3. Choose `Initialize / Reconfigure`.
4. Approve the UAC prompt.
5. Enter Panel URL, Pair Code, Node Name, and Listen Port.

The initialized runtime is copied to:

```text
C:\ProgramData\mc-netprobe\client
```

## Tray Shortcuts

- `Open Config File` opens `C:\ProgramData\mc-netprobe\client\config\agent\client.yaml`.
- `Open Logs Folder` opens `C:\ProgramData\mc-netprobe\client\logs`.
- `Open Panel` opens the configured panel URL.

The background service starts before user login. The tray starts after user login and acts as a control surface.
```

- [ ] **Step 6: Run tests**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
.venv/bin/python -m pytest tests/test_windows_packaging_scripts.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add clients/windows/scripts clients/windows/README-WINDOWS.md tests/test_windows_packaging_scripts.py
git commit -m "build(windows): add client packaging scripts"
```

---

### Task 10: Wire Full Validation Commands and Documentation Index

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add README pointer**

Modify `README.md` under `Client Agent On Windows` by adding:

```markdown
### New Windows tray/service client

The new Windows client work is tracked in:

- Design: `docs/superpowers/specs/2026-04-26-windows-client-design.md`
- Plan: `docs/superpowers/plans/2026-04-26-windows-client-tray-service-plan.md`
- Windows client README: `clients/windows/README-WINDOWS.md`

The first version targets Windows 10/11 x64 and installs its runtime to `C:\ProgramData\mc-netprobe\client`.
```

- [ ] **Step 2: Run docs grep checks**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
grep -R "C:\\\\ProgramData\\\\mc-netprobe\\\\client" -n README.md clients/windows/README-WINDOWS.md docs/superpowers/specs/2026-04-26-windows-client-design.md
```

Expected: each file has at least one match.

- [ ] **Step 3: Run full local validation**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
.venv/bin/python -m pytest tests/test_windows_client_templates.py tests/test_windows_service_supervisor_adapter.py tests/test_windows_packaging_scripts.py tests/test_control_bridge.py tests/test_agent_service.py -q
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-client-core
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-service
cargo run --manifest-path clients/windows/Cargo.toml -p mc-netprobe-elevate -- plan-install
```

Expected:

- pytest exits 0.
- cargo tests exit 0.
- elevated helper plan command prints JSON with service and firewall plans.

- [ ] **Step 4: Commit docs pointer**

```bash
git add README.md
git commit -m "docs(windows): link tray service client docs"
```

---

### Task 11: Windows Runtime Implementation Pass

**Files:**
- Modify: `clients/windows/crates/mc-netprobe-service/src/main.rs`
- Modify: `clients/windows/crates/mc-netprobe-service/src/supervisor.rs`
- Modify: `clients/windows/crates/mc-netprobe-service/src/control.rs`
- Modify: `clients/windows/crates/mc-netprobe-elevate/src/main.rs`
- Modify: `clients/windows/apps/tray/src-tauri/src/main.rs`

- [ ] **Step 1: Implement Windows-only service entrypoint**

Add `#[cfg(windows)]` code in `mc-netprobe-service/src/main.rs` that uses the `windows-service` crate to register the service entrypoint named `mc-netprobe-client`. Keep the non-Windows CLI behavior from Task 6 unchanged so Linux CI still works.

The Windows entrypoint must:

- Load `C:\ProgramData\mc-netprobe\client\config\client-app.yaml`.
- Build `ClientPaths`.
- Start `Supervisor`.
- Start Named Pipe server.
- Stop children on service stop.

- [ ] **Step 2: Implement hidden child process launch**

In `supervisor.rs`, add Windows-only child launch code using `std::os::windows::process::CommandExt` and `CREATE_NO_WINDOW`.

The launch must:

- Use `process_spec::agent_process`.
- Use `process_spec::control_bridge_process`.
- Redirect stdout and stderr to the configured log file.
- Record child state in `SupervisorStatus`.

- [ ] **Step 3: Implement Named Pipe server and CLI client**

In `control.rs`, add Windows-only Named Pipe handling:

- Server accepts one JSON request per connection.
- CLI mode `mc-netprobe-service.exe control status|start|stop|restart` connects to the pipe and prints JSON response.
- Request/response types must use `mc_netprobe_client_core::ipc`.

- [ ] **Step 4: Implement elevated helper actions**

In `mc-netprobe-elevate/src/main.rs`, implement `initialize` on Windows:

- Copy files into `C:\ProgramData\mc-netprobe\client`.
- Write config templates with wizard-provided values.
- Run `sc.exe create` or Windows Service API registration.
- Run `netsh advfirewall firewall add rule` for enabled firewall plans.
- Start the service.
- Print structured JSON result.

- [ ] **Step 5: Implement tray menu actions**

In `tray/src-tauri/src/main.rs`, connect tray menu items to:

- Open initialization window.
- Call service control CLI or Named Pipe for status/restart/start/stop.
- Open config file through `tauri-plugin-opener`.
- Open logs folder.
- Open panel URL from `client-app.yaml`.
- Quit tray.

- [ ] **Step 6: Run Windows validation**

On a Windows 10/11 x64 machine:

```powershell
cargo build --manifest-path clients/windows/Cargo.toml --release
powershell -ExecutionPolicy Bypass -File clients/windows/scripts/package-windows-client.ps1 -BuildRef (git rev-parse --short=12 HEAD)
powershell -ExecutionPolicy Bypass -File clients/windows/scripts/validate-windows-client.ps1
```

Expected:

- Release binaries build.
- Zip is created.
- Service installs and starts.
- No console windows remain visible during normal operation.

- [ ] **Step 7: Commit runtime implementation**

```bash
git add clients/windows
git commit -m "feat(windows): implement tray service runtime"
```

---

### Task 12: Staging Pairing and Final Branch Validation

**Files:**
- Modify only if validation reveals an issue in files from prior tasks.

- [ ] **Step 1: Run Linux-side regression tests**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
.venv/bin/python -m pytest tests/test_agent_service.py tests/test_control_bridge.py tests/test_windows_client_templates.py tests/test_windows_service_supervisor_adapter.py tests/test_windows_packaging_scripts.py -q
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-client-core
cargo test --manifest-path clients/windows/Cargo.toml -p mc-netprobe-service
```

Expected: all tests pass.

- [ ] **Step 2: Pair Windows client against staging panel**

On Windows, initialize the client with:

```text
Panel URL: http://100.100.0.17:18765
Node Name: client-windows-e2e
Role: client
Runtime Mode: native-windows
Listen Port: 9870
```

Expected:

- Panel shows node role `client`.
- Runtime mode is `native-windows`.
- Pair succeeds.
- Heartbeat updates.
- Direct or heartbeat job dispatch completes and result appears in panel.

- [ ] **Step 3: Verify reboot behavior**

On Windows:

```powershell
Restart-Computer
```

After reboot and before relying on tray:

```powershell
Get-Service -Name mc-netprobe-client
Get-Content C:\ProgramData\mc-netprobe\client\logs\supervisor.log -Tail 40
```

Expected:

- Service status is `Running`.
- Supervisor log shows agent and control bridge started.
- Panel receives heartbeat after reboot.

- [ ] **Step 4: Verify tray shortcuts**

Use the tray menu:

- `Open Config File` opens `client.yaml`.
- `Open Logs Folder` opens the logs directory.
- `Open Panel` opens the configured panel URL.
- `Copy Diagnostics` redacts `node_token` and `pair_code`.

Expected: all menu items work without administrator prompts.

- [ ] **Step 5: Push branch**

Run:

```bash
cd /root/server/Frp-network-evaluation-windows-client
git status --short
git push origin codex/windows-client-tray-service
```

Expected:

- `git status --short` is clean before push.
- Remote branch contains the final implementation commits.
