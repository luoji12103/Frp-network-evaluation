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
            "start" | "stop" | "restart" => {
                control::offline_response("cli", format!("{command} requires the Windows service runtime"))
            }
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
