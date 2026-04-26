from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CLIENT_TEMPLATE = ROOT / "clients" / "windows" / "templates" / "client.yaml"
APP_TEMPLATE = ROOT / "clients" / "windows" / "templates" / "client-app.yaml"


def test_windows_agent_template_uses_existing_agent_contract_fields() -> None:
    payload = yaml.safe_load(CLIENT_TEMPLATE.read_text(encoding="utf-8"))
    assert payload["role"] == "client"
    assert payload["runtime_mode"] == "native-windows"
    assert payload["listen_host"] == "0.0.0.0"
    assert payload["listen_port"] == 9870
    assert payload["control_port"] == 9871
    assert payload["protocol_version"] == "1"
    assert payload["agent_version"] == "1"
    assert payload["platform_name_override"] is None
    assert "node_token" in payload
    assert "pair_code" in payload


def test_windows_client_app_template_scopes_firewall_and_service_names() -> None:
    payload = yaml.safe_load(APP_TEMPLATE.read_text(encoding="utf-8"))
    assert payload["service_name"] == "mc-netprobe-client"
    assert payload["display_name"] == "mc-netprobe Client"
    assert payload["pipe_name"] == r"\\.\pipe\mc-netprobe-client-service"
    assert payload["restart_policy"]["max_restarts"] == 5
    assert payload["restart_policy"]["window_seconds"] == 600
    assert payload["firewall"]["agent_rule_prefix"] == "mc-netprobe-client-agent"
    assert payload["firewall"]["control_bridge_rule_prefix"] == "mc-netprobe-client-control-bridge"
    assert payload["control_bridge"]["host"] == "127.0.0.1"
    assert payload["control_bridge"]["port"] == 9871
    assert payload["control_bridge"]["expose_remote"] is False
    assert payload["paths"]["runtime_root"] == r"C:\ProgramData\mc-netprobe\client"
    assert payload["paths"]["agent_config"] == r"C:\ProgramData\mc-netprobe\client\config\agent\client.yaml"
    assert payload["paths"]["logs_dir"] == r"C:\ProgramData\mc-netprobe\client\logs"
