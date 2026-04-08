"""HTTP helpers for panel-to-control-bridge communication."""

from __future__ import annotations

import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx

from controller.panel_models import BridgeActionRequest, BridgeActionResponse
from controller.panel_store import PanelStore


class ControlBridgeError(RuntimeError):
    """Structured transport error raised for control bridge requests."""

    def __init__(self, code: str, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"


class ControlBridgeClient:
    """Run runtime and lifecycle requests against host control bridges."""

    def __init__(
        self,
        store: PanelStore,
        timeout_sec: float = 10.0,
        panel_bridge_url: str | None = None,
        panel_bridge_token_path: str | Path = "data/panel-control-bridge-token.txt",
    ) -> None:
        self.store = store
        self.timeout_sec = timeout_sec
        self.panel_bridge_url = panel_bridge_url
        self.panel_bridge_token_path = Path(panel_bridge_token_path)

    def ensure_panel_bridge_token(self) -> str:
        self.panel_bridge_token_path.parent.mkdir(parents=True, exist_ok=True)
        if self.panel_bridge_token_path.exists():
            existing = self.panel_bridge_token_path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        token = secrets.token_hex(24)
        self.panel_bridge_token_path.write_text(f"{token}\n", encoding="utf-8")
        return token

    def node_runtime(self, node: dict[str, Any]) -> BridgeActionResponse:
        return BridgeActionResponse.model_validate(
            self._request(
                base_url=self._node_bridge_url(node),
                headers={"X-Node-Token": self.store.build_node_token(int(node["id"]))},
                method="GET",
                path="/api/v1/control/runtime",
            )
        )

    def node_action(self, node: dict[str, Any], action: str, tail_lines: int | None = None) -> BridgeActionResponse:
        payload = BridgeActionRequest(action=action, tail_lines=tail_lines)
        return BridgeActionResponse.model_validate(
            self._request(
                base_url=self._node_bridge_url(node),
                headers={"X-Node-Token": self.store.build_node_token(int(node["id"]))},
                method="POST",
                path="/api/v1/control/actions",
                json_body=payload.model_dump(exclude_none=True),
            )
        )

    def panel_runtime(self) -> BridgeActionResponse:
        return BridgeActionResponse.model_validate(
            self._request(
                base_url=self._panel_bridge_base_url(),
                headers={"X-Control-Token": self.ensure_panel_bridge_token()},
                method="GET",
                path="/api/v1/control/runtime",
            )
        )

    def panel_action(self, action: str, tail_lines: int | None = None) -> BridgeActionResponse:
        payload = BridgeActionRequest(action=action, tail_lines=tail_lines)
        return BridgeActionResponse.model_validate(
            self._request(
                base_url=self._panel_bridge_base_url(),
                headers={"X-Control-Token": self.ensure_panel_bridge_token()},
                method="POST",
                path="/api/v1/control/actions",
                json_body=payload.model_dump(exclude_none=True),
            )
        )

    def _panel_bridge_base_url(self) -> str:
        if not self.panel_bridge_url:
            raise ControlBridgeError("missing_panel_bridge", "Panel control bridge is not configured")
        return self.panel_bridge_url

    def _node_bridge_url(self, node: dict[str, Any]) -> str:
        endpoint_report = node.get("endpoint_report") or {}
        if endpoint_report.get("control_url"):
            return str(endpoint_report["control_url"])
        control_port = endpoint_report.get("control_listen_port")
        if control_port:
            effective_pull_url = node.get("endpoints", {}).get("effective_pull_url")
            if effective_pull_url:
                parsed = urlparse(str(effective_pull_url))
                bridge_url = parsed._replace(netloc=f"{parsed.hostname}:{int(control_port)}")
                return urlunparse(bridge_url)
        raise ControlBridgeError("missing_node_bridge", f"Node {node.get('node_name')} does not expose a control bridge URL")

    def _request(
        self,
        base_url: str,
        headers: dict[str, str],
        method: str,
        path: str,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout_sec) as client:
            try:
                response = client.request(method, f"{base_url.rstrip('/')}{path}", headers=headers, json=json_body)
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as exc:
                raise ControlBridgeError("timeout", f"request to {base_url}{path} timed out") from exc
            except httpx.ConnectError as exc:
                raise ControlBridgeError("connect_error", f"could not connect to {base_url}") from exc
            except httpx.HTTPStatusError as exc:
                detail = self._response_detail(exc.response)
                code = "http_error"
                if exc.response.status_code == 401:
                    code = "auth_error"
                elif exc.response.status_code == 503:
                    code = "bridge_unavailable"
                raise ControlBridgeError(code, detail, status_code=exc.response.status_code) from exc
            except httpx.RequestError as exc:
                raise ControlBridgeError("request_error", str(exc)) from exc

    def _response_detail(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        detail = payload.get("detail") if isinstance(payload, dict) else None
        if detail:
            return str(detail)
        return response.text.strip() or f"HTTP {response.status_code}"
