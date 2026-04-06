from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agents.service import create_agent_app


def test_agent_runs_direct_job_and_returns_cached_result(tmp_path: Path) -> None:
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


def test_agent_status_is_available_without_pairing(tmp_path: Path) -> None:
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
        response = client.get("/api/v1/status")
        assert response.status_code == 200
        assert response.json()["paired"] is False
