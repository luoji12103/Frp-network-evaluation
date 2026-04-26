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
        assert!(spec.program.to_string_lossy().ends_with(r"app\python\python.exe"));
        assert_eq!(spec.args[0..2], ["-m", "agents.service"]);
        assert!(spec.args.contains(&"--config".to_string()));
        assert_eq!(
            spec.working_dir,
            PathBuf::from(r"C:\ProgramData\mc-netprobe\client\app\repo")
        );
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
