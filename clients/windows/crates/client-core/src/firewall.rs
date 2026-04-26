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
    FirewallRulePlan {
        name: format!("{prefix}-{port}"),
        port,
        enabled: true,
    }
}

pub fn control_bridge_rule(prefix: &str, port: u16, expose_remote: bool) -> FirewallRulePlan {
    FirewallRulePlan {
        name: format!("{prefix}-{port}"),
        port,
        enabled: expose_remote,
    }
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
