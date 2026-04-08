"""Long-lived HTTP agent service used by panel-based monitoring."""

from __future__ import annotations

import argparse
import asyncio
import socket
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
import uvicorn
import yaml
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agents import execute_task
from controller.panel_models import (
    AgentCapabilities,
    AgentEndpointReport,
    AgentHealthResponse,
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    AgentIdentity,
    AgentPairRequest,
    AgentPairResponse,
    AgentRuntimeStatus,
    AgentStatusResponse,
    AgentTaskCompletion,
    AgentTaskDispatch,
    SUPPORTED_AGENT_PROTOCOL_VERSION,
)
from probes.common import current_environment, detect_platform_name, now_iso


HEARTBEAT_INTERVAL_SEC = 15.0


class LocalPairRequest(BaseModel):
    """Optional local pairing API request."""

    panel_url: str
    pair_code: str
    advertise_url: str | None = None


class AgentConfig(BaseModel):
    """Persistent agent configuration."""

    panel_url: str | None = None
    node_name: str
    role: str
    runtime_mode: str
    listen_host: str = "0.0.0.0"
    listen_port: int = 9870
    advertise_url: str | None = None
    node_token: str | None = None
    pair_code: str | None = None
    protocol_version: str = SUPPORTED_AGENT_PROTOCOL_VERSION
    agent_version: str = "1"


class AgentRuntime:
    """Runtime state, pairing flow, and background heartbeat loop."""

    def __init__(self, config_path: str | Path, overrides: dict[str, Any] | None = None, start_background: bool = True) -> None:
        self.config_path = Path(config_path)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._heartbeat_thread: threading.Thread | None = None
        self._results: dict[str, dict[str, Any]] = {}
        self._completed_jobs: list[dict[str, Any]] = []
        self._started_at = now_iso()
        self._last_heartbeat_at: str | None = None
        self._last_error: str | None = None
        self.config = self._load_config(overrides or {})
        if self.config.pair_code and self.config.panel_url and not self.config.node_token:
            self._pair_with_panel(panel_url=self.config.panel_url, pair_code=self.config.pair_code, advertise_url=self.config.advertise_url)
        if start_background:
            self.start_background_threads()

    def identity(self) -> AgentIdentity:
        return AgentIdentity(
            node_name=self.config.node_name,
            role=self.config.role,  # type: ignore[arg-type]
            runtime_mode=self.config.runtime_mode,  # type: ignore[arg-type]
            protocol_version=self.config.protocol_version,
            platform_name=detect_platform_name(),
            hostname=socket.gethostname(),
            agent_version=self.config.agent_version,
        )

    def endpoint_report(self) -> AgentEndpointReport:
        return AgentEndpointReport(
            listen_host=self.config.listen_host,
            listen_port=self.config.listen_port,
            advertise_url=self.config.advertise_url,
        )

    def capabilities(self) -> AgentCapabilities:
        return AgentCapabilities(pull_http=True, heartbeat_queue=True, result_lookup=True)

    def runtime_status(self) -> AgentRuntimeStatus:
        return AgentRuntimeStatus(
            paired=bool(self.config.node_token),
            started_at=self._started_at,
            last_heartbeat_at=self._last_heartbeat_at,
            last_error=self._last_error,
            environment=current_environment() | {"platform_name": detect_platform_name(), "hostname": socket.gethostname()},
        )

    def status_snapshot(self) -> AgentStatusResponse:
        return AgentStatusResponse(
            identity=self.identity(),
            endpoint=self.endpoint_report(),
            capabilities=self.capabilities(),
            runtime_status=self.runtime_status(),
        )

    def start_background_threads(self) -> None:
        if self._heartbeat_thread is not None or not self.config.panel_url or not self.config.node_token:
            return
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=1.0)

    def verify_token(self, presented: str | None) -> None:
        if not self.config.node_token:
            raise HTTPException(status_code=409, detail="Agent is not paired")
        if not presented or presented != self.config.node_token:
            raise HTTPException(status_code=401, detail="Invalid node token")

    def run_direct_job(self, request: AgentTaskDispatch) -> AgentTaskCompletion:
        result = self._execute_task(task=request.task, payload=request.payload)
        run_id = request.run_id or f"{request.task}-{int(time.time() * 1000)}"
        with self._lock:
            self._results[run_id] = result
        return AgentTaskCompletion(job_id=request.job_id, run_id=run_id, task=request.task, result=result)

    def get_result(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            if run_id not in self._results:
                raise KeyError(run_id)
            return self._results[run_id]

    def trigger_local_pair(self, request: LocalPairRequest) -> dict[str, Any]:
        paired = self._pair_with_panel(panel_url=request.panel_url, pair_code=request.pair_code, advertise_url=request.advertise_url)
        return {"ok": True, "paired": True, "config": paired.model_dump()}

    def trigger_heartbeat(self) -> dict[str, Any]:
        response = self._send_heartbeat()
        return response.model_dump()

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.is_set():
            self._send_heartbeat()
            self._stop_event.wait(HEARTBEAT_INTERVAL_SEC)

    def _send_heartbeat(self) -> AgentHeartbeatResponse:
        if not self.config.panel_url or not self.config.node_token:
            return AgentHeartbeatResponse(ok=False, status="unpaired", jobs=[])

        pending = [AgentTaskCompletion.model_validate(item) for item in self._drain_completed_jobs()]
        remaining_rounds = 3
        while remaining_rounds > 0:
            remaining_rounds -= 1
            payload = AgentHeartbeatRequest(
                endpoint=self.endpoint_report(),
                runtime_status=self.runtime_status(),
                completed_jobs=pending,
            )
            try:
                with httpx.Client(timeout=10.0) as client:
                    response = client.post(
                        f"{self.config.panel_url.rstrip('/')}/api/v1/agents/heartbeat",
                        headers={"X-Node-Token": self.config.node_token},
                        json=payload.model_dump(),
                    )
                    response.raise_for_status()
                    data = AgentHeartbeatResponse.model_validate(response.json())
            except Exception as exc:  # pragma: no cover - network variability
                self._last_error = str(exc)
                if pending:
                    self._requeue_completed_jobs(pending)
                return AgentHeartbeatResponse(ok=False, status="error", jobs=[])

            self._last_heartbeat_at = now_iso()
            self._last_error = None
            if not data.jobs:
                return data
            pending = self._execute_leased_jobs(data.jobs)

        self._requeue_completed_jobs(pending)
        return AgentHeartbeatResponse(ok=True, status="accepted", jobs=[])

    def _pair_with_panel(self, panel_url: str, pair_code: str, advertise_url: str | None) -> AgentConfig:
        if advertise_url is not None:
            self.config.advertise_url = advertise_url
        payload = AgentPairRequest(
            pair_code=pair_code,
            identity=self.identity(),
            endpoint=self.endpoint_report(),
            capabilities=self.capabilities(),
        )
        with httpx.Client(timeout=10.0) as client:
            response = client.post(f"{panel_url.rstrip('/')}/api/v1/agents/pair", json=payload.model_dump())
            response.raise_for_status()
            data = AgentPairResponse.model_validate(response.json())

        self.config.panel_url = panel_url
        self.config.node_token = str(data.node_token)
        self.config.advertise_url = data.endpoint.advertise_url or advertise_url or self.config.advertise_url
        self.config.pair_code = None
        self._save_config()
        return self.config

    def _execute_task(self, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        merged_payload = dict(payload)
        merged_payload.setdefault("source", self.config.role)
        merged_payload.setdefault("platform_name", detect_platform_name())
        return asyncio.run(execute_task(role=self.config.role, task=task, payload=merged_payload))

    def _execute_leased_jobs(self, jobs: list[AgentTaskDispatch]) -> list[AgentTaskCompletion]:
        completed: list[AgentTaskCompletion] = []
        for job in jobs:
            try:
                result = self._execute_task(task=job.task, payload=job.payload)
            except Exception as exc:  # pragma: no cover - defensive
                result = {
                    "name": job.task,
                    "source": self.config.role,
                    "target": "unknown",
                    "success": False,
                    "metrics": {},
                    "samples": [],
                    "error": str(exc),
                    "started_at": now_iso(),
                    "duration_ms": 0.0,
                    "metadata": {"role": self.config.role},
                }
            completed.append(
                AgentTaskCompletion(
                    job_id=job.job_id,
                    run_id=job.run_id,
                    task=job.task,
                    result=result,
                )
            )
        return completed

    def _drain_completed_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            completed = list(self._completed_jobs)
            self._completed_jobs.clear()
        return completed

    def _requeue_completed_jobs(self, jobs: list[AgentTaskCompletion]) -> None:
        if not jobs:
            return
        with self._lock:
            self._completed_jobs = [job.model_dump() for job in jobs] + self._completed_jobs

    def _load_config(self, overrides: dict[str, Any]) -> AgentConfig:
        raw: dict[str, Any] = {}
        if self.config_path.exists():
            loaded = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw.update(loaded)
        raw.update({key: value for key, value in overrides.items() if value is not None})
        config = AgentConfig.model_validate(raw)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._save_config(config)
        return config

    def _save_config(self, config: AgentConfig | None = None) -> None:
        current = config or self.config
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(yaml.safe_dump(current.model_dump(), sort_keys=False, allow_unicode=True), encoding="utf-8")


def create_agent_app(
    config_path: str | Path,
    overrides: dict[str, Any] | None = None,
    start_background: bool = True,
    runtime: AgentRuntime | None = None,
) -> FastAPI:
    runtime = runtime or AgentRuntime(config_path=config_path, overrides=overrides, start_background=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        if start_background:
            runtime.start_background_threads()
        yield
        runtime.stop()

    app = FastAPI(title="mc-netprobe-agent", version="1.0", lifespan=lifespan)

    @app.get("/api/v1/health")
    def get_health() -> AgentHealthResponse:
        return AgentHealthResponse(started_at=runtime.runtime_status().started_at)

    @app.get("/api/v1/status")
    def get_status(x_node_token: str | None = Header(default=None)) -> dict[str, Any]:
        runtime.verify_token(x_node_token)
        return runtime.status_snapshot().model_dump()

    @app.post("/api/v1/pair")
    def pair_local(request: LocalPairRequest) -> dict[str, Any]:
        return runtime.trigger_local_pair(request)

    @app.post("/api/v1/heartbeat")
    def force_heartbeat() -> dict[str, Any]:
        return runtime.trigger_heartbeat()

    @app.post("/api/v1/jobs/run")
    def run_job(request: AgentTaskDispatch, x_node_token: str | None = Header(default=None)) -> JSONResponse:
        runtime.verify_token(x_node_token)
        response = runtime.run_direct_job(request)
        return JSONResponse(status_code=200, content=response.model_dump())

    @app.get("/api/v1/results/{run_id}")
    def get_result(run_id: str, x_node_token: str | None = Header(default=None)) -> dict[str, Any]:
        runtime.verify_token(x_node_token)
        try:
            return {"ok": True, "run_id": run_id, "result": runtime.get_result(run_id)}
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the agent service."""
    parser = argparse.ArgumentParser(description="mc-netprobe persistent agent")
    parser.add_argument("--config", default="config/agent/agent.yaml")
    parser.add_argument("--panel-url", dest="panel_url")
    parser.add_argument("--pair-code", dest="pair_code")
    parser.add_argument("--node-name", dest="node_name")
    parser.add_argument("--role", dest="role", choices=["client", "relay", "server"])
    parser.add_argument("--runtime-mode", dest="runtime_mode", choices=["docker-linux", "native-macos", "native-windows"])
    parser.add_argument("--listen-host", dest="listen_host", default=None)
    parser.add_argument("--listen-port", dest="listen_port", type=int, default=None)
    parser.add_argument("--advertise-url", dest="advertise_url")
    parser.add_argument("--node-token", dest="node_token")
    return parser


def main() -> int:
    """Run the agent HTTP service with the persisted config."""
    args = build_parser().parse_args()
    overrides = {key: value for key, value in vars(args).items() if key != "config" and value is not None}
    runtime = AgentRuntime(config_path=args.config, overrides=overrides, start_background=False)
    app = create_agent_app(config_path=args.config, overrides=overrides, start_background=True, runtime=runtime)
    config = runtime.config
    uvicorn.run(app, host=config.listen_host, port=config.listen_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
