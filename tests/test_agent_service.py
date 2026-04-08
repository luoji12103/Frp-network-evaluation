from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import agents.service as agent_service
from agents.service import create_agent_app


def test_agent_runs_direct_job_and_returns_cached_result(monkeypatch, tmp_path: Path) -> None:
    async def fake_execute_task(role: str, task: str, payload: dict[str, object]) -> dict[str, object]:
        return {
            "name": task,
            "source": role,
            "target": "local",
            "success": True,
            "metrics": {"sample_interval_sec": payload.get("sample_interval_sec")},
            "samples": [],
            "error": None,
            "started_at": "2026-04-06T00:00:00Z",
            "duration_ms": 1.0,
            "metadata": {"role": role},
        }

    monkeypatch.setattr(agent_service, "execute_task", fake_execute_task)

    app = create_agent_app(
        config_path=tmp_path / "agent.yaml",
        overrides={
            "node_name": "relay-1",
            "role": "relay",
            "runtime_mode": "docker-linux",
            "node_token": "secret-token",
        },
        start_background=False,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/jobs/run",
            headers={"X-Node-Token": "secret-token"},
            json={
                "job_id": 1,
                "run_id": "run-direct",
                "task": "system_snapshot",
                "payload": {"sample_interval_sec": 0.01, "process_names": []},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["run_id"] == "run-direct"
        assert payload["result"]["name"] == "system_snapshot"

        cached = client.get("/api/v1/results/run-direct", headers={"X-Node-Token": "secret-token"})
        assert cached.status_code == 200
        assert cached.json()["result"]["name"] == "system_snapshot"


def test_agent_health_is_available_without_pairing(tmp_path: Path) -> None:
    app = create_agent_app(
        config_path=tmp_path / "agent.yaml",
        overrides={
            "node_name": "client-1",
            "role": "client",
            "runtime_mode": "native-windows",
        },
        start_background=False,
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

        protected = client.get("/api/v1/status")
        assert protected.status_code == 409
        assert protected.json()["detail"] == "Agent is not paired"


def test_agent_status_requires_token_and_returns_structured_snapshot(tmp_path: Path) -> None:
    app = create_agent_app(
        config_path=tmp_path / "agent.yaml",
        overrides={
            "node_name": "server-1",
            "role": "server",
            "runtime_mode": "native-macos",
            "listen_host": "100.100.0.8",
            "listen_port": 39870,
            "advertise_url": "http://100.100.0.8:39870",
            "node_token": "secret-token",
        },
        start_background=False,
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/status", headers={"X-Node-Token": "secret-token"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["identity"]["node_name"] == "server-1"
        assert payload["identity"]["protocol_version"] == "1"
        assert payload["endpoint"]["listen_host"] == "100.100.0.8"
        assert payload["endpoint"]["listen_port"] == 39870
        assert payload["capabilities"]["pull_http"] is True
        assert payload["runtime_status"]["paired"] is True
