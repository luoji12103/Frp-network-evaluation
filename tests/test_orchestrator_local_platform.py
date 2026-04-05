import asyncio

from controller.orchestrator import Orchestrator
from controller.scenario import ScenariosConfig, ThresholdsConfig, TopologyConfig
from probes.common import ProbeResult


def test_local_nodes_use_host_platform_for_execution(monkeypatch) -> None:
    topology = TopologyConfig.model_validate(
        {
            "project_name": "mc-frp-netprobe",
            "nodes": {
                "client": {"role": "client", "host": "127.0.0.1", "os": "windows", "local": True},
                "relay": {"role": "relay", "host": "127.0.0.1", "os": "linux", "local": True},
                "server": {"role": "server", "host": "127.0.0.1", "os": "macos", "local": True},
            },
            "services": {
                "relay_probe": {"host": "127.0.0.1", "port": 22},
                "mc_public": {"host": "127.0.0.1", "port": 25565},
                "iperf_public": {"host": "127.0.0.1", "port": 5201},
                "mc_local": {"host": "127.0.0.1", "port": 25565},
                "iperf_local": {"host": "127.0.0.1", "port": 5201},
            },
        }
    )
    orchestrator = Orchestrator(
        topology=topology,
        thresholds=ThresholdsConfig(),
        scenarios=ScenariosConfig(),
        run_id="run-test",
    )
    captured_payload: dict[str, object] = {}

    async def fake_execute_task(role: str, task: str, payload: dict[str, object]) -> dict[str, object]:
        captured_payload.update(payload)
        return ProbeResult(
            name=task,
            source=role,
            target=str(payload["host"]),
            success=True,
            metadata={},
        ).to_dict()

    monkeypatch.setattr("controller.orchestrator.execute_task", fake_execute_task)
    monkeypatch.setattr("controller.orchestrator.detect_platform_name", lambda: "linux")

    result = asyncio.run(
        orchestrator._execute_on_node(
            "client",
            "ping",
            {"host": "127.0.0.1"},
            path_label="client_to_relay",
        )
    )

    assert captured_payload["platform_name"] == "linux"
    assert result.metadata["node_os"] == "linux"
    assert result.metadata["configured_node_os"] == "windows"
