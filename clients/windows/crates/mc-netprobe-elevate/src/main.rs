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
