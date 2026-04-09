from __future__ import annotations

from pathlib import Path

from controller.agent_http_client import AgentHttpError
from controller.panel_models import AgentCapabilities, AgentEndpointReport, AgentIdentity, AgentRuntimeStatus, NodeUpsertRequest
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


def test_dispatch_probe_records_pull_error_code_and_queue_fallback(monkeypatch, tmp_path: Path) -> None:
    store = PanelStore(db_path=tmp_path / "monitor.db", secret_path=tmp_path / "panel-secret.txt")
    orchestrator = PanelOrchestrator(store=store, output_root=tmp_path / "results")

    node = store.upsert_node(
        NodeUpsertRequest(
            node_name="relay-1",
            role="relay",
            runtime_mode="docker-linux",
            configured_pull_url="http://relay.example:9870",
            enabled=True,
        )
    )
    pair_code, _ = store.create_pair_code(node["id"])
    store.pair_agent(
        identity=AgentIdentity(
            node_name=node["node_name"],
            role=node["role"],
            runtime_mode=node["runtime_mode"],
            protocol_version="1",
            platform_name="linux",
            hostname="relay-1-host",
            agent_version="test-agent",
        ),
        pair_code=pair_code,
        endpoint=AgentEndpointReport(
            listen_host="0.0.0.0",
            listen_port=9870,
            advertise_url="http://relay.example:9870",
        ),
        capabilities=AgentCapabilities(pull_http=True, heartbeat_queue=True, result_lookup=True),
    )
    store.record_heartbeat(
        node_id=node["id"],
        endpoint=AgentEndpointReport(
            listen_host="0.0.0.0",
            listen_port=9870,
            advertise_url="http://relay.example:9870",
        ),
        runtime_status=AgentRuntimeStatus(
            paired=True,
            started_at=now_iso(),
            last_heartbeat_at=now_iso(),
            last_error=None,
            environment={},
        ),
    )
    run_id = store.create_run("baseline", "test")
    node = store.get_node(node["id"])
    assert node is not None

    def fake_run_job(node, job_id, run_id, task, payload):
        raise AgentHttpError("timeout", "request to http://relay.example/api/v1/jobs/run timed out")

    def fake_dispatch_via_queue(node, run_id, task, payload, timeout_sec, event_run_id=None, path_label=None):
        return ProbeResult(
            name=task,
            source=node["role"],
            target=str(payload.get("host", node["node_name"])),
            success=True,
            metrics={"packet_loss_pct": 0.0},
            samples=[],
            error=None,
            started_at=now_iso(),
            duration_ms=1.0,
            metadata={},
        )

    monkeypatch.setattr(orchestrator.http, "run_job", fake_run_job)
    monkeypatch.setattr(orchestrator, "_dispatch_via_queue", fake_dispatch_via_queue)

    result = orchestrator._dispatch_probe(
        node=node,
        run_id="probe-run-1",
        task="ping",
        payload={"host": "relay.example", "timeout_sec": 1.0},
        path_label="client_to_relay",
        event_run_id=run_id,
    )

    assert result.success is True
    assert result.metadata["transport"] == "queue-fallback"
    assert result.metadata["fallback_from_code"] == "timeout"

    stored_node = store.get_node(node["id"])
    assert stored_node is not None
    assert stored_node["connectivity"]["pull"]["code"] == "timeout"

    events = store.list_run_events(run_id)
    transport_error = next(item for item in events if item["event_kind"] == "probe_transport_error")
    assert transport_error["payload"]["error_code"] == "timeout"
    completed = next(item for item in events if item["event_kind"] == "probe_completed")
    assert completed["payload"]["fallback_from_code"] == "timeout"


def test_dispatch_via_queue_classifies_pending_timeout(tmp_path: Path) -> None:
    store = PanelStore(db_path=tmp_path / "monitor.db", secret_path=tmp_path / "panel-secret.txt")
    orchestrator = PanelOrchestrator(store=store, output_root=tmp_path / "results")

    node = store.upsert_node(
        NodeUpsertRequest(
            node_name="relay-1",
            role="relay",
            runtime_mode="docker-linux",
            configured_pull_url="http://relay.example:9870",
            enabled=True,
        )
    )
    pair_code, _ = store.create_pair_code(node["id"])
    store.pair_agent(
        identity=AgentIdentity(
            node_name=node["node_name"],
            role=node["role"],
            runtime_mode=node["runtime_mode"],
            protocol_version="1",
            platform_name="linux",
            hostname="relay-1-host",
            agent_version="test-agent",
        ),
        pair_code=pair_code,
        endpoint=AgentEndpointReport(
            listen_host="0.0.0.0",
            listen_port=9870,
            advertise_url="http://relay.example:9870",
        ),
        capabilities=AgentCapabilities(pull_http=False, heartbeat_queue=True, result_lookup=True),
    )
    store.record_heartbeat(
        node_id=node["id"],
        endpoint=AgentEndpointReport(
            listen_host="0.0.0.0",
            listen_port=9870,
            advertise_url="http://relay.example:9870",
        ),
        runtime_status=AgentRuntimeStatus(
            paired=True,
            started_at=now_iso(),
            last_heartbeat_at=now_iso(),
            last_error=None,
            environment={},
        ),
    )
    run_id = store.create_run("baseline", "test")
    node = store.get_node(node["id"])
    assert node is not None

    result = orchestrator._dispatch_via_queue(
        node=node,
        run_id=run_id,
        task="ping",
        payload={"host": "relay.example", "timeout_sec": 0.0},
        timeout_sec=0.0,
        event_run_id=run_id,
        path_label="client_to_relay",
    )

    assert result.success is False
    assert result.metadata["error_code"] == "queue_not_leased"
    assert result.metadata["job"]["status"] == "pending"

    detail = store.get_run_detail(run_id)
    assert detail is not None
    assert detail["progress"]["last_failure_code"] == "queue_not_leased"
    assert detail["progress"]["latest_queue_job"]["status"] == "pending"
    assert detail["progress"]["latest_queue_job"]["job_id"]

    events = store.list_run_events(run_id)
    timeout_event = next(item for item in events if item["event_kind"] == "queue_timeout")
    assert timeout_event["payload"]["error_code"] == "queue_not_leased"
    assert timeout_event["payload"]["job"]["status"] == "pending"
