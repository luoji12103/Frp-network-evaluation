from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from controller.webui import create_app


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
        assert '"zh-CN"' in body
        assert '"en-US"' in body
        assert "Admin Login" in body
        assert "管理员登录" in body


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
        assert "保存全局配置" in page.text

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
