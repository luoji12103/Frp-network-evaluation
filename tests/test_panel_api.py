from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from controller.agent_http_client import AgentHttpError
from controller.control_bridge_client import ControlBridgeError
from controller.panel_models import (
    AgentCapabilities,
    AgentEndpointReport,
    AgentIdentity,
    AgentRuntimeStatus,
    BridgeActionResponse,
    NodeUpsertRequest,
)
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


def pair_identity(node_name: str, role: str, runtime_mode: str, platform_name: str) -> AgentIdentity:
    return AgentIdentity(
        node_name=node_name,
        role=role,  # type: ignore[arg-type]
        runtime_mode=runtime_mode,  # type: ignore[arg-type]
        protocol_version="1",
        platform_name=platform_name,
        hostname=f"{node_name}-host",
        agent_version="test-agent",
    )


def create_paired_node(
    client: TestClient,
    *,
    node_name: str,
    role: str,
    runtime_mode: str,
    platform_name: str,
    configured_pull_url: str,
    advertise_url: str | None = None,
    enabled: bool = True,
    heartbeat: bool = True,
    pull_ok: bool | None = None,
) -> dict[str, object]:
    runtime = client.app.state.runtime
    store = runtime.store
    node = store.upsert_node(
        NodeUpsertRequest(
            node_name=node_name,
            role=role,  # type: ignore[arg-type]
            runtime_mode=runtime_mode,  # type: ignore[arg-type]
            configured_pull_url=configured_pull_url,
            enabled=enabled,
        )
    )
    pair_code, _ = store.create_pair_code(node["id"])
    effective_advertise = advertise_url or configured_pull_url
    store.pair_agent(
        identity=pair_identity(node_name=node_name, role=role, runtime_mode=runtime_mode, platform_name=platform_name),
        pair_code=pair_code,
        endpoint=AgentEndpointReport(listen_host="0.0.0.0", listen_port=9870, advertise_url=effective_advertise),
        capabilities=AgentCapabilities(),
    )
    if heartbeat:
        store.record_heartbeat(
            node_id=node["id"],
            endpoint=AgentEndpointReport(listen_host="0.0.0.0", listen_port=9870, advertise_url=effective_advertise),
            runtime_status=AgentRuntimeStatus(
                paired=True,
                started_at=now_iso(),
                last_heartbeat_at=now_iso(),
                last_error=None,
                environment={"platform_name": platform_name},
            ),
        )
    if pull_ok is True:
        store.update_pull_status(int(node["id"]), ok=True)
    if pull_ok is False:
        store.update_pull_status(int(node["id"]), ok=False, error="timed out", error_code="timeout")
    return node


def wait_for_release_validation(client: TestClient) -> dict[str, object]:
    for _ in range(100):
        response = client.get("/api/v1/admin/release-validation")
        assert response.status_code == 200
        payload = response.json()
        if not payload["running"]:
            return payload
        time.sleep(0.02)
    raise AssertionError("release validation did not finish in time")


def seed_dashboard_data(client: TestClient) -> str:
    runtime = client.app.state.runtime
    store = runtime.store
    node_specs = [
        ("client-1", "client", "native-windows", "windows", "http://client.example:9870"),
        ("relay-1", "relay", "docker-linux", "linux", "http://relay.example:9870"),
        ("server-1", "server", "native-macos", "macos", "http://server.example:9870"),
    ]
    for node_name, role, runtime_mode, platform_name, pull_url in node_specs:
        node = store.upsert_node(
            NodeUpsertRequest(
                node_name=node_name,
                role=role,  # type: ignore[arg-type]
                runtime_mode=runtime_mode,  # type: ignore[arg-type]
                configured_pull_url=pull_url,
                enabled=True,
            )
        )
        pair_code, _ = store.create_pair_code(node["id"])
        store.pair_agent(
            identity=pair_identity(node_name=node_name, role=role, runtime_mode=runtime_mode, platform_name=platform_name),
            pair_code=pair_code,
            endpoint=AgentEndpointReport(listen_host="0.0.0.0", listen_port=9870, advertise_url=pull_url),
            capabilities=AgentCapabilities(),
        )
        store.record_heartbeat(
            node_id=node["id"],
            endpoint=AgentEndpointReport(listen_host="0.0.0.0", listen_port=9870, advertise_url=pull_url),
            runtime_status=AgentRuntimeStatus(
                paired=True,
                started_at=now_iso(),
                last_heartbeat_at=now_iso(),
                last_error=None,
                environment={"platform_name": platform_name},
            ),
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
        assert payload["time_range"] == "24h"
        assert payload["privacy_mode"] == "role-and-path-only"
        assert payload["build"]["display_label"]
        assert response.headers["X-MC-Netprobe-Build"]


def test_public_page_includes_login_and_bilingual_toggle(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        response = client.get("/")
        assert response.status_code == 200
        body = response.text
        assert '<html lang="zh-CN">' in body
        assert 'id="localeSelect"' in body
        assert 'id="autoRefreshSelect"' in body
        assert "管理员登录" in body
        assert "公开网络质量" in body
        assert "/assets/public-dashboard.js" in body


def test_public_detail_pages_bootstrap_without_login(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        seed_dashboard_data(client)

        path_page = client.get("/public/path/client_to_relay")
        assert path_page.status_code == 200
        assert "window.__PUBLIC_PAGE__" in path_page.text
        assert "client_to_relay" in path_page.text

        role_page = client.get("/public/role/client")
        assert role_page.status_code == 200
        assert "window.__PUBLIC_PAGE__" in role_page.text
        assert "role" in role_page.text


def test_pages_and_runtime_include_build_label(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MC_NETPROBE_RELEASE_VERSION", "9.9.9")
    monkeypatch.setenv("MC_NETPROBE_BUILD_REF", "abc123def456")
    with build_client(tmp_path) as client:
        public_page = client.get("/")
        assert public_page.status_code == 200
        assert "v9.9.9 · abc123def456" in public_page.text
        assert public_page.headers["X-MC-Netprobe-Build"] == "v9.9.9+abc123def456"

        login_page = client.get("/login")
        assert login_page.status_code == 200
        assert "v9.9.9 · abc123def456" in login_page.text
        assert login_page.headers["X-MC-Netprobe-Build-Ref"] == "abc123def456"

        public_dashboard = client.get("/api/v1/public-dashboard")
        assert public_dashboard.status_code == 200
        assert public_dashboard.json()["build"]["display_label"] == "v9.9.9 · abc123def456"
        assert public_dashboard.json()["build"]["header_label"] == "v9.9.9+abc123def456"
        assert public_dashboard.headers["X-MC-Netprobe-Release-Version"] == "9.9.9"
        assert public_dashboard.headers["X-MC-Netprobe-Build-Ref"] == "abc123def456"
        assert public_dashboard.headers["X-MC-Netprobe-Build"] == "v9.9.9+abc123def456"

        login_admin(client)
        admin_page = client.get("/admin")
        assert admin_page.status_code == 200
        assert "v9.9.9 · abc123def456" in admin_page.text

        dashboard = client.get("/api/v1/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["build"]["display_label"] == "v9.9.9 · abc123def456"
        assert dashboard.json()["build"]["header_label"] == "v9.9.9+abc123def456"
        assert dashboard.headers["X-MC-Netprobe-Build"] == "v9.9.9+abc123def456"

        version = client.get("/api/v1/version")
        assert version.status_code == 200
        assert version.json()["service"] == "panel"
        assert version.json()["build"]["display_label"] == "v9.9.9 · abc123def456"
        assert version.headers["X-MC-Netprobe-Build"] == "v9.9.9+abc123def456"

        runtime = client.get("/api/v1/admin/runtime")
        assert runtime.status_code == 200
        assert runtime.json()["build"]["display_label"] == "v9.9.9 · abc123def456"
        assert runtime.json()["build"]["header_label"] == "v9.9.9+abc123def456"
        details = runtime.json()["panel"]["runtime"]["details"]
        assert details["panel_release_version"] == "9.9.9"
        assert details["panel_build_ref"] == "abc123def456"
        assert details["panel_version_label"] == "v9.9.9 · abc123def456"


def test_snapshots_include_generated_at(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        public_dashboard = client.get("/api/v1/public-dashboard")
        assert public_dashboard.status_code == 200
        assert public_dashboard.json()["generated_at"]

        login_admin(client)
        dashboard = client.get("/api/v1/dashboard")
        assert dashboard.status_code == 200
        assert dashboard.json()["generated_at"]

        runtime_payload = client.get("/api/v1/admin/runtime")
        assert runtime_payload.status_code == 200
        assert runtime_payload.json()["generated_at"]


def test_release_validation_reports_pass_warn_and_skip(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        runtime = client.app.state.runtime
        build_payload = dict(runtime._build_info)

        create_paired_node(
            client,
            node_name="client-1",
            role="client",
            runtime_mode="native-windows",
            platform_name="windows",
            configured_pull_url="http://client.example:9870",
            pull_ok=True,
        )
        create_paired_node(
            client,
            node_name="relay-1",
            role="relay",
            runtime_mode="docker-linux",
            platform_name="linux",
            configured_pull_url="http://configured-relay.example:9870",
            advertise_url="http://advertised-relay.example:9870",
            pull_ok=False,
        )
        create_paired_node(
            client,
            node_name="server-1",
            role="server",
            runtime_mode="native-macos",
            platform_name="macos",
            configured_pull_url="http://server.example:39870",
            enabled=False,
            pull_ok=None,
        )

        def fake_get_version(node: dict[str, object]) -> dict[str, object]:
            if node["node_name"] == "relay-1":
                return {
                    "service": "agent",
                    "build": {
                        "release_version": "1.1.0",
                        "build_ref": "mismatch123456",
                        "display_label": "v1.1.0 · mismatch123456",
                        "header_label": "v1.1.0+mismatch123456",
                    },
                    "started_at": now_iso(),
                    "protocol_version": "1",
                }
            return {
                "service": "agent",
                "build": build_payload,
                "started_at": now_iso(),
                "protocol_version": "1",
            }

        def fake_check_health(node: dict[str, object]) -> dict[str, object]:
            return {"ok": True, "status": "healthy", "started_at": now_iso()}

        def fake_check_status(node: dict[str, object]) -> dict[str, object]:
            return {"ok": True}

        def fake_node_runtime(node: dict[str, object]) -> BridgeActionResponse:
            return BridgeActionResponse.model_validate(
                {
                    "accepted": True,
                    "state": "running",
                    "human_summary": f"{node['node_name']} runtime synchronized",
                    "runtime": {"state": "running", "checked_at": now_iso(), "last_error": None, "details": {}},
                    "supervisor": {
                        "control_available": True,
                        "bridge_url": f"http://{node['node_name']}.bridge:9871",
                        "supervisor_state": "running",
                        "process_state": "running",
                        "pid_or_container_id": "123",
                        "log_location": "/tmp/test.log",
                        "last_error": None,
                        "checked_at": now_iso(),
                    },
                }
            )

        runtime.http.get_version = fake_get_version  # type: ignore[method-assign]
        runtime.http.check_health = fake_check_health  # type: ignore[method-assign]
        runtime.http.check_status = fake_check_status  # type: ignore[method-assign]
        runtime.control.node_runtime = fake_node_runtime  # type: ignore[method-assign]

        started = client.post("/api/v1/admin/release-validation")
        assert started.status_code == 200
        assert started.json()["running"] is True

        payload = wait_for_release_validation(client)
        assert payload["generated_at"]
        assert payload["checked_at"]
        assert payload["build"]["display_label"] == runtime._build_info["display_label"]
        assert payload["summary"]["pass"] >= 1
        assert payload["summary"]["warn"] >= 1
        assert payload["summary"]["skip"] >= 1
        assert payload["panel"]["status"] == "pass"

        node_statuses = {item["target_name"]: item["status"] for item in payload["nodes"]}
        assert node_statuses["client-1"] == "pass"
        assert node_statuses["relay-1"] == "warn"
        assert node_statuses["server-1"] == "skip"

        relay_item = next(item for item in payload["nodes"] if item["target_name"] == "relay-1")
        assert relay_item["checks"]["connectivity"]["status"] == "warn"
        assert relay_item["checks"]["build"]["status"] == "warn"
        assert relay_item["code"] in {"endpoint_mismatch", "build_mismatch", "timeout"}


def test_release_validation_reports_failures(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        runtime = client.app.state.runtime

        create_paired_node(
            client,
            node_name="client-1",
            role="client",
            runtime_mode="native-windows",
            platform_name="windows",
            configured_pull_url="http://client.example:9870",
            pull_ok=True,
        )
        create_paired_node(
            client,
            node_name="relay-1",
            role="relay",
            runtime_mode="docker-linux",
            platform_name="linux",
            configured_pull_url="http://relay.example:9870",
            pull_ok=True,
        )
        server_node = create_paired_node(
            client,
            node_name="server-1",
            role="server",
            runtime_mode="native-macos",
            platform_name="macos",
            configured_pull_url="http://server.example:39870",
            heartbeat=False,
            pull_ok=False,
        )
        runtime.store.mark_push_error(int(server_node["id"]), error="Heartbeat timeout", error_code="heartbeat_timeout")

        def fake_get_version(node: dict[str, object]) -> dict[str, object]:
            return {
                "service": "agent",
                "build": runtime._build_info,
                "started_at": now_iso(),
                "protocol_version": "1",
            }

        def fake_check_health(node: dict[str, object]) -> dict[str, object]:
            return {"ok": True, "status": "healthy", "started_at": now_iso()}

        def fake_check_status(node: dict[str, object]) -> dict[str, object]:
            if node["node_name"] == "client-1":
                raise AgentHttpError("legacy_status_shape", "legacy /api/v1/status payload")
            if node["node_name"] == "relay-1":
                raise AgentHttpError("protocol_mismatch", "unsupported protocol_version")
            return {"ok": True}

        def fake_node_runtime(node: dict[str, object]) -> BridgeActionResponse:
            if node["node_name"] == "server-1":
                raise ControlBridgeError("bridge_unreachable", "control bridge unreachable")
            return BridgeActionResponse.model_validate(
                {
                    "accepted": True,
                    "state": "running",
                    "human_summary": f"{node['node_name']} runtime synchronized",
                    "runtime": {"state": "running", "checked_at": now_iso(), "last_error": None, "details": {}},
                    "supervisor": {
                        "control_available": True,
                        "bridge_url": f"http://{node['node_name']}.bridge:9871",
                        "supervisor_state": "running",
                        "process_state": "running",
                        "pid_or_container_id": "123",
                        "log_location": "/tmp/test.log",
                        "last_error": None,
                        "checked_at": now_iso(),
                    },
                }
            )

        runtime.http.get_version = fake_get_version  # type: ignore[method-assign]
        runtime.http.check_health = fake_check_health  # type: ignore[method-assign]
        runtime.http.check_status = fake_check_status  # type: ignore[method-assign]
        runtime.control.node_runtime = fake_node_runtime  # type: ignore[method-assign]

        client.post("/api/v1/admin/release-validation")
        payload = wait_for_release_validation(client)

        assert payload["summary"]["fail"] >= 3
        issues = {item["target_name"]: item for item in payload["issues"]}
        assert issues["client-1"]["code"] == "legacy_status_shape"
        assert issues["relay-1"]["code"] == "protocol_mismatch"
        assert issues["server-1"]["code"] in {"bridge_unreachable", "timeout"}

        server_item = next(item for item in payload["nodes"] if item["target_name"] == "server-1")
        assert server_item["checks"]["control_bridge"]["status"] == "fail"
        assert server_item["checks"]["connectivity"]["status"] == "fail"


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
        assert '<html lang="zh-CN">' in page.text
        assert "保存全局配置" in page.text
        assert 'id="autoRefreshSelect"' in page.text
        assert 'id="filtersSummary"' in page.text
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
                "configured_pull_url": "http://relay.example:9870",
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
                "pair_code": pair_payload["pair_code"],
                "identity": pair_identity("relay-1", "relay", "docker-linux", "linux").model_dump(),
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://relay.example:9870",
                },
                "capabilities": {"pull_http": True, "heartbeat_queue": True, "result_lookup": True},
            },
        )
        assert paired.status_code == 200
        token = paired.json()["node_token"]
        assert token
        assert paired.json()["identity"]["protocol_version"] == "1"

        heartbeat = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://relay.example:9870",
                },
                "runtime_status": {
                    "paired": True,
                    "started_at": now_iso(),
                    "last_heartbeat_at": None,
                    "last_error": None,
                    "environment": {"uptime_sec": 10},
                },
                "completed_jobs": [],
            },
        )
        assert heartbeat.status_code == 200
        assert heartbeat.json()["jobs"] == []

        stored_node = client.get(f"/api/v1/nodes/{node['id']}").json()
        assert stored_node["endpoints"]["configured_pull_url"] == "http://relay.example:9870"
        assert stored_node["endpoints"]["advertised_pull_url"] == "http://relay.example:9870"
        assert stored_node["connectivity"]["push"]["state"] == "ok"

def test_node_connectivity_diagnostic_surfaces_endpoint_mismatch(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        node = client.post(
            "/api/v1/nodes",
            json={
                "node_name": "server-1",
                "role": "server",
                "runtime_mode": "native-macos",
                "configured_pull_url": "http://configured.example:39870",
                "enabled": True,
            },
        ).json()["node"]
        pair = client.post(f"/api/v1/nodes/{node['id']}/pair-code").json()
        paired = client.post(
            "/api/v1/agents/pair",
            json={
                "pair_code": pair["pair_code"],
                "identity": pair_identity("server-1", "server", "native-macos", "macos").model_dump(),
                "endpoint": {
                    "listen_host": "100.100.0.8",
                    "listen_port": 39870,
                    "advertise_url": "http://100.100.0.8:39870",
                },
                "capabilities": AgentCapabilities().model_dump(),
            },
        )
        assert paired.status_code == 200
        token = paired.json()["node_token"]

        heartbeat = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "endpoint": {
                    "listen_host": "100.100.0.8",
                    "listen_port": 39870,
                    "advertise_url": "http://100.100.0.8:39870",
                },
                "runtime_status": {
                    "paired": True,
                    "started_at": now_iso(),
                    "last_heartbeat_at": now_iso(),
                    "last_error": None,
                    "environment": {"platform_name": "macos"},
                },
                "completed_jobs": [],
            },
        )
        assert heartbeat.status_code == 200

        stored = client.get(f"/api/v1/nodes/{node['id']}").json()
        assert stored["status"] == "push-only"
        assert stored["connectivity"]["endpoint_mismatch"] is True
        assert stored["connectivity"]["diagnostic_code"] == "endpoint_mismatch"
        assert stored["connectivity"]["push"]["code"] is None
        assert stored["connectivity"]["pull"]["code"] is None
        assert "differs from the agent-advertised URL" in stored["connectivity"]["summary"]
        assert "configured_pull_url" in stored["connectivity"]["recommended_step"]

        runtime_payload = client.get("/api/v1/admin/runtime").json()
        assert any(
            item["kind"] == "node"
            and item["target_name"] == "server-1"
            and item["code"] == "endpoint_mismatch"
            for item in runtime_payload["attention"]["items"]
        )


def test_legacy_agent_status_shape_is_classified_in_pull_diagnostics(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        runtime = client.app.state.runtime
        node = client.post(
            "/api/v1/nodes",
            json={
                "node_name": "server-1",
                "role": "server",
                "runtime_mode": "native-macos",
                "configured_pull_url": "http://100.100.0.8:39870",
                "enabled": True,
            },
        ).json()["node"]
        pair = client.post(f"/api/v1/nodes/{node['id']}/pair-code").json()
        paired = client.post(
            "/api/v1/agents/pair",
            json={
                "pair_code": pair["pair_code"],
                "identity": pair_identity("server-1", "server", "native-macos", "macos").model_dump(),
                "endpoint": {
                    "listen_host": "100.100.0.8",
                    "listen_port": 39870,
                    "advertise_url": "http://100.100.0.8:39870",
                },
                "capabilities": AgentCapabilities().model_dump(),
            },
        )
        token = paired.json()["node_token"]
        heartbeat = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "endpoint": {
                    "listen_host": "100.100.0.8",
                    "listen_port": 39870,
                    "advertise_url": "http://100.100.0.8:39870",
                },
                "runtime_status": {
                    "paired": True,
                    "started_at": now_iso(),
                    "last_heartbeat_at": now_iso(),
                    "last_error": None,
                    "environment": {"platform_name": "macos"},
                },
                "completed_jobs": [],
            },
        )
        assert heartbeat.status_code == 200

        def fake_request(node: dict[str, object], method: str, path: str, json_body=None, timeout_sec=None) -> dict[str, object]:
            assert method == "GET"
            assert path == "/api/v1/status"
            return {
                "node_name": "server-1",
                "role": "server",
                "runtime_mode": "native-macos",
                "panel_url": "http://panel.example:8765",
                "listen_host": "100.100.0.8",
                "listen_port": 39870,
                "advertise_url": "http://100.100.0.8:39870",
                "paired": True,
                "started_at": now_iso(),
                "last_heartbeat_at": now_iso(),
                "last_error": None,
                "environment": {"platform_name": "macos"},
            }

        runtime.http._request = fake_request  # type: ignore[method-assign]
        runtime.run_maintenance_cycle(force_runtime_sync=False)

        stored = client.get(f"/api/v1/nodes/{node['id']}").json()
        assert stored["status"] == "push-only"
        assert stored["connectivity"]["diagnostic_code"] == "legacy_status_shape"
        assert stored["connectivity"]["pull"]["code"] == "legacy_status_shape"
        assert "legacy /api/v1/status payload" in stored["connectivity"]["pull"]["error"]
        assert "structured status contract" in stored["connectivity"]["recommended_step"]
        assert stored["runtime"]["details"]["suggested_action"]["kind"] == "open_node"

        runtime_payload = client.get("/api/v1/admin/runtime").json()
        node_item = next(
            item
            for item in runtime_payload["attention"]["items"]
            if item["kind"] == "node" and item["target_name"] == "server-1"
        )
        assert node_item["code"] == "legacy_status_shape"
        assert node_item["suggested_action"]["kind"] == "open_node"


def test_status_protocol_mismatch_is_classified_in_pull_diagnostics(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        runtime = client.app.state.runtime
        node = client.post(
            "/api/v1/nodes",
            json={
                "node_name": "relay-1",
                "role": "relay",
                "runtime_mode": "docker-linux",
                "configured_pull_url": "http://relay.example:9870",
                "enabled": True,
            },
        ).json()["node"]
        pair = client.post(f"/api/v1/nodes/{node['id']}/pair-code").json()
        paired = client.post(
            "/api/v1/agents/pair",
            json={
                "pair_code": pair["pair_code"],
                "identity": pair_identity("relay-1", "relay", "docker-linux", "linux").model_dump(),
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://relay.example:9870",
                },
                "capabilities": AgentCapabilities().model_dump(),
            },
        )
        token = paired.json()["node_token"]
        heartbeat = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://relay.example:9870",
                },
                "runtime_status": {
                    "paired": True,
                    "started_at": now_iso(),
                    "last_heartbeat_at": now_iso(),
                    "last_error": None,
                    "environment": {"platform_name": "linux"},
                },
                "completed_jobs": [],
            },
        )
        assert heartbeat.status_code == 200

        def fake_request(node: dict[str, object], method: str, path: str, json_body=None, timeout_sec=None) -> dict[str, object]:
            assert method == "GET"
            assert path == "/api/v1/status"
            return {
                "identity": {
                    "node_name": "relay-1",
                    "role": "relay",
                    "runtime_mode": "docker-linux",
                    "protocol_version": "999",
                    "platform_name": "linux",
                    "hostname": "relay-1-host",
                    "agent_version": "legacy-agent",
                },
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://relay.example:9870",
                },
                "capabilities": {
                    "pull_http": True,
                    "heartbeat_queue": True,
                    "result_lookup": True,
                },
                "runtime_status": {
                    "paired": True,
                    "started_at": now_iso(),
                    "last_heartbeat_at": now_iso(),
                    "last_error": None,
                    "environment": {"platform_name": "linux"},
                },
            }

        runtime.http._request = fake_request  # type: ignore[method-assign]
        runtime.run_maintenance_cycle(force_runtime_sync=False)

        stored = client.get(f"/api/v1/nodes/{node['id']}").json()
        assert stored["status"] == "push-only"
        assert stored["connectivity"]["diagnostic_code"] == "protocol_mismatch"
        assert stored["connectivity"]["pull"]["code"] == "protocol_mismatch"
        assert "Unsupported agent protocol_version '999'" in stored["connectivity"]["pull"]["error"]
        assert "Align panel and agent protocol versions" in stored["connectivity"]["recommended_step"]
        assert stored["runtime"]["details"]["suggested_action"]["kind"] == "open_node"


def test_active_run_is_exposed_in_runtime_payload_and_run_conflict(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        store = client.app.state.runtime.store
        run_id = store.create_run("baseline", "test")
        store.record_run_event(run_id, "phase_started", "baseline phase started", {"phase": "baseline"})

        runtime_payload = client.get("/api/v1/admin/runtime").json()
        assert runtime_payload["active_run"]["run_id"] == run_id
        assert runtime_payload["active_run"]["progress"]["active_phase"] == "baseline"
        assert any(item["kind"] == "run" and item["run_id"] == run_id for item in runtime_payload["attention"]["items"])

        conflict = client.post(
            "/api/v1/runs",
            json={"run_kind": "full", "source": "admin-ui"},
        )
        assert conflict.status_code == 409
        detail = conflict.json()["detail"]
        assert detail["active_run"]["run_id"] == run_id
        assert detail["active_run"]["progress"]["active_phase"] == "baseline"
        assert detail["suggested_action"]["kind"] == "open_run"
        assert detail["suggested_action"]["run_id"] == run_id
        assert "follow progress" in detail["recommended_step"]


def test_active_run_attention_surfaces_queued_job_diagnostic(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        store = client.app.state.runtime.store
        store.upsert_node(
            NodeUpsertRequest(
                node_name="relay-1",
                role="relay",
                runtime_mode="docker-linux",
                configured_pull_url="http://relay.example:9870",
                enabled=True,
            )
        )
        run_id = store.create_run("baseline", "test")
        store.record_run_event(run_id, "phase_started", "baseline phase started", {"phase": "baseline"})
        store.record_run_event(
            run_id,
            "queue_timeout",
            "ping queued job timed out on relay-1",
            {
                "job_id": 42,
                "task": "ping",
                "node_name": "relay-1",
                "queue_status": "pending",
                "error": "Timed out waiting for job 42",
                "error_code": "queue_not_leased",
                "job": {
                    "job_id": 42,
                    "task": "ping",
                    "status": "pending",
                    "lease_state": "not-leased",
                },
            },
        )

        runtime_payload = client.get("/api/v1/admin/runtime").json()
        run_item = next(item for item in runtime_payload["attention"]["items"] if item["kind"] == "run")
        assert run_item["severity"] == "warning"
        assert run_item["code"] == "queue_not_leased"
        assert "queue job 42 pending" in run_item["summary"]
        assert run_item["suggested_action"]["kind"] == "open_run"
        assert run_item["suggested_action"]["run_id"] == run_id

        queue_item = next(item for item in runtime_payload["attention"]["items"] if item["kind"] == "run-queue")
        assert queue_item["run_id"] == run_id
        assert queue_item["code"] == "queue_not_leased"
        assert "Job 42" in queue_item["summary"]
        assert queue_item["suggested_action"]["kind"] == "open_node"

        relay_node = next(item for item in runtime_payload["nodes"] if item["node_name"] == "relay-1")
        assert relay_node["run_attention"]["run_id"] == run_id
        assert relay_node["run_attention"]["node_id"] == relay_node["id"]
        assert relay_node["run_attention"]["suggested_action"]["kind"] == "open_run"
        assert "job 42" in relay_node["run_attention"]["summary"]
        assert relay_node["runtime"]["details"]["active_run_id"] == run_id
        assert "job 42" in (relay_node["runtime"]["details"]["operator_summary"] or "")
        assert relay_node["runtime"]["details"]["suggested_action"]["kind"] == "open_run"
        assert "never reached the node" in (relay_node["run_attention"]["recommended_step"] or "")

        detail = client.get(f"/api/v1/admin/runs/{run_id}").json()
        assert detail["progress"]["current_blocker"]["code"] == "queue_not_leased"
        assert detail["progress"]["current_blocker"]["kind"] == "queue"
        assert detail["progress"]["current_blocker"]["suggested_action"]["kind"] == "open_node"
        assert detail["progress"]["current_blocker"]["node_id"] == relay_node["id"]
        assert detail["progress"]["latest_queue_job"]["node_id"] == relay_node["id"]
        assert detail["progress"]["headline_severity"] == "warning"
        assert "never reached the node" in (detail["progress"]["recommended_step"] or "")
        events = client.get(f"/api/v1/admin/runs/{run_id}/events").json()["items"]
        queue_event = next(item for item in events if item["event_kind"] == "queue_timeout")
        assert queue_event["node_id"] == relay_node["id"]


def test_active_run_attention_ignores_stale_queue_failure_after_newer_success(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        store = client.app.state.runtime.store
        store.upsert_node(
            NodeUpsertRequest(
                node_name="relay-1",
                role="relay",
                runtime_mode="docker-linux",
                configured_pull_url="http://relay.example:9870",
                enabled=True,
            )
        )
        run_id = store.create_run("baseline", "test")
        store.record_run_event(run_id, "phase_started", "baseline phase started", {"phase": "baseline"})
        store.record_run_event(
            run_id,
            "queue_timeout",
            "ping queued job timed out on relay-1",
            {
                "job_id": 42,
                "task": "ping",
                "node_name": "relay-1",
                "queue_status": "pending",
                "error": "Timed out waiting for job 42",
                "error_code": "queue_not_leased",
                "job": {
                    "job_id": 42,
                    "task": "ping",
                    "status": "pending",
                    "lease_state": "not-leased",
                },
            },
        )
        store.record_run_event(
            run_id,
            "probe_completed",
            "ping completed on relay-1 via pull",
            {
                "task": "ping",
                "node_name": "relay-1",
                "path_label": "client_to_relay",
                "transport": "pull",
                "success": True,
                "error": None,
            },
        )

        runtime_payload = client.get("/api/v1/admin/runtime").json()
        run_item = next(item for item in runtime_payload["attention"]["items"] if item["kind"] == "run")
        assert run_item["severity"] == "info"
        assert run_item["code"] is None
        assert "queue job 42" not in run_item["summary"]
        assert all(item["kind"] != "run-queue" for item in runtime_payload["attention"]["items"])

        relay_node = next(item for item in runtime_payload["nodes"] if item["node_name"] == "relay-1")
        assert "run_attention" in relay_node
        assert relay_node["run_attention"]["node_id"] == relay_node["id"]
        assert relay_node["run_attention"]["suggested_action"]["kind"] == "open_run"
        assert "last touched ping" in relay_node["run_attention"]["summary"]
        assert "last touched ping" in (relay_node["runtime"]["details"]["operator_summary"] or "")
        assert relay_node["runtime"]["details"]["suggested_action"]["kind"] == "open_run"
        assert relay_node["run_attention"]["recommended_step"] is None

        detail = client.get(f"/api/v1/admin/runs/{run_id}").json()
        assert detail["progress"]["current_blocker"] is None
        assert detail["progress"]["latest_probe"]["node_id"] == relay_node["id"]
        assert detail["progress"]["recommended_step"] is None


def test_run_detail_progress_surfaces_failure_code_and_hint(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        store = client.app.state.runtime.store
        run_id = store.create_run("baseline", "test")
        store.record_run_event(run_id, "phase_started", "baseline phase started", {"phase": "baseline"})
        store.record_run_event(
            run_id,
            "probe_completed",
            "ping completed on relay-1 via pull-error",
            {
                "task": "ping",
                "node_name": "relay-1",
                "path_label": "client_to_relay",
                "transport": "pull-error",
                "success": False,
                "error": "timeout: request to http://relay.example/api/v1/jobs/run timed out",
                "error_code": "timeout",
            },
        )

        detail = client.get(f"/api/v1/admin/runs/{run_id}").json()
        assert detail["progress"]["last_failure_code"] == "timeout"
        assert "timed out" in detail["progress"]["last_failure_message"]
        assert "agent listener" in (detail["progress"]["recommended_step"] or "")


def test_pair_rejects_unsupported_protocol_version(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        node = client.post(
            "/api/v1/nodes",
            json={
                "node_name": "server-1",
                "role": "server",
                "runtime_mode": "native-macos",
                "configured_pull_url": "http://server.example:9870",
                "enabled": True,
            },
        ).json()["node"]
        pair_code = client.post(f"/api/v1/nodes/{node['id']}/pair-code").json()["pair_code"]

        response = client.post(
            "/api/v1/agents/pair",
            json={
                "pair_code": pair_code,
                "identity": {
                    "node_name": "server-1",
                    "role": "server",
                    "runtime_mode": "native-macos",
                    "protocol_version": "999",
                    "platform_name": "macos",
                    "hostname": "server-host",
                    "agent_version": "future",
                },
                "endpoint": {"listen_host": "100.100.0.8", "listen_port": 39870, "advertise_url": "http://100.100.0.8:39870"},
                "capabilities": {"pull_http": True, "heartbeat_queue": True, "result_lookup": True},
            },
        )
        assert response.status_code == 409
        assert "Unsupported protocol_version" in response.json()["detail"]


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
                "configured_pull_url": "http://client.example:9870",
                "enabled": True,
            },
        ).json()["node"]
        pair_code = client.post(f"/api/v1/nodes/{node['id']}/pair-code").json()["pair_code"]
        token = client.post(
            "/api/v1/agents/pair",
            json={
                "pair_code": pair_code,
                "identity": pair_identity("client-1", "client", "native-windows", "windows").model_dump(),
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://client.example:9870",
                },
                "capabilities": {"pull_http": True, "heartbeat_queue": True, "result_lookup": True},
            },
        ).json()["node_token"]

        run_id = runtime.store.create_run("baseline", "test")
        job_id = runtime.store.enqueue_job(
            node_id=node["id"],
            run_id=run_id,
            task="ping",
            payload={"host": "127.0.0.1", "count": 2, "timeout_sec": 1.0},
            timeout_sec=3.0,
        )

        first = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://client.example:9870",
                },
                "runtime_status": {
                    "paired": True,
                    "started_at": now_iso(),
                    "last_heartbeat_at": None,
                    "last_error": None,
                    "environment": {"ok": True},
                },
                "completed_jobs": [],
            },
        )
        assert first.status_code == 200
        leased_job = first.json()["jobs"][0]
        assert leased_job["job_id"] == job_id
        assert leased_job["timeout_sec"] == 3.0
        assert leased_job["lease_expires_at"]

        second = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://client.example:9870",
                },
                "runtime_status": {
                    "paired": True,
                    "started_at": now_iso(),
                    "last_heartbeat_at": None,
                    "last_error": None,
                    "environment": {"ok": True},
                },
                "completed_jobs": [
                    {
                        "job_id": job_id,
                        "run_id": run_id,
                        "task": "ping",
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

        detail = client.get(f"/api/v1/admin/runs/{run_id}")
        assert detail.status_code == 200
        progress = detail.json()["progress"]
        assert progress["latest_queue_job"]["status"] == "completed"
        assert progress["latest_queue_job"]["job_id"] == job_id
        assert progress["latest_queue_job"]["task"] == "ping"

        events = client.get(f"/api/v1/admin/runs/{run_id}/events")
        assert events.status_code == 200
        items = events.json()["items"]
        event_kinds = [item["event_kind"] for item in items]
        assert "queue_leased" in event_kinds
        assert "queue_completed" in event_kinds
        completed = next(item for item in items if item["event_kind"] == "queue_completed")
        assert completed["severity"] == "info"
        assert "job" in (completed["summary"] or "")


def test_late_queue_completion_is_recorded_as_ignored(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        runtime = client.app.state.runtime
        node = client.post(
            "/api/v1/nodes",
            json={
                "node_name": "client-1",
                "role": "client",
                "runtime_mode": "native-windows",
                "configured_pull_url": "http://client.example:9870",
                "enabled": True,
            },
        ).json()["node"]
        pair_code = client.post(f"/api/v1/nodes/{node['id']}/pair-code").json()["pair_code"]
        token = client.post(
            "/api/v1/agents/pair",
            json={
                "pair_code": pair_code,
                "identity": pair_identity("client-1", "client", "native-windows", "windows").model_dump(),
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://client.example:9870",
                },
                "capabilities": {"pull_http": True, "heartbeat_queue": True, "result_lookup": True},
            },
        ).json()["node_token"]

        run_id = runtime.store.create_run("baseline", "test")
        job_id = runtime.store.enqueue_job(
            node_id=node["id"],
            run_id=run_id,
            task="ping",
            payload={"host": "127.0.0.1", "count": 2, "timeout_sec": 1.0},
            timeout_sec=3.0,
        )
        runtime.store.fail_job(job_id, "Timed out waiting for job result")

        response = client.post(
            "/api/v1/agents/heartbeat",
            headers={"X-Node-Token": token},
            json={
                "endpoint": {
                    "listen_host": "0.0.0.0",
                    "listen_port": 9870,
                    "advertise_url": "http://client.example:9870",
                },
                "runtime_status": {
                    "paired": True,
                    "started_at": now_iso(),
                    "last_heartbeat_at": None,
                    "last_error": None,
                    "environment": {"ok": True},
                },
                "completed_jobs": [
                    {
                        "job_id": job_id,
                        "run_id": run_id,
                        "task": "ping",
                        "result": {
                            "name": "ping",
                            "source": "client",
                            "target": "127.0.0.1",
                            "success": True,
                            "metrics": {"packet_loss_pct": 0.0},
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
        assert response.status_code == 200

        detail = client.get(f"/api/v1/admin/runs/{run_id}")
        assert detail.status_code == 200
        progress = detail.json()["progress"]
        assert progress["latest_queue_job"]["status"] == "completion_ignored"

        events = client.get(f"/api/v1/admin/runs/{run_id}/events")
        items = events.json()["items"]
        event_kinds = [item["event_kind"] for item in items]
        assert "queue_completion_ignored" in event_kinds
        ignored = next(item for item in items if item["event_kind"] == "queue_completion_ignored")
        assert ignored["severity"] == "warning"
        assert ignored["code"] in {None, "queue_failed"}


def test_public_dashboard_returns_paths_without_internal_fields(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        seed_dashboard_data(client)
        response = client.get("/api/v1/public-dashboard?time_range=7d")
        assert response.status_code == 200
        payload = response.json()
        assert payload["paths"]
        assert payload["summary"]["active_alerts"] >= 1
        assert "endpoints" not in payload["nodes"][0]
        assert "node_name" not in payload["nodes"][0]
        assert payload["time_range"] == "7d"
        assert payload["privacy_mode"] == "role-and-path-only"
        assert payload["nodes"][0]["connectivity"]["push"]["state"] in {"ok", "unknown", "error"}
        assert payload["alerts"][0]["path_id"] in {"client_to_relay", "relay_to_server", "client_to_mc_public", "client_to_iperf_public", None}


def test_public_path_health_and_timeseries_are_anonymous_and_sanitized(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        seed_dashboard_data(client)

        path_health = client.get("/api/v1/public/path-health?time_range=30d&path_id=client_to_relay")
        assert path_health.status_code == 200
        path_payload = path_health.json()
        assert path_payload["time_range"] == "30d"
        assert path_payload["privacy_mode"] == "role-and-path-only"
        assert path_payload["path"]["path_id"] == "client_to_relay"
        assert "node_name" not in path_payload["path"]
        assert "control_bridge_url" not in path_payload["path"]

        timeseries = client.get("/api/v1/public/timeseries?scope_kind=path&scope_id=client_to_relay&metric_group=latency&time_range=24h")
        assert timeseries.status_code == 200
        series_payload = timeseries.json()
        assert series_payload["scope_kind"] == "path"
        assert series_payload["scope_id"] == "client_to_relay"
        assert series_payload["metric_group"] == "latency"
        assert series_payload["privacy_mode"] == "role-and-path-only"
        assert series_payload["series"]
        first_series = series_payload["series"][0]
        assert "runtime" not in first_series
        assert "supervisor" not in first_series
        assert "node_name" not in first_series


def test_public_role_timeseries_filters_allowed_scope(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        seed_dashboard_data(client)
        response = client.get("/api/v1/public/timeseries?scope_kind=role&scope_id=client&metric_group=system&time_range=24h")
        assert response.status_code == 200
        payload = response.json()
        assert payload["scope_kind"] == "role"
        assert payload["scope_id"] == "client"
        assert payload["metric_group"] == "system"
        assert payload["series"]

        invalid = client.get("/api/v1/public/timeseries?scope_kind=role&scope_id=client&metric_group=secret&time_range=24h")
        assert invalid.status_code == 400


def test_admin_analytics_routes_require_login(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        endpoints = [
            "/api/v1/admin/filters",
            "/api/v1/admin/runtime",
            "/api/v1/admin/actions",
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
