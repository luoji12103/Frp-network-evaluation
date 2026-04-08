from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from controller.control_bridge import ControlAdapter, PanelTokenResolver, create_control_bridge_app
from controller.panel_models import BridgeActionResponse, RuntimeSummary, SupervisorSummary


class FakeAdapter(ControlAdapter):
    def runtime(self) -> BridgeActionResponse:
        return BridgeActionResponse(
            state="running",
            human_summary="fake adapter running",
            runtime=RuntimeSummary(state="running", checked_at="2026-04-08T00:00:00+00:00"),
            supervisor=SupervisorSummary(control_available=True, supervisor_state="running", process_state="running"),
        )

    def start(self) -> BridgeActionResponse:
        return self.runtime()

    def stop(self) -> BridgeActionResponse:
        return BridgeActionResponse(
            state="stopped",
            human_summary="fake adapter stopped",
            runtime=RuntimeSummary(state="stopped", checked_at="2026-04-08T00:00:01+00:00"),
            supervisor=SupervisorSummary(control_available=True, supervisor_state="stopped", process_state="stopped"),
        )

    def restart(self) -> BridgeActionResponse:
        return self.runtime()

    def tail_log(self, tail_lines: int) -> BridgeActionResponse:
        return BridgeActionResponse(
            state="ok",
            human_summary=f"tail {tail_lines}",
            runtime=RuntimeSummary(state="running", checked_at="2026-04-08T00:00:02+00:00"),
            supervisor=SupervisorSummary(control_available=True, supervisor_state="running", process_state="running"),
            log_excerpt=["line-1", "line-2"],
        )


def test_control_bridge_requires_token_and_returns_runtime_and_actions(tmp_path: Path) -> None:
    token_file = tmp_path / "bridge-token.txt"
    token_file.write_text("bridge-secret\n", encoding="utf-8")
    app = create_control_bridge_app(
        adapter=FakeAdapter(),
        token_resolver=PanelTokenResolver(token_file=token_file),
        bridge_url="http://bridge.test:8877",
    )
    with TestClient(app) as client:
        missing = client.get("/api/v1/control/runtime")
        assert missing.status_code == 401

        runtime = client.get("/api/v1/control/runtime", headers={"X-Control-Token": "bridge-secret"})
        assert runtime.status_code == 200
        assert runtime.json()["state"] == "running"
        assert runtime.json()["supervisor"]["bridge_url"] == "http://bridge.test:8877"

        tail = client.post(
            "/api/v1/control/actions",
            headers={"X-Control-Token": "bridge-secret"},
            json={"action": "tail_log", "tail_lines": 20},
        )
        assert tail.status_code == 200
        assert tail.json()["log_excerpt"] == ["line-1", "line-2"]

        restart = client.post(
            "/api/v1/control/actions",
            headers={"X-Control-Token": "bridge-secret"},
            json={"action": "restart"},
        )
        assert restart.status_code == 200
        assert restart.json()["accepted"] is True
