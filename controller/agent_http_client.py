"""HTTP helpers for panel-to-agent communication."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import ValidationError

from controller.panel_models import (
    SUPPORTED_AGENT_PROTOCOL_VERSION,
    AgentStatusResponse,
    AgentTaskCompletion,
    AgentTaskDispatch,
)
from controller.panel_store import PanelStore


class AgentHttpError(RuntimeError):
    """Structured transport error raised for pull-mode agent requests."""

    def __init__(self, code: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class AgentHttpClient:
    """Run direct pull-mode requests against paired agents."""

    def __init__(self, store: PanelStore, timeout_sec: float = 10.0) -> None:
        self.store = store
        self.timeout_sec = timeout_sec

    def check_status(self, node: dict[str, Any]) -> dict[str, Any]:
        payload = self._request(node=node, method="GET", path="/api/v1/status")
        try:
            status = AgentStatusResponse.model_validate(payload)
        except ValidationError as exc:
            legacy_detail = self._legacy_status_detail(payload)
            if legacy_detail is not None:
                raise AgentHttpError("legacy_status_shape", legacy_detail) from exc
            raise AgentHttpError(
                "protocol_mismatch",
                "Agent status payload did not match the current structured contract",
            ) from exc
        protocol_version = str(status.identity.protocol_version or "").strip()
        if protocol_version != SUPPORTED_AGENT_PROTOCOL_VERSION:
            raise AgentHttpError(
                "protocol_mismatch",
                (
                    f"Unsupported agent protocol_version '{protocol_version}' "
                    f"(expected {SUPPORTED_AGENT_PROTOCOL_VERSION})"
                ),
            )
        return status.model_dump()

    def run_job(self, node: dict[str, Any], job_id: int | None, run_id: str, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = AgentTaskDispatch(job_id=job_id, run_id=run_id, task=task, payload=payload)
        response = self._request(
            node=node,
            method="POST",
            path="/api/v1/jobs/run",
            json_body=request.model_dump(),
            timeout_sec=self.timeout_sec + float(payload.get("timeout_sec", 0.0)),
        )
        return AgentTaskCompletion.model_validate(response).model_dump()

    def get_result(self, node: dict[str, Any], run_id: str) -> dict[str, Any]:
        return self._request(node=node, method="GET", path=f"/api/v1/results/{run_id}")

    def _request(
        self,
        node: dict[str, Any],
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
        timeout_sec: float | None = None,
    ) -> dict[str, Any]:
        base_url = self._agent_base_url(node)
        token = self.store.build_node_token(int(node["id"]))
        timeout = timeout_sec or self.timeout_sec
        with httpx.Client(timeout=timeout) as client:
            try:
                response = client.request(
                    method,
                    f"{base_url.rstrip('/')}{path}",
                    headers={"X-Node-Token": token},
                    json=json_body,
                )
                response.raise_for_status()
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise AgentHttpError("invalid_json", f"{base_url}{path} did not return valid JSON") from exc
                if not isinstance(payload, dict):
                    raise AgentHttpError(
                        "invalid_payload",
                        f"{base_url}{path} returned {type(payload).__name__}, expected a JSON object",
                    )
                return payload
            except httpx.TimeoutException as exc:
                raise AgentHttpError("timeout", f"request to {base_url}{path} timed out") from exc
            except httpx.ConnectError as exc:
                raise AgentHttpError("connect_error", f"could not connect to {base_url}") from exc
            except httpx.HTTPStatusError as exc:
                detail = self._response_detail(exc.response)
                code = "http_error"
                if exc.response.status_code == 401:
                    code = "auth_error"
                elif exc.response.status_code in {404, 405} and self._is_contract_route(path):
                    code = "protocol_mismatch"
                    detail = f"Agent did not expose {path}; upgrade the agent to a compatible control-plane contract"
                elif exc.response.status_code == 409 or "protocol" in detail.lower():
                    code = "protocol_mismatch"
                raise AgentHttpError(code, detail, status_code=exc.response.status_code) from exc
            except httpx.RequestError as exc:
                raise AgentHttpError("request_error", str(exc)) from exc

    def _agent_base_url(self, node: dict[str, Any]) -> str:
        base_url = node.get("endpoints", {}).get("effective_pull_url")
        if not base_url:
            raise AgentHttpError("missing_endpoint", "Effective pull URL is not configured")
        return str(base_url)

    def _response_detail(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if detail:
            return str(detail)
        return f"HTTP {response.status_code}"

    def _legacy_status_detail(self, payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return None
        structured_keys = {"identity", "endpoint", "capabilities", "runtime_status"}
        if structured_keys.issubset(payload):
            return None
        legacy_keys = {
            "node_name",
            "role",
            "runtime_mode",
            "listen_host",
            "listen_port",
            "panel_url",
            "paired",
            "started_at",
        }
        if legacy_keys.intersection(payload):
            return (
                "Agent responded with a legacy /api/v1/status payload; upgrade the agent to the current "
                "structured contract before relying on pull-mode health checks"
            )
        return None

    def _is_contract_route(self, path: str) -> bool:
        return path == "/api/v1/status" or path == "/api/v1/jobs/run" or path.startswith("/api/v1/results/")
