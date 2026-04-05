"""HTTP helpers for panel-to-agent communication."""

from __future__ import annotations

from typing import Any

import httpx

from controller.panel_store import PanelStore


class AgentHttpClient:
    """Run direct pull-mode requests against paired agents."""

    def __init__(self, store: PanelStore, timeout_sec: float = 10.0) -> None:
        self.store = store
        self.timeout_sec = timeout_sec

    def check_status(self, node: dict[str, Any]) -> dict[str, Any]:
        if not node.get("agent_url"):
            raise ValueError("Agent URL is not configured")
        with httpx.Client(timeout=self.timeout_sec) as client:
            response = client.get(f"{node['agent_url'].rstrip('/')}/api/v1/status")
            response.raise_for_status()
            return response.json()

    def run_job(self, node: dict[str, Any], job_id: int | None, run_id: str, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not node.get("agent_url"):
            raise ValueError("Agent URL is not configured")
        token = self.store.build_node_token(int(node["id"]))
        with httpx.Client(timeout=self.timeout_sec + float(payload.get("timeout_sec", 0.0))) as client:
            response = client.post(
                f"{node['agent_url'].rstrip('/')}/api/v1/jobs/run",
                headers={"X-Node-Token": token},
                json={
                    "job_id": job_id,
                    "run_id": run_id,
                    "task": task,
                    "payload": payload,
                },
            )
            response.raise_for_status()
            return response.json()

    def get_result(self, node: dict[str, Any], run_id: str) -> dict[str, Any]:
        if not node.get("agent_url"):
            raise ValueError("Agent URL is not configured")
        token = self.store.build_node_token(int(node["id"]))
        with httpx.Client(timeout=self.timeout_sec) as client:
            response = client.get(
                f"{node['agent_url'].rstrip('/')}/api/v1/results/{run_id}",
                headers={"X-Node-Token": token},
            )
            response.raise_for_status()
            return response.json()
