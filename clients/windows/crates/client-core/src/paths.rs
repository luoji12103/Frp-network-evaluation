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
        let app_dir = join_runtime_path(&root, &["app"]);
        let logs_dir = join_runtime_path(&root, &["logs"]);
        let state_dir = join_runtime_path(&root, &["state"]);
        Self {
            repo_dir: join_runtime_path(&app_dir, &["repo"]),
            python_exe: join_runtime_path(&app_dir, &["python", "python.exe"]),
            agent_config: join_runtime_path(&root, &["config", "agent", "client.yaml"]),
            client_config: join_runtime_path(&root, &["config", "client-app.yaml"]),
            agent_log: join_runtime_path(&logs_dir, &["agent.log"]),
            control_bridge_log: join_runtime_path(&logs_dir, &["control-bridge.log"]),
            supervisor_log: join_runtime_path(&logs_dir, &["supervisor.log"]),
            status_file: join_runtime_path(&state_dir, &["supervisor-status.json"]),
            app_dir,
            logs_dir,
            state_dir,
            root,
        }
    }
}

pub fn default_runtime_root() -> PathBuf {
    let program_data = std::env::var_os("PROGRAMDATA")
        .map(|value| value.to_string_lossy().into_owned())
        .unwrap_or_else(|| r"C:\ProgramData".to_string());
    windows_path_from_root(&program_data, &["mc-netprobe", "client"])
}

fn join_runtime_path(root: &PathBuf, segments: &[&str]) -> PathBuf {
    let root = root.to_string_lossy();
    if root.contains('\\') {
        let mut path = root.trim_end_matches(['\\', '/']).to_string();
        for segment in segments {
            path.push('\\');
            path.push_str(segment);
        }
        PathBuf::from(path)
    } else {
        segments
            .iter()
            .fold(PathBuf::from(root.as_ref()), |path, segment| path.join(segment))
    }
}

fn windows_path_from_root(root: &str, segments: &[&str]) -> PathBuf {
    let mut path = root.trim_end_matches(['\\', '/']).to_string();
    for segment in segments {
        path.push('\\');
        path.push_str(segment);
    }
    PathBuf::from(path)
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
        assert!(root.to_string_lossy().ends_with(r"mc-netprobe\client"));
    }

    #[test]
    fn windows_path_from_root_uses_backslashes_on_linux() {
        let root = windows_path_from_root(r"C:\ProgramData", &["mc-netprobe", "client"]);
        assert_eq!(root, PathBuf::from(r"C:\ProgramData\mc-netprobe\client"));
    }
}
