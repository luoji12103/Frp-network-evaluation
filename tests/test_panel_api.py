from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from controller.panel_models import NodeUpsertRequest
from controller.webui import create_app
from probes.common import ProbeResult, RunResult, ThresholdFinding, now_iso


def build_client(tmp_path: Path) -> TestClient:
    app = create_app(
        db_path=tmp_path / "monitor.db",
        start_background=False,
        admin_username="admin",
        admin_password="secret-pass",
    )
    return TestClient(app)


def login_admin(client: TestClient) -> None:
    response = client.post(
        "/login",
        content="username=admin&password=secret-pass&next=%2Fadmin",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin"


def seed_dashboard_data(client: TestClient) -> str:
    runtime = client.app.state.runtime
    store = runtime.store
    nodes = [
        NodeUpsertRequest(node_name="client-1", role="client", runtime_mode="native-windows", agent_url="http://client.example:9870", enabled=True),
        NodeUpsertRequest(node_name="relay-1", role="relay", runtime_mode="docker-linux", agent_url="http://relay.example:9870", enabled=True),
        NodeUpsertRequest(node_name="server-1", role="server", runtime_mode="native-macos", agent_url="http://server.example:9870", enabled=True),
    ]
    for payload in nodes:
        node = store.upsert_node(payload)
        pair_code, _ = store.create_pair_code(node["id"])
        store.pair_agent(
            node_name=node["node_name"],
            role=node["role"],
            runtime_mode=node["runtime_mode"],
            pair_code=pair_code,
            agent_url=node["agent_url"],
            advertise_url=node["agent_url"],
        )
        store.update_pull_status(node["id"], ok=True)

    created_run_id = store.create_run("full", "test")
    run_result = RunResult(
        run_id="run-seeded",
        project="mc-netprobe-monitor",
        started_at=now_iso(),
        finished_at=now_iso(),
        environment={"platform": "test"},
        probes=[
            ProbeResult(
                name="ping",
                source="client",
                target="relay",
                success=True,
                metrics={"packet_loss_pct": 0.0, "rtt_avg_ms": 10.0, "rtt_p95_ms": 12.0, "jitter_ms": 1.0},
                metadata={"path_label": "client_to_relay", "source_node": "client"},
            ),
            ProbeResult(
                name="ping",
                source="relay",
                target="server",
                success=True,
                metrics={"packet_loss_pct": 0.2, "rtt_avg_ms": 22.0, "rtt_p95_ms": 30.0, "jitter_ms": 4.0},
                metadata={"path_label": "relay_to_server", "source_node": "relay"},
            ),
            ProbeResult(
                name="tcp_handshake",
                source="client",
                target="mc_public",
                success=True,
                metrics={"connect_avg_ms": 165.0, "connect_p95_ms": 180.0, "connect_timeout_or_error_pct": 0.0},
                metadata={"path_label": "client_to_mc_public", "source_node": "client"},
            ),
            ProbeResult(
                name="throughput",
                source="client",
                target="iperf_public",
                success=True,
                metrics={"throughput_up_mbps": 48.0, "throughput_down_mbps": 52.0},
                metadata={"path_label": "client_to_iperf_public", "source_node": "client"},
            ),
            ProbeResult(
                name="system_snapshot",
                source="client",
                target="client",
                success=True,
                metrics={"cpu_usage_pct": 21.0, "memory_usage_pct": 31.0},
                metadata={"path_label": "client_system", "source_node": "client"},
            ),
        ],
        threshold_findings=[
            ThresholdFinding(
                path_label="client_to_mc_public",
                probe_name="tcp_handshake",
                metric="connect_avg_ms",
                threshold=150.0,
                actual=165.0,
                message="connect_avg_ms exceeded the configured maximum",
            )
        ],
        conclusion=["seeded run"],
    )
    store.finish_run(created_run_id, status="completed", run_result=run_result)
    return created_run_id


def test_public_dashboard_bootstraps_defaults(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.get("/api/v1/public-dashboard")
        assert response.status_code == 200
        payload = response.json()
        assert payload["topology_name"] == "mc-netprobe-monitor"
        assert payload["summary"]["total_nodes"] == 0


def test_public_page_includes_login_and_bilingual_toggle(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.get("/")
        assert response.status_code == 200
        body = response.text
        assert 'id="localeSelect"' in body
        assert "Admin Login" in body
        assert "/assets/public-dashboard.js" in body


def test_admin_login_required_for_management_routes(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        page = client.get("/admin", follow_redirects=False)
        assert page.status_code == 303
        assert page.headers["location"] == "/login?next=/admin"

        api = client.get("/api/v1/dashboard")
        assert api.status_code == 401
        assert api.json()["detail"] == "Admin login required"


def test_admin_login_allows_dashboard_access(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        page = client.get("/admin")
        assert page.status_code == 200
        assert "Save Global Settings" in page.text
        assert "/assets/admin-dashboard.js" in page.text

        api = client.get("/api/v1/dashboard")
        assert api.status_code == 200
        payload = api.json()
        assert payload["settings"]["services"]["mc_public"]["port"] == 25565
        assert [item["run_kind"] for item in payload["schedules"]] == ["system", "baseline", "capacity"]


def test_node_pair_code_and_agent_pairing_flow(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        node = client.post(
            "/api/v1/nodes",
            json={
                "node_name": "relay-1",
                "role": "relay",
                "runtime_mode": "docker-linux",
                "agent_url": "http://relay.example:9870",
                "enabled": True,
            },
        ).json()["node"]
        pair = client.post(f"/api/v1/nodes/{node['id']}/pair-code")
        assert pair.status_code == 200
        pair_payload = pair.json()
        assert "docker compose -f docker/relay-agent.compose.yml up -d --build" in pair_payload["startup_command"]

        paired = client.post(
            "/api/v1/agents/pair",
            json={
                "node_name": "relay-1",
                "role": "relay",
                "runtime_mode": "docker-linux",
                "pair_code": pair_payload["pair_code"],
                "agent_url": "http://relay.example:9870",
                "advertise_url": "http://relay.example:9870",
                "listen_host": "0.0.0.0",
                "listen_port": 9870,
                "platform_name": "linux",
                "hostname": "relay-host",
                "version": "1",
            },
        )
        assert paired.status_code == 200
        token = paired.json()["node_token"]
        assert token

        heartbeat = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "node_name": "relay-1",
                "agent_url": "http://relay.example:9870",
                "advertise_url": "http://relay.example:9870",
                "status": {"uptime_sec": 10},
                "completed_jobs": [],
            },
        )
        assert heartbeat.status_code == 200
        assert heartbeat.json()["jobs"] == []


def test_heartbeat_leases_jobs_and_accepts_completed_results(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        runtime = client.app.state.runtime
        node = client.post(
            "/api/v1/nodes",
            json={
                "node_name": "client-1",
                "role": "client",
                "runtime_mode": "native-windows",
                "agent_url": "http://client.example:9870",
                "enabled": True,
            },
        ).json()["node"]
        pair_code = client.post(f"/api/v1/nodes/{node['id']}/pair-code").json()["pair_code"]
        token = client.post(
            "/api/v1/agents/pair",
            json={
                "node_name": "client-1",
                "role": "client",
                "runtime_mode": "native-windows",
                "pair_code": pair_code,
                "agent_url": "http://client.example:9870",
                "advertise_url": "http://client.example:9870",
                "listen_host": "0.0.0.0",
                "listen_port": 9870,
                "platform_name": "windows",
                "hostname": "client-host",
                "version": "1",
            },
        ).json()["node_token"]

        run_id = runtime.store.create_run("baseline", "test")
        job_id = runtime.store.enqueue_job(
            node_id=node["id"],
            run_id=run_id,
            task="ping",
            payload={"host": "127.0.0.1", "count": 2, "timeout_sec": 1.0},
        )

        first = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "node_name": "client-1",
                "agent_url": "http://client.example:9870",
                "status": {"ok": True},
                "completed_jobs": [],
            },
        )
        assert first.status_code == 200
        assert first.json()["jobs"][0]["job_id"] == job_id

        second = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "node_name": "client-1",
                "agent_url": "http://client.example:9870",
                "status": {"ok": True},
                "completed_jobs": [
                    {
                        "job_id": job_id,
                        "result": {
                            "name": "ping",
                            "source": "client",
                            "target": "127.0.0.1",
                            "success": True,
                            "metrics": {"packet_loss_pct": 0.0, "rtt_avg_ms": 10.0, "rtt_p95_ms": 12.0, "jitter_ms": 1.0},
                            "samples": [],
                            "error": None,
                            "started_at": None,
                            "duration_ms": 2.0,
                            "metadata": {"path_label": "client_to_relay"},
                        },
                    }
                ],
            },
        )
        assert second.status_code == 200
        assert runtime.store.get_job(job_id)["status"] == "completed"


def test_public_dashboard_returns_paths_without_internal_fields(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        seed_dashboard_data(client)
        response = client.get("/api/v1/public-dashboard?time_range=7d")
        assert response.status_code == 200
        payload = response.json()
        assert payload["paths"]
        assert payload["summary"]["active_alerts"] >= 1
        assert "agent_url" not in payload["nodes"][0]


def test_admin_analytics_routes_require_login(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        endpoints = [
            "/api/v1/admin/filters",
            "/api/v1/admin/overview",
            "/api/v1/admin/timeseries",
            "/api/v1/admin/path-health",
            "/api/v1/admin/runs",
            "/api/v1/admin/alerts",
        ]
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401


def test_admin_analytics_endpoints_and_alert_actions(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        run_id = seed_dashboard_data(client)

        filters = client.get("/api/v1/admin/filters")
        assert filters.status_code == 200
        assert "client_to_relay" in filters.json()["paths"]

        overview = client.get("/api/v1/admin/overview?time_range=24h")
        assert overview.status_code == 200
        assert overview.json()["kpis"]["active_alerts"] >= 1

        timeseries = client.get("/api/v1/admin/timeseries?time_range=24h&metric_name=connect_avg_ms")
        assert timeseries.status_code == 200
        assert timeseries.json()["metric_name"] == "connect_avg_ms"
        assert timeseries.json()["series"]

        path_health = client.get("/api/v1/admin/path-health?time_range=24h&path_label=client_to_mc_public")
        assert path_health.status_code == 200
        assert path_health.json()["paths"][0]["path_label"] == "client_to_mc_public"

        runs = client.get("/api/v1/admin/runs?time_range=24h&run_kind=full")
        assert runs.status_code == 200
        assert runs.json()["items"][0]["run_id"] == run_id

        run_detail = client.get(f"/api/v1/admin/runs/{run_id}")
        assert run_detail.status_code == 200
        assert run_detail.json()["threshold_findings"]
        assert run_detail.json()["probes"]

        alerts = client.get("/api/v1/admin/alerts?time_range=24h")
        assert alerts.status_code == 200
        items = alerts.json()["items"]
        assert items
        alert_id = items[0]["id"]

        ack = client.post(f"/api/v1/admin/alerts/{alert_id}/ack", json={"actor": "test-admin"})
        assert ack.status_code == 200
        assert ack.json()["alert"]["acknowledged"] is True

        silence = client.post(
            f"/api/v1/admin/alerts/{alert_id}/silence",
            json={"silenced_until": "2099-01-01T00:00:00+00:00", "reason": "maintenance", "actor": "test-admin"},
        )
        assert silence.status_code == 200
        assert silence.json()["alert"]["is_silenced"] is True
