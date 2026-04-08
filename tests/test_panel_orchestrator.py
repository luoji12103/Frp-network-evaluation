from __future__ import annotations

from pathlib import Path

from controller.panel_models import AgentCapabilities, AgentEndpointReport, AgentIdentity, NodeUpsertRequest
from controller.panel_orchestrator import PanelOrchestrator
from controller.panel_store import PanelStore
from probes.common import ProbeResult, now_iso


def test_full_run_is_persisted_with_probe_history(monkeypatch, tmp_path: Path) -> None:
    store = PanelStore(db_path=tmp_path / "monitor.db", secret_path=tmp_path / "panel-secret.txt")
    orchestrator = PanelOrchestrator(store=store, output_root=tmp_path / "results")

    client = store.upsert_node(
        NodeUpsertRequest(
            node_name="client-1",
            role="client",
            runtime_mode="native-windows",
            configured_pull_url="http://client.example:9870",
            enabled=True,
        )
    )
    relay = store.upsert_node(
        NodeUpsertRequest(
            node_name="relay-1",
            role="relay",
            runtime_mode="docker-linux",
            configured_pull_url="http://relay.example:9870",
            enabled=True,
        )
    )
    server = store.upsert_node(
        NodeUpsertRequest(
            node_name="server-1",
            role="server",
            runtime_mode="native-macos",
            configured_pull_url="http://server.example:9870",
            enabled=True,
        )
    )

    for node in (client, relay, server):
        pair_code, _ = store.create_pair_code(node["id"])
        store.pair_agent(
            identity=AgentIdentity(
                node_name=node["node_name"],
                role=node["role"],
                runtime_mode=node["runtime_mode"],
                protocol_version="1",
                platform_name="test",
                hostname=f"{node['node_name']}-host",
                agent_version="test-agent",
            ),
            pair_code=pair_code,
            endpoint=AgentEndpointReport(
                listen_host="0.0.0.0",
                listen_port=9870,
                advertise_url=node["endpoints"]["configured_pull_url"],
            ),
            capabilities=AgentCapabilities(),
        )
        store.update_pull_status(node["id"], ok=True)

    def fake_run_job(node, job_id, run_id, task, payload):
        name = "system_snapshot" if task == "system_snapshot" else task
        metrics = {}
        target = str(payload.get("host") or payload.get("port") or node["node_name"])
        if task == "ping":
            metrics = {"packet_loss_pct": 0.0, "rtt_avg_ms": 10.0, "rtt_p95_ms": 12.0, "jitter_ms": 1.0}
        elif task in {"tcp_probe", "mc_tcp_probe"}:
            name = "mc_tcp_connect" if task == "mc_tcp_probe" else "tcp_handshake"
            metrics = {"connect_avg_ms": 15.0, "connect_p95_ms": 18.0, "connect_timeout_or_error_pct": 0.0}
        elif task == "throughput":
            metrics = {
                "throughput_up_mbps": None if payload.get("reverse") else 25.0,
                "throughput_down_mbps": 24.0 if payload.get("reverse") else None,
                "throughput_stability_score": 99.0,
            }
        elif task == "start_iperf_server":
            name = "iperf3_server"
            metrics = {"port": payload["port"]}
            target = f"{payload['bind_host']}:{payload['port']}"
        elif task == "system_snapshot":
            metrics = {"cpu_usage_pct": 10.0, "memory_usage_pct": 20.0, "network_up_mbps": 1.0, "network_down_mbps": 1.0}

        return {
            "ok": True,
            "run_id": run_id,
            "result": ProbeResult(
                name=name,
                source=node["role"],
                target=target,
                success=True,
                metrics=metrics,
                samples=[],
                error=None,
                started_at=now_iso(),
                duration_ms=1.0,
                metadata={},
            ).to_dict(),
        }

    monkeypatch.setattr(orchestrator.http, "run_job", fake_run_job)

    run_id = store.create_run("full", "test")
    orchestrator._run_and_persist(run_id=run_id, run_kind="full", source="test")

    run = store.list_recent_runs(limit=1)[0]
    assert run["id"] == run_id
    assert run["status"] == "completed"
    assert run["html_path"]

    samples = store.query_history(metric_name="cpu_usage_pct", time_range_hours=24)
    assert samples
