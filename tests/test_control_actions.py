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
from controller.control_bridge_client import ControlBridgeError
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


class FailingBridgeControlClient(FakeControlClient):
    def node_runtime(self, node: dict[str, object]) -> BridgeActionResponse:
        raise ControlBridgeError("connect_error", "could not connect to http://relay.example:9871")

    def node_action(self, node: dict[str, object], action: str, tail_lines: int | None = None) -> BridgeActionResponse:
        raise ControlBridgeError("connect_error", "could not connect to http://relay.example:9871")

    def panel_runtime(self) -> BridgeActionResponse:
        raise ControlBridgeError("connect_error", "could not connect to http://panel-control-bridge:8877")

    def panel_action(self, action: str, tail_lines: int | None = None) -> BridgeActionResponse:
        raise ControlBridgeError("connect_error", "could not connect to http://panel-control-bridge:8877")


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
        node_runtime = runtime_response.json()["nodes"][0]
        assert node_runtime["endpoints"]["control_bridge_url"] == "http://relay.example:9871"
        assert node_runtime["runtime"]["details"]["available_actions"] == [
            "sync_runtime",
            "tail_log",
            "start",
            "restart",
            "stop",
        ]
        assert "pull checks are failing" in (node_runtime["runtime"]["details"]["operator_summary"] or "")
        assert node_runtime["runtime"]["details"]["suggested_action"]["kind"] == "sync_runtime"
        assert node_runtime["runtime"]["details"]["suggested_action"]["target_id"] == node["id"]

        queued = client.post(f"/api/v1/admin/nodes/{node['id']}/actions", json={"action": "sync_runtime", "actor": "admin-ui"})
        assert queued.status_code == 200
        assert queued.json()["queued"] is True

        runtime.run_maintenance_cycle(force_runtime_sync=True)

        actions = client.get("/api/v1/admin/actions").json()["items"]
        assert actions[0]["status"] == "completed"
        assert "sync_runtime" in actions[0]["action"]
        assert actions[0]["target_name"] == "relay-1"
        assert actions[0]["has_runtime_snapshot"] is True
        assert actions[0]["active"] is False
        assert actions[0]["severity"] == "info"
        assert "handled for relay-1" in (actions[0]["summary"] or "")
        assert actions[0]["target_runtime_state"] == "running"
        assert "pull checks are failing" in (actions[0]["target_operator_summary"] or "")

        stored_node = client.get(f"/api/v1/nodes/{node['id']}").json()
        assert stored_node["runtime"]["state"] == "running"
        assert stored_node["supervisor"]["control_available"] is True
        assert stored_node["runtime"]["details"]["active_action_id"] is None


def test_node_actions_are_hidden_when_control_bridge_runtime_is_unreachable(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        node = seed_paired_node(client)
        runtime = client.app.state.runtime
        runtime.control = FailingBridgeControlClient()

        runtime_payload = client.get("/api/v1/admin/runtime").json()
        node_runtime = next(item for item in runtime_payload["nodes"] if item["id"] == node["id"])
        assert node_runtime["supervisor"]["control_available"] is False
        assert node_runtime["runtime"]["details"]["bridge_error_code"] == "connect_error"
        assert node_runtime["runtime"]["details"]["available_actions"] == []
        assert "unreachable" in (node_runtime["runtime"]["details"]["readonly_reason"] or "")
        assert any(
            item["kind"] == "node-control"
            and item["target_name"] == "relay-1"
            and item["code"] == "connect_error"
            for item in runtime_payload["attention"]["items"]
        )

        restart = client.post(
            f"/api/v1/admin/nodes/{node['id']}/actions",
            json={"action": "restart", "actor": "admin-ui"},
        )
        assert restart.status_code == 409
        assert "unreachable" in restart.json()["detail"]


def test_node_actions_are_serialized_per_target_and_conflicts_include_active_action(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        node = seed_paired_node(client)

        first = client.post(f"/api/v1/admin/nodes/{node['id']}/actions", json={"action": "sync_runtime", "actor": "admin-ui"})
        assert first.status_code == 200
        first_action_id = first.json()["action"]["id"]

        conflict = client.post(f"/api/v1/admin/nodes/{node['id']}/actions", json={"action": "restart", "actor": "admin-ui"})
        assert conflict.status_code == 409
        detail = conflict.json()["detail"]
        assert detail["active_action"]["id"] == first_action_id
        assert detail["active_action"]["action"] == "sync_runtime"

        node_payload = client.get(f"/api/v1/nodes/{node['id']}").json()
        assert node_payload["runtime"]["details"]["active_action_id"] == first_action_id
        assert "sync_runtime" in (node_payload["runtime"]["details"]["active_action_summary"] or "")
        assert "sync_runtime" in (node_payload["runtime"]["details"]["operator_summary"] or "")
        assert node_payload["runtime"]["details"]["suggested_action"]["kind"] == "open_action"
        assert node_payload["runtime"]["details"]["suggested_action"]["action_id"] == first_action_id
        runtime_payload = client.get("/api/v1/admin/runtime").json()
        node_attention = next(item for item in runtime_payload["attention"]["items"] if item["kind"] == "node-action")
        assert node_attention["action_id"] == first_action_id
        assert "sync_runtime" in (node_attention["summary"] or "")
        assert node_attention["suggested_action"]["kind"] == "open_action"
        assert node_attention["suggested_action"]["action_id"] == first_action_id


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
        assert runtime_payload["runtime"]["details"]["active_action_id"] is None


def test_panel_actions_are_serialized_per_target(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)

        first = client.post("/api/v1/admin/panel/actions", json={"action": "sync_runtime", "actor": "admin-ui"})
        assert first.status_code == 200
        first_action_id = first.json()["action"]["id"]

        conflict = client.post("/api/v1/admin/panel/actions", json={"action": "sync_runtime", "actor": "admin-ui"})
        assert conflict.status_code == 409
        detail = conflict.json()["detail"]
        assert detail["active_action"]["id"] == first_action_id
        assert detail["active_action"]["target_name"] == "panel"

        runtime_payload = client.get("/api/v1/admin/runtime").json()["panel"]
        assert runtime_payload["runtime"]["details"]["active_action_id"] == first_action_id
        assert "sync_runtime" in (runtime_payload["runtime"]["details"]["active_action_summary"] or "")
        assert runtime_payload["runtime"]["details"]["suggested_action"]["kind"] == "open_action"
        assert runtime_payload["runtime"]["details"]["suggested_action"]["action_id"] == first_action_id
        attention_payload = client.get("/api/v1/admin/runtime").json()["attention"]["items"]
        panel_attention = next(item for item in attention_payload if item["kind"] == "panel-action")
        assert panel_attention["action_id"] == first_action_id
        assert "sync_runtime" in (panel_attention["summary"] or "")
        assert panel_attention["suggested_action"]["kind"] == "open_action"
        assert panel_attention["suggested_action"]["action_id"] == first_action_id


def test_native_panel_runtime_is_observable_without_bridge(tmp_path: Path, monkeypatch) -> None:
    log_path = tmp_path / "panel-native.log"
    log_path.write_text("line-a\nline-b\nline-c\n", encoding="utf-8")
    monkeypatch.delenv("MC_NETPROBE_PANEL_CONTROL_BRIDGE_URL", raising=False)
    monkeypatch.setenv("MC_NETPROBE_PANEL_LOG_FILE", str(log_path))

    with build_client(tmp_path) as client:
        login_admin(client)

        runtime_payload = client.get("/api/v1/admin/runtime").json()["panel"]
        assert runtime_payload["runtime"]["details"]["deployment_mode"] == "native"
        assert runtime_payload["runtime"]["details"]["control_mode"] == "native-readonly"
        assert runtime_payload["runtime"]["details"]["available_actions"] == [
            "sync_runtime",
            "pause_scheduler",
            "resume_scheduler",
            "tail_log",
        ]
        assert "read-only runtime" in (runtime_payload["runtime"]["details"]["operator_summary"] or "")
        assert runtime_payload["runtime"]["details"]["suggested_action"]["kind"] == "tail_log"
        assert runtime_payload["supervisor"]["control_available"] is False
        assert runtime_payload["supervisor"]["supervisor_state"] == "native-readonly"
        assert runtime_payload["supervisor"]["process_state"] == "running"
        assert runtime_payload["supervisor"]["pid_or_container_id"]
        assert runtime_payload["supervisor"]["log_location"] == str(log_path.resolve())

        restart = client.post("/api/v1/admin/panel/actions", json={"action": "restart", "actor": "admin-ui"})
        assert restart.status_code == 409
        assert "requires a configured panel control bridge" in restart.json()["detail"]

        queued = client.post("/api/v1/admin/panel/actions", json={"action": "tail_log", "actor": "admin-ui"})
        assert queued.status_code == 200
        assert queued.json()["queued"] is True

        client.app.state.runtime.run_maintenance_cycle(force_runtime_sync=True)

        action = client.get("/api/v1/admin/actions").json()["items"][0]
        assert action["status"] == "completed"
        assert action["target_name"] == "panel"
        assert action["has_log_excerpt"] is True
        assert action["severity"] == "info"
        assert action["target_runtime_state"] == "running"
        assert "read-only runtime" in (action["target_operator_summary"] or "")
        detail = client.get(f"/api/v1/admin/actions/{action['id']}").json()
        assert "panel-native.log" in (detail["result_summary"] or "")
        assert "panel-native.log" in (detail["summary"] or "")
        assert detail["log_excerpt"][-1] == "line-c"
        assert detail["runtime_snapshot"]["supervisor"]["supervisor_state"] == "native-readonly"
        assert detail["target_snapshot"]["target_kind"] == "panel"
        assert detail["target_snapshot"]["runtime"]["details"]["control_mode"] == "native-readonly"
        assert "read-only runtime" in (detail["target_snapshot"]["operator_summary"] or "")


def test_panel_bridge_actions_are_hidden_when_bridge_runtime_is_unreachable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MC_NETPROBE_PANEL_CONTROL_BRIDGE_URL", "http://panel-control-bridge:8877")
    with build_client(tmp_path) as client:
        login_admin(client)
        runtime = client.app.state.runtime
        runtime.control = FailingBridgeControlClient()

        runtime_payload = client.get("/api/v1/admin/runtime").json()["panel"]
        assert runtime_payload["runtime"]["details"]["bridge_error_code"] == "connect_error"
        assert runtime_payload["runtime"]["details"]["available_actions"] == [
            "sync_runtime",
            "pause_scheduler",
            "resume_scheduler",
        ]
        assert "unreachable" in (runtime_payload["runtime"]["details"]["readonly_reason"] or "")
        assert "could not connect" in (runtime_payload["runtime"]["details"]["operator_summary"] or "")
        assert runtime_payload["runtime"]["details"]["suggested_action"]["kind"] == "sync_runtime"

        restart = client.post("/api/v1/admin/panel/actions", json={"action": "restart", "actor": "admin-ui"})
        assert restart.status_code == 409
        assert "unreachable" in restart.json()["detail"]


def test_failed_node_action_immediately_marks_bridge_unavailable(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        node = seed_paired_node(client)
        runtime = client.app.state.runtime
        runtime.control = FailingBridgeControlClient()

        queued = client.post(
            f"/api/v1/admin/nodes/{node['id']}/actions",
            json={"action": "sync_runtime", "actor": "admin-ui"},
        )
        assert queued.status_code == 200

        runtime.run_maintenance_cycle(force_runtime_sync=True)

        action = client.get("/api/v1/admin/actions").json()["items"][0]
        assert action["status"] == "failed"
        assert action["severity"] == "warning"
        assert "could not connect" in (action["summary"] or "")
        assert action["code"] == "connect_error"
        detail = client.get(f"/api/v1/admin/actions/{action['id']}").json()
        assert detail["failure"]["code"] == "connect_error"

        node_payload = client.get(f"/api/v1/nodes/{node['id']}").json()
        assert node_payload["runtime"]["details"]["bridge_error_code"] == "connect_error"
        assert node_payload["runtime"]["details"]["available_actions"] == []


def test_failed_panel_action_immediately_marks_bridge_unavailable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("MC_NETPROBE_PANEL_CONTROL_BRIDGE_URL", "http://panel-control-bridge:8877")
    with build_client(tmp_path) as client:
        login_admin(client)
        runtime = client.app.state.runtime
        runtime.control = FailingBridgeControlClient()

        queued = client.post("/api/v1/admin/panel/actions", json={"action": "tail_log", "actor": "admin-ui"})
        assert queued.status_code == 200

        runtime.run_maintenance_cycle(force_runtime_sync=True)

        action = client.get("/api/v1/admin/actions").json()["items"][0]
        assert action["status"] == "failed"
        assert action["severity"] == "warning"
        assert "could not connect" in (action["summary"] or "")
        assert action["code"] == "connect_error"
        detail = client.get(f"/api/v1/admin/actions/{action['id']}").json()
        assert detail["failure"]["code"] == "connect_error"

        panel_payload = client.get("/api/v1/admin/runtime").json()["panel"]
        assert panel_payload["runtime"]["details"]["bridge_error_code"] == "connect_error"
        assert panel_payload["runtime"]["details"]["available_actions"] == [
            "sync_runtime",
            "pause_scheduler",
            "resume_scheduler",
        ]


def test_action_detail_returns_normalized_log_and_runtime_snapshot(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        node = seed_paired_node(client)
        runtime = client.app.state.runtime
        runtime.control = FakeControlClient()

        queued = client.post(
            f"/api/v1/admin/nodes/{node['id']}/actions",
            json={"action": "tail_log", "actor": "admin-ui", "tail_lines": 40},
        )
        assert queued.status_code == 200

        runtime.run_maintenance_cycle(force_runtime_sync=True)

        action = client.get("/api/v1/admin/actions").json()["items"][0]
        assert action["has_log_excerpt"] is True
        assert action["has_runtime_snapshot"] is True

        detail = client.get(f"/api/v1/admin/actions/{action['id']}").json()
        assert detail["request"]["tail_lines"] == 40
        assert detail["log_excerpt"] == ["line-a", "line-b"]
        assert detail["log_location"] == "docker://node"
        assert detail["runtime_snapshot"]["supervisor"]["log_location"] == "docker://node"
        assert detail["target_snapshot"]["target_kind"] == "node"
        assert detail["target_snapshot"]["target_id"] == node["id"]
        assert detail["target_snapshot"]["target_name"] == "relay-1"
        assert detail["target_snapshot"]["supervisor"]["control_available"] is True
        assert detail["target_snapshot"]["endpoints"]["control_bridge_url"] == "http://relay.example:9871"


def test_run_events_endpoint_returns_timeline(tmp_path: Path) -> None:
    with build_client(tmp_path) as client:
        login_admin(client)
        store = client.app.state.runtime.store
        run_id = store.create_run("baseline", "test")
        store.record_run_event(run_id, "phase_started", "baseline phase started", {"phase": "baseline"})
        store.record_run_event(run_id, "probe_dispatched", "probe dispatched", {"task": "ping"})
        detail_before_finish = client.get(f"/api/v1/admin/runs/{run_id}").json()
        assert detail_before_finish["active"] is True
        assert detail_before_finish["progress"]["active_phase"] == "baseline"
        assert detail_before_finish["progress"]["events_count"] >= 3
        assert detail_before_finish["progress"]["latest_probe"]["task"] == "ping"
        assert detail_before_finish["progress"]["headline"] == "Latest probe ping was dispatched."
        assert detail_before_finish["progress"]["headline_severity"] == "info"
        assert "Wait for the probe result" in (detail_before_finish["progress"]["recommended_step"] or "")

        store.record_run_event(run_id, "phase_completed", "baseline phase completed", {"phase": "baseline"})
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
        items = response.json()["items"]
        kinds = [item["event_kind"] for item in items]
        assert "run_created" in kinds
        assert "probe_dispatched" in kinds
        dispatched = next(item for item in items if item["event_kind"] == "probe_dispatched")
        assert dispatched["summary"] == "ping"
        assert dispatched["severity"] == "info"

        runs = client.get("/api/v1/admin/runs?time_range=24h").json()["items"]
        run_summary = next(item for item in runs if item["run_id"] == run_id)
        assert run_summary["active"] is False
        assert run_summary["progress"]["events_count"] >= 5
        assert run_summary["progress"]["last_event_kind"] == "run_finished"
