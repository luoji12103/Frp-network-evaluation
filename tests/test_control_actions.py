from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from controller.panel_models import (
    AgentCapabilities,
    AgentEndpointReport,
    AgentIdentity,
    BridgeActionResponse,
    RuntimeSummary,
    SupervisorSummary,
)
from controller.webui import create_app
from probes.common import RunResult, now_iso


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


class FakeControlClient:
    def ensure_panel_bridge_token(self) -> str:
        return "panel-token"

    def node_runtime(self, node: dict[str, object]) -> BridgeActionResponse:
        bridge_url = node.get("endpoints", {}).get("control_bridge_url") if isinstance(node.get("endpoints"), dict) else None
        return BridgeActionResponse(
            state="running",
            human_summary="node runtime synced",
            runtime=RuntimeSummary(state="running", checked_at=now_iso()),
            supervisor=SupervisorSummary(
                control_available=True,
                bridge_url=str(bridge_url) if bridge_url else None,
                supervisor_state="running",
                process_state="running",
                pid_or_container_id="1234",
                log_location="docker://node",
                checked_at=now_iso(),
            ),
        )

    def node_action(self, node: dict[str, object], action: str, tail_lines: int | None = None) -> BridgeActionResponse:
        return BridgeActionResponse(
            accepted=action in {"restart", "stop", "start"},
            state="running" if action != "stop" else "stopped",
            human_summary=f"{action} handled for {node.get('node_name')}",
            runtime=RuntimeSummary(state="running" if action != "stop" else "stopped", checked_at=now_iso()),
            supervisor=SupervisorSummary(
                control_available=True,
                bridge_url=node.get("endpoints", {}).get("control_bridge_url") if isinstance(node.get("endpoints"), dict) else None,
                supervisor_state="running" if action != "stop" else "stopped",
                process_state="running" if action != "stop" else "stopped",
                pid_or_container_id="1234",
                log_location="docker://node",
                checked_at=now_iso(),
            ),
            log_excerpt=["line-a", "line-b"] if action == "tail_log" else [],
        )

    def panel_runtime(self) -> BridgeActionResponse:
        return BridgeActionResponse(
            state="running",
            human_summary="panel runtime synced",
            runtime=RuntimeSummary(state="running", checked_at=now_iso()),
            supervisor=SupervisorSummary(
                control_available=True,
                bridge_url="http://panel-control-bridge:8877",
                supervisor_state="running",
                process_state="running",
                pid_or_container_id="panel-1",
                log_location="docker://panel",
                checked_at=now_iso(),
            ),
        )

    def panel_action(self, action: str, tail_lines: int | None = None) -> BridgeActionResponse:
        return BridgeActionResponse(
            accepted=action in {"restart", "stop"},
            state="running" if action != "stop" else "stopped",
            human_summary=f"panel {action} accepted",
            runtime=RuntimeSummary(state="running" if action != "stop" else "stopped", checked_at=now_iso()),
            supervisor=SupervisorSummary(
                control_available=True,
                bridge_url="http://panel-control-bridge:8877",
                supervisor_state="running" if action != "stop" else "stopped",
                process_state="running" if action != "stop" else "stopped",
                pid_or_container_id="panel-1",
                log_location="docker://panel",
                checked_at=now_iso(),
            ),
        )


def seed_paired_node(client: TestClient) -> dict[str, object]:
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
    pair_payload = client.post(f"/api/v1/nodes/{node['id']}/pair-code").json()
    client.post(
        "/api/v1/agents/pair",
        json={
            "pair_code": pair_payload["pair_code"],
            "identity": pair_identity("relay-1", "relay", "docker-linux", "linux").model_dump(),
            "endpoint": {
                "listen_host": "0.0.0.0",
                "listen_port": 9870,
                "advertise_url": "http://relay.example:9870",
                "control_listen_port": 9871,
                "control_url": "http://relay.example:9871",
            },
            "capabilities": AgentCapabilities().model_dump(),
        },
    )
    return node


def test_admin_runtime_and_node_action_flow(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        node = seed_paired_node(client)
        runtime = client.app.state.runtime
        runtime.control = FakeControlClient()

        runtime_response = client.get("/api/v1/admin/runtime")
        assert runtime_response.status_code == 200
        assert runtime_response.json()["nodes"][0]["endpoints"]["control_bridge_url"] == "http://relay.example:9871"

        queued = client.post(f"/api/v1/admin/nodes/{node['id']}/actions", json={"action": "sync_runtime", "actor": "admin-ui"})
        assert queued.status_code == 200
        assert queued.json()["queued"] is True

        runtime.run_maintenance_cycle(force_runtime_sync=True)

        actions = client.get("/api/v1/admin/actions").json()["items"]
        assert actions[0]["status"] == "completed"
        assert "sync_runtime" in actions[0]["action"]

        stored_node = client.get(f"/api/v1/nodes/{node['id']}").json()
        assert stored_node["runtime"]["state"] == "running"
        assert stored_node["supervisor"]["control_available"] is True


def test_panel_actions_require_confirmation_and_update_scheduler(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        runtime = client.app.state.runtime
        runtime.control = FakeControlClient()

        first = client.post("/api/v1/admin/panel/actions", json={"action": "pause_scheduler", "actor": "admin-ui"})
        assert first.status_code == 200
        assert first.json()["confirmation_required"] is True

        confirmed = client.post(
            "/api/v1/admin/panel/actions",
            json={
                "action": "pause_scheduler",
                "actor": "admin-ui",
                "confirmation_token": first.json()["confirmation_token"],
            },
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["queued"] is True

        runtime.run_maintenance_cycle(force_runtime_sync=True)

        runtime_payload = client.get("/api/v1/admin/runtime").json()["panel"]
        assert runtime_payload["runtime"]["details"]["scheduler_paused"] is True


def test_run_events_endpoint_returns_timeline(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        store = client.app.state.runtime.store
        run_id = store.create_run("baseline", "test")
        store.record_run_event(run_id, "probe_dispatched", "probe dispatched", {"task": "ping"})
        store.finish_run(run_id=run_id, status="completed", run_result=RunResult(
            run_id=run_id,
            project="mc-netprobe-monitor",
            started_at=now_iso(),
            finished_at=now_iso(),
            environment={},
            probes=[],
            threshold_findings=[],
            conclusion=[],
        ))

        response = client.get(f"/api/v1/admin/runs/{run_id}/events")
        assert response.status_code == 200
        kinds = [item["event_kind"] for item in response.json()["items"]]
        assert "run_created" in kinds
        assert "probe_dispatched" in kinds
