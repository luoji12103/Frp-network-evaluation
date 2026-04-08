"""Host-level control bridge for panel and node lifecycle operations."""

from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import uvicorn
import yaml
from fastapi import FastAPI, Header, HTTPException

from controller.panel_models import BridgeActionRequest, BridgeActionResponse, RuntimeSummary, SupervisorSummary
from probes.common import now_iso


DEFAULT_PANEL_CONTROL_BRIDGE_PORT = 8877
DEFAULT_NODE_CONTROL_PORT_OFFSET = 1
DEFAULT_MACOS_CONTROL_BRIDGE_LABEL = "com.mc-netprobe.server.control-bridge"
DEFAULT_WINDOWS_CONTROL_BRIDGE_TASK = "mc-netprobe-client-control-bridge"
DEFAULT_RELAY_CONTROL_BRIDGE_CONTAINER = "mc-netprobe-relay-control-bridge"
DEFAULT_PANEL_CONTROL_BRIDGE_CONTAINER = "mc-netprobe-panel-control-bridge"
DEFAULT_RELAY_CONTAINER = "mc-netprobe-relay-agent"
DEFAULT_PANEL_CONTAINER = "mc-netprobe-panel"


class BridgeActionError(RuntimeError):
    """Structured error raised while executing a bridge action."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class ControlAdapter(ABC):
    """Host supervisor adapter used by the control bridge."""

    @abstractmethod
    def runtime(self) -> BridgeActionResponse:
        """Return the current runtime and supervisor state."""

    @abstractmethod
    def start(self) -> BridgeActionResponse:
        """Start the managed service."""

    @abstractmethod
    def stop(self) -> BridgeActionResponse:
        """Stop the managed service."""

    @abstractmethod
    def restart(self) -> BridgeActionResponse:
        """Restart the managed service."""

    @abstractmethod
    def tail_log(self, tail_lines: int) -> BridgeActionResponse:
        """Return the last N lines of the managed service log."""


class LaunchdAdapter(ControlAdapter):
    """Manage a launchd-backed service on macOS."""

    def __init__(self, label: str, plist_path: str | Path, log_path: str | Path) -> None:
        self.label = label
        self.plist_path = str(Path(plist_path).expanduser().resolve())
        self.log_path = str(Path(log_path).expanduser().resolve())
        self.domain_target = f"gui/{self._uid()}"
        self.service_target = f"{self.domain_target}/{label}"

    def runtime(self) -> BridgeActionResponse:
        command = ["launchctl", "print", self.service_target]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        checked_at = now_iso()
        if completed.returncode != 0:
            summary = "launchd service is not loaded"
            return BridgeActionResponse(
                state="stopped",
                human_summary=summary,
                runtime=RuntimeSummary(state="stopped", checked_at=checked_at, last_error=completed.stderr.strip() or None),
                supervisor=SupervisorSummary(
                    control_available=True,
                    supervisor_state="unloaded",
                    process_state="stopped",
                    log_location=self.log_path,
                    last_error=completed.stderr.strip() or None,
                    checked_at=checked_at,
                ),
                log_location=self.log_path,
                error=completed.stderr.strip() or None,
                raw_runtime={"stdout": completed.stdout, "stderr": completed.stderr},
            )
        payload = completed.stdout
        process_state = "running" if "state = running" in payload.lower() else "stopped"
        pid = _extract_launchd_value(payload, "pid")
        supervisor_state = _extract_launchd_value(payload, "state") or process_state
        return BridgeActionResponse(
            state=process_state,
            human_summary=f"launchd reports {supervisor_state}",
            runtime=RuntimeSummary(state=process_state, checked_at=checked_at),
            supervisor=SupervisorSummary(
                control_available=True,
                supervisor_state=supervisor_state,
                process_state=process_state,
                pid_or_container_id=pid,
                log_location=self.log_path,
                checked_at=checked_at,
            ),
            log_location=self.log_path,
            raw_runtime={"stdout": payload},
        )

    def start(self) -> BridgeActionResponse:
        subprocess.run(["launchctl", "bootstrap", self.domain_target, self.plist_path], capture_output=True, text=True, check=False)
        completed = subprocess.run(
            ["launchctl", "kickstart", "-k", self.service_target],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise BridgeActionError("launchd_start_failed", completed.stderr.strip() or "launchctl kickstart failed")
        return self.runtime()

    def stop(self) -> BridgeActionResponse:
        completed = subprocess.run(
            ["launchctl", "bootout", self.service_target],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 and "no such process" not in completed.stderr.lower():
            raise BridgeActionError("launchd_stop_failed", completed.stderr.strip() or "launchctl bootout failed")
        return self.runtime()

    def restart(self) -> BridgeActionResponse:
        self.stop()
        return self.start()

    def tail_log(self, tail_lines: int) -> BridgeActionResponse:
        lines = _tail_file(self.log_path, tail_lines)
        return BridgeActionResponse(
            state="ok",
            human_summary=f"Read {len(lines)} log lines from {self.log_path}",
            runtime=RuntimeSummary(state="running", checked_at=now_iso()),
            supervisor=SupervisorSummary(control_available=True, log_location=self.log_path, checked_at=now_iso()),
            log_location=self.log_path,
            log_excerpt=lines,
        )

    def _uid(self) -> int:
        completed = subprocess.run(["id", "-u"], capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            raise BridgeActionError("launchd_uid_lookup_failed", completed.stderr.strip() or "failed to resolve uid")
        return int(completed.stdout.strip())


class WindowsTaskAdapter(ControlAdapter):
    """Manage a Windows scheduled task-backed service."""

    def __init__(self, task_name: str, log_path: str | Path) -> None:
        self.task_name = task_name
        self.log_path = str(Path(log_path).expanduser())

    def runtime(self) -> BridgeActionResponse:
        script = (
            f"$task = Get-ScheduledTask -TaskName '{self.task_name}'; "
            f"$info = Get-ScheduledTaskInfo -TaskName '{self.task_name}'; "
            "@{state=[string]$task.State; lastTaskResult=[string]$info.LastTaskResult; "
            "lastRunTime=[string]$info.LastRunTime; nextRunTime=[string]$info.NextRunTime} | ConvertTo-Json -Compress"
        )
        payload = self._powershell(script)
        state = str(payload.get("state") or "Unknown").lower()
        process_state = "running" if state == "running" else "stopped"
        checked_at = now_iso()
        return BridgeActionResponse(
            state=process_state,
            human_summary=f"Scheduled task is {state}",
            runtime=RuntimeSummary(state=process_state, checked_at=checked_at, details=payload),
            supervisor=SupervisorSummary(
                control_available=True,
                supervisor_state=state,
                process_state=process_state,
                log_location=self.log_path,
                checked_at=checked_at,
            ),
            log_location=self.log_path,
            raw_runtime=payload,
        )

    def start(self) -> BridgeActionResponse:
        self._powershell_raw(f"Start-ScheduledTask -TaskName '{self.task_name}'")
        return self.runtime()

    def stop(self) -> BridgeActionResponse:
        self._powershell_raw(f"Stop-ScheduledTask -TaskName '{self.task_name}'")
        return self.runtime()

    def restart(self) -> BridgeActionResponse:
        self._powershell_raw(f"Stop-ScheduledTask -TaskName '{self.task_name}' -ErrorAction SilentlyContinue")
        self._powershell_raw(f"Start-ScheduledTask -TaskName '{self.task_name}'")
        return self.runtime()

    def tail_log(self, tail_lines: int) -> BridgeActionResponse:
        lines = _tail_file(self.log_path, tail_lines)
        return BridgeActionResponse(
            state="ok",
            human_summary=f"Read {len(lines)} log lines from {self.log_path}",
            runtime=RuntimeSummary(state="running", checked_at=now_iso()),
            supervisor=SupervisorSummary(control_available=True, log_location=self.log_path, checked_at=now_iso()),
            log_location=self.log_path,
            log_excerpt=lines,
        )

    def _powershell(self, script: str) -> dict[str, Any]:
        completed = self._powershell_raw(script)
        try:
            return json.loads(completed.stdout.strip() or "{}")
        except json.JSONDecodeError as exc:  # pragma: no cover - Windows-only
            raise BridgeActionError("windows_status_parse_failed", str(exc)) from exc

    def _powershell_raw(self, script: str) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise BridgeActionError("windows_task_command_failed", completed.stderr.strip() or completed.stdout.strip() or "PowerShell failed")
        return completed


class DockerContainerAdapter(ControlAdapter):
    """Manage a Docker container through the Engine HTTP API over a Unix socket."""

    def __init__(self, container_name: str, log_location: str | None = None, socket_path: str | Path = "/var/run/docker.sock") -> None:
        self.container_name = container_name
        self.log_location = log_location or f"docker://{container_name}"
        self.socket_path = str(Path(socket_path))

    def runtime(self) -> BridgeActionResponse:
        payload = self._docker_request("GET", f"/containers/{self.container_name}/json")
        state = payload.get("State", {})
        status = str(state.get("Status") or "unknown")
        process_state = "running" if bool(state.get("Running")) else "stopped"
        checked_at = now_iso()
        return BridgeActionResponse(
            state=process_state,
            human_summary=f"Docker container {self.container_name} is {status}",
            runtime=RuntimeSummary(state=process_state, checked_at=checked_at, details={"status": status, "health": state.get("Health")}),
            supervisor=SupervisorSummary(
                control_available=True,
                supervisor_state=status,
                process_state=process_state,
                pid_or_container_id=str(payload.get("Id") or "")[:12] or None,
                log_location=self.log_location,
                checked_at=checked_at,
            ),
            log_location=self.log_location,
            raw_runtime=payload,
        )

    def start(self) -> BridgeActionResponse:
        self._docker_request("POST", f"/containers/{self.container_name}/start", expected=(204, 304))
        return self.runtime()

    def stop(self) -> BridgeActionResponse:
        self._docker_request("POST", f"/containers/{self.container_name}/stop", params={"t": 1}, expected=(204, 304))
        return self.runtime()

    def restart(self) -> BridgeActionResponse:
        self._docker_request("POST", f"/containers/{self.container_name}/restart", params={"t": 1}, expected=(204, 304))
        return self.runtime()

    def tail_log(self, tail_lines: int) -> BridgeActionResponse:
        text = self._docker_request_text(
            "GET",
            f"/containers/{self.container_name}/logs",
            params={"stdout": 1, "stderr": 1, "tail": tail_lines},
        )
        lines = [line.rstrip("\n") for line in text.splitlines() if line.strip()]
        return BridgeActionResponse(
            state="ok",
            human_summary=f"Read {len(lines)} log lines from {self.log_location}",
            runtime=RuntimeSummary(state="running", checked_at=now_iso()),
            supervisor=SupervisorSummary(control_available=True, log_location=self.log_location, checked_at=now_iso()),
            log_location=self.log_location,
            log_excerpt=lines,
        )

    def _docker_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        transport = httpx.HTTPTransport(uds=self.socket_path)
        with httpx.Client(base_url="http://docker", transport=transport, timeout=10.0) as client:
            response = client.request(method, path, params=params)
        if response.status_code not in expected:
            raise BridgeActionError("docker_api_failed", _docker_error_message(response))
        if response.status_code == 204:
            return {}
        return response.json() if response.content else {}

    def _docker_request_text(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> str:
        transport = httpx.HTTPTransport(uds=self.socket_path)
        with httpx.Client(base_url="http://docker", transport=transport, timeout=10.0) as client:
            response = client.request(method, path, params=params)
        if response.status_code not in expected:
            raise BridgeActionError("docker_api_failed", _docker_error_message(response))
        return response.text


class TokenResolver(ABC):
    """Resolve and validate bearer tokens for bridge requests."""

    @abstractmethod
    def verify(self, presented: str | None) -> None:
        """Raise HTTPException when the presented token is invalid."""


class PanelTokenResolver(TokenResolver):
    """Verify the panel bridge token from a shared file."""

    def __init__(self, token_file: str | Path) -> None:
        self.token_file = Path(token_file)

    def verify(self, presented: str | None) -> None:
        if not presented:
            raise HTTPException(status_code=401, detail="Missing control bridge token")
        expected = self._read_token()
        if not expected:
            raise HTTPException(status_code=503, detail="Control bridge token is not ready yet")
        if presented != expected:
            raise HTTPException(status_code=401, detail="Invalid control bridge token")

    def _read_token(self) -> str:
        if not self.token_file.exists():
            return ""
        return self.token_file.read_text(encoding="utf-8").strip()


class NodeTokenResolver(TokenResolver):
    """Verify the node token from the colocated agent config file."""

    def __init__(self, agent_config_path: str | Path) -> None:
        self.agent_config_path = Path(agent_config_path)

    def verify(self, presented: str | None) -> None:
        if not presented:
            raise HTTPException(status_code=401, detail="Missing node token")
        config = self._load_agent_config()
        expected = str(config.get("node_token") or "")
        if not expected:
            raise HTTPException(status_code=409, detail="Agent is not paired")
        if presented != expected:
            raise HTTPException(status_code=401, detail="Invalid node token")

    def _load_agent_config(self) -> dict[str, Any]:
        if not self.agent_config_path.exists():
            return {}
        loaded = yaml.safe_load(self.agent_config_path.read_text(encoding="utf-8")) or {}
        return loaded if isinstance(loaded, dict) else {}


class ControlBridgeService:
    """Own adapter execution and async scheduling for a control bridge."""

    def __init__(self, adapter: ControlAdapter, bridge_url: str | None = None) -> None:
        self.adapter = adapter
        self.bridge_url = bridge_url

    def runtime(self) -> BridgeActionResponse:
        response = self.adapter.runtime()
        return self._decorate_bridge_url(response)

    def execute(self, request: BridgeActionRequest) -> BridgeActionResponse:
        if request.action in {"status", "sync_runtime"}:
            return self.runtime()
        if request.action == "tail_log":
            response = self.adapter.tail_log(request.tail_lines or 40)
            return self._decorate_bridge_url(response)
        if request.action in {"start", "stop", "restart"}:
            threading.Thread(target=self._run_background_action, args=(request.action,), daemon=True).start()
            response = self.runtime()
            response.accepted = True
            response.human_summary = f"{request.action} has been accepted by the control bridge"
            return self._decorate_bridge_url(response)
        raise BridgeActionError("unsupported_action", f"Action {request.action} is not supported by this bridge")

    def _run_background_action(self, action: str) -> None:
        time.sleep(0.75)
        try:
            if action == "start":
                self.adapter.start()
            elif action == "stop":
                self.adapter.stop()
            elif action == "restart":
                self.adapter.restart()
        except Exception:
            # The panel records the accepted action before the supervisor change.
            return

    def _decorate_bridge_url(self, response: BridgeActionResponse) -> BridgeActionResponse:
        if self.bridge_url and not response.supervisor.bridge_url:
            response.supervisor.bridge_url = self.bridge_url
        return response


def create_control_bridge_app(
    adapter: ControlAdapter,
    token_resolver: TokenResolver,
    bridge_url: str | None = None,
    service: ControlBridgeService | None = None,
) -> FastAPI:
    service = service or ControlBridgeService(adapter=adapter, bridge_url=bridge_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.control_bridge = service
        yield

    app = FastAPI(title="mc-netprobe-control-bridge", version="1.0", lifespan=lifespan)

    @app.get("/api/v1/control/health")
    def control_health() -> dict[str, Any]:
        return {"ok": True, "status": "healthy", "started_at": now_iso()}

    @app.get("/api/v1/control/runtime")
    def control_runtime(x_node_token: str | None = Header(default=None), x_control_token: str | None = Header(default=None)) -> dict[str, Any]:
        token_resolver.verify(x_node_token or x_control_token)
        return service.runtime().model_dump()

    @app.post("/api/v1/control/actions")
    def control_action(
        payload: BridgeActionRequest,
        x_node_token: str | None = Header(default=None),
        x_control_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        token_resolver.verify(x_node_token or x_control_token)
        return service.execute(payload).model_dump()

    return app


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the control bridge."""
    parser = argparse.ArgumentParser(description="mc-netprobe host control bridge")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=DEFAULT_PANEL_CONTROL_BRIDGE_PORT)
    parser.add_argument("--mode", choices=["node", "panel"], required=True)
    parser.add_argument("--adapter", choices=["launchd", "windows-task", "docker-container"], required=True)
    parser.add_argument("--bridge-url", default=None)
    parser.add_argument("--token-file", default="data/panel-control-bridge-token.txt")
    parser.add_argument("--agent-config", default="config/agent/server.yaml")
    parser.add_argument("--label", default=None)
    parser.add_argument("--plist-path", default=None)
    parser.add_argument("--task-name", default=None)
    parser.add_argument("--container-name", default=None)
    parser.add_argument("--log-path", default="logs/control-bridge.log")
    parser.add_argument("--docker-socket", default="/var/run/docker.sock")
    return parser


def build_adapter(args: argparse.Namespace) -> ControlAdapter:
    """Construct a host adapter from CLI arguments."""
    if args.adapter == "launchd":
        label = args.label or DEFAULT_MACOS_CONTROL_BRIDGE_LABEL.replace(".control-bridge", ".agent")
        plist_path = args.plist_path or str(Path.home() / "Library" / "LaunchAgents" / f"{label}.plist")
        return LaunchdAdapter(label=label, plist_path=plist_path, log_path=args.log_path)
    if args.adapter == "windows-task":
        task_name = args.task_name or "mc-netprobe-client-agent"
        return WindowsTaskAdapter(task_name=task_name, log_path=args.log_path)
    container_name = args.container_name or (DEFAULT_PANEL_CONTAINER if args.mode == "panel" else DEFAULT_RELAY_CONTAINER)
    return DockerContainerAdapter(container_name=container_name, log_location=args.log_path, socket_path=args.docker_socket)


def build_token_resolver(args: argparse.Namespace) -> TokenResolver:
    """Construct a token resolver from CLI arguments."""
    if args.mode == "panel":
        return PanelTokenResolver(token_file=args.token_file)
    return NodeTokenResolver(agent_config_path=args.agent_config)


def main() -> int:
    """Run the control bridge server."""
    args = build_parser().parse_args()
    app = create_control_bridge_app(
        adapter=build_adapter(args),
        token_resolver=build_token_resolver(args),
        bridge_url=args.bridge_url,
    )
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def _extract_launchd_value(payload: str, field_name: str) -> str | None:
    marker = f"{field_name} = "
    for line in payload.splitlines():
        line = line.strip()
        if line.startswith(marker):
            return line[len(marker) :].strip().strip(";")
    return None


def _tail_file(path: str | Path, tail_lines: int) -> list[str]:
    target = Path(path).expanduser()
    if not target.exists():
        return []
    lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-tail_lines:]


def _docker_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        payload = {}
    if isinstance(payload, dict) and payload.get("message"):
        return str(payload["message"])
    return response.text.strip() or f"HTTP {response.status_code}"


if __name__ == "__main__":
    raise SystemExit(main())
