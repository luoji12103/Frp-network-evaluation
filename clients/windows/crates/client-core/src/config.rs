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
