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
        Self {
            version: IPC_VERSION,
            request_id: request_id.into(),
            command: ServiceCommand::Status,
        }
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
