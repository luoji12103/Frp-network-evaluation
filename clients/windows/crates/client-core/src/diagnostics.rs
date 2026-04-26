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
                    let redacted =
                        if SECRET_KEYS.iter().any(|secret| key.to_ascii_lowercase().contains(secret))
                        {
                            serde_json::Value::String("<redacted>".into())
                        } else {
                            redact_value(value)
                        };
                    (key, redacted)
                })
                .collect(),
        ),
        serde_json::Value::Array(items) => {
            serde_json::Value::Array(items.into_iter().map(redact_value).collect())
        }
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
