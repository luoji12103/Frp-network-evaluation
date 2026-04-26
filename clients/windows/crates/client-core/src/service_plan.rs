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
    let root = runtime_root.to_string_lossy();
    if root.contains('\\') {
        format!(r"{}\app\mc-netprobe-service.exe", root.trim_end_matches(['\\', '/']))
    } else {
        runtime_root
            .join("app")
            .join("mc-netprobe-service.exe")
            .to_string_lossy()
            .to_string()
    }
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
        assert!(args.contains(&r"binPath= C:\ProgramData\mc-netprobe\client\app\mc-netprobe-service.exe".to_string()));
    }
}
