use mc_netprobe_client_core::ipc::{IPC_VERSION, ServiceResponse, ServiceStatus};

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
