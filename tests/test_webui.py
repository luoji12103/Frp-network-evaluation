from controller.webui import build_default_topology_payload, collect_config_warnings, collect_run_blockers


def test_build_default_topology_payload_is_remote_ready() -> None:
    payload = build_default_topology_payload()
    assert payload["nodes"]["client"]["local"] is False
    assert payload["nodes"]["relay"]["os"] == "linux"
    assert payload["services"]["mc_public"]["port"] == 25565


def test_collect_config_warnings_for_incomplete_payload() -> None:
    payload = {
        "topology": build_default_topology_payload(),
        "thresholds": {},
        "scenarios": {},
    }
    warnings = collect_config_warnings(payload)
    assert any("client.host" in item for item in warnings)
    assert any("relay.ssh_user" in item for item in warnings)


def test_collect_run_blockers_requires_hosts_and_remote_fields() -> None:
    payload = {
        "topology": build_default_topology_payload(),
        "thresholds": {},
        "scenarios": {},
    }
    blockers = collect_run_blockers(payload)
    assert any("client host is required" == item for item in blockers)
    assert any("relay ssh_user is required for remote execution" == item for item in blockers)
