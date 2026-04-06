"""FastAPI-based monitoring panel for persistent agents."""

from __future__ import annotations

import argparse
import json
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from jinja2 import Template

from controller.agent_http_client import AgentHttpClient
from controller.panel_models import (
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    AgentPairRequest,
    AgentPairResponse,
    DashboardSnapshot,
    HistoryResponse,
    ManualRunRequest,
    NodeUpsertRequest,
    PairCodeResponse,
    PanelJobDispatch,
    PanelSettings,
)
from controller.panel_orchestrator import PanelOrchestrator
from controller.panel_store import PanelStore


RESULTS_DIR = Path("results")
TEMPLATE_PATH = Path(__file__).with_name("webui_template.html")


class PanelRuntime:
    """Own long-lived services backing the FastAPI panel."""

    def __init__(self, db_path: str | Path = "data/monitor.db", start_background: bool = True) -> None:
        self.store = PanelStore(db_path=db_path)
        self.orchestrator = PanelOrchestrator(store=self.store, output_root=RESULTS_DIR)
        self.http = AgentHttpClient(store=self.store)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_background = start_background

    def start(self) -> None:
        if not self._start_background or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            self.store.mark_stale_nodes(stale_after_sec=45)
            self._refresh_pull_health()
            if not self.store.has_active_run():
                for schedule in self.store.due_schedules():
                    self.store.mark_schedule_dispatched(schedule_id=int(schedule["id"]), interval_sec=int(schedule["interval_sec"]))
                    if not self._schedule_ready(str(schedule["run_kind"])):
                        continue
                    started = self.orchestrator.run_scheduled_due(run_kind=str(schedule["run_kind"]))
                    if started is not None:
                        break
            self._stop_event.wait(3.0)

    def _refresh_pull_health(self) -> None:
        for node in self.store.list_nodes():
            if not node["paired"] or not node["agent_url"]:
                continue
            try:
                self.http.check_status(node)
                self.store.update_pull_status(int(node["id"]), ok=True)
            except Exception as exc:
                self.store.update_pull_status(int(node["id"]), ok=False, error=str(exc))

    def _schedule_ready(self, run_kind: str) -> bool:
        nodes = {role: self.store.get_node_by_role(role) for role in ("client", "relay", "server")}
        paired_enabled = [node for node in nodes.values() if node and node["paired"] and node["enabled"]]
        if run_kind == "system":
            return bool(paired_enabled)
        return len(paired_enabled) == 3


def build_parser() -> argparse.ArgumentParser:
    """Build CLI args for the panel server."""
    parser = argparse.ArgumentParser(description="mc-netprobe monitoring panel")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--db-path", default="data/monitor.db")
    return parser


def create_app(db_path: str | Path = "data/monitor.db", start_background: bool = True) -> FastAPI:
    runtime = PanelRuntime(db_path=db_path, start_background=start_background)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        runtime.start()
        yield
        runtime.stop()

    app = FastAPI(title="mc-netprobe-panel", version="1.0", lifespan=lifespan)

    @app.get("/", response_class=HTMLResponse)
    def dashboard_page() -> HTMLResponse:
        template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
        snapshot = runtime.store.build_dashboard_snapshot()
        body = template.render(initial_state_json=json.dumps(snapshot, ensure_ascii=False))
        return HTMLResponse(content=body)

    @app.get("/api/state")
    def legacy_state() -> dict[str, Any]:
        return runtime.store.build_dashboard_snapshot()

    @app.get("/api/v1/dashboard")
    def dashboard() -> DashboardSnapshot:
        return DashboardSnapshot.model_validate(runtime.store.build_dashboard_snapshot())

    @app.post("/api/v1/dashboard")
    def save_dashboard_settings(payload: PanelSettings) -> dict[str, Any]:
        runtime.store.update_settings(payload)
        runtime.store.update_schedule_intervals(payload)
        return {"ok": True, "settings": runtime.store.get_settings().model_dump()}

    @app.get("/api/v1/history")
    def history(node: str | None = None, probe_name: str | None = None, metric_name: str | None = None, time_range: str = "24h") -> HistoryResponse:
        hours = _parse_time_range(time_range)
        return HistoryResponse(samples=runtime.store.query_history(node=node, probe_name=probe_name, metric_name=metric_name, time_range_hours=hours))

    @app.post("/api/v1/nodes")
    def upsert_node(payload: NodeUpsertRequest) -> dict[str, Any]:
        return {"ok": True, "node": runtime.store.upsert_node(payload)}

    @app.get("/api/v1/nodes/{node_id}")
    def get_node(node_id: int) -> dict[str, Any]:
        node = runtime.store.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="Node not found")
        return node

    @app.post("/api/v1/nodes/{node_id}/pair-code")
    def create_pair_code(node_id: int, request: Request) -> PairCodeResponse:
        node = runtime.store.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="Node not found")
        pair_code, expires_at = runtime.store.create_pair_code(node_id=node_id)
        panel_url = str(request.base_url).rstrip("/")
        startup_command, fallback_command = build_startup_commands(node=node, panel_url=panel_url, pair_code=pair_code)
        return PairCodeResponse(
            node_id=node_id,
            node_name=str(node["node_name"]),
            pair_code=pair_code,
            expires_at=expires_at,
            startup_command=startup_command,
            fallback_command=fallback_command,
        )

    @app.post("/api/v1/agents/pair")
    def pair_agent(payload: AgentPairRequest, request: Request) -> AgentPairResponse:
        node, node_token = runtime.store.pair_agent(
            node_name=payload.node_name,
            role=payload.role,
            runtime_mode=payload.runtime_mode,
            pair_code=payload.pair_code,
            agent_url=payload.agent_url,
            advertise_url=payload.advertise_url,
        )
        advertise_url = payload.advertise_url or payload.agent_url or node.get("agent_url")
        return AgentPairResponse(
            node_id=int(node["id"]),
            topology_id=int(node["topology_id"]),
            node_token=node_token,
            panel_url=str(request.base_url).rstrip("/"),
            node_name=payload.node_name,
            role=payload.role,
            listen_host=payload.listen_host,
            listen_port=payload.listen_port,
            advertise_url=advertise_url,
        )

    @app.post("/api/v1/agents/heartbeat")
    def agent_heartbeat(payload: AgentHeartbeatRequest, x_node_token: str | None = Header(default=None)) -> AgentHeartbeatResponse:
        if not x_node_token:
            raise HTTPException(status_code=401, detail="Missing node token")
        try:
            node = runtime.store.resolve_node_from_token(payload.node_name, x_node_token)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        for completed in payload.completed_jobs:
            runtime.store.complete_job(job_id=completed.job_id, result=completed.result)

        runtime.store.record_heartbeat(node_id=int(node["id"]), agent_url=payload.advertise_url or payload.agent_url, status=payload.status)
        jobs = [
            PanelJobDispatch(
                job_id=int(job["id"]),
                task=str(job["job_kind"]),
                payload=json.loads(job["payload_json"]),
                created_at=str(job["created_at"]),
            )
            for job in runtime.store.lease_jobs(node_id=int(node["id"]))
        ]
        return AgentHeartbeatResponse(ok=True, jobs=jobs)

    @app.post("/api/v1/runs")
    def start_manual_run(payload: ManualRunRequest) -> JSONResponse:
        if runtime.store.has_active_run():
            raise HTTPException(status_code=409, detail="A monitoring run is already in progress")
        run_id = runtime.orchestrator.start_run_in_background(run_kind=payload.run_kind, source=payload.source)
        return JSONResponse(status_code=202, content={"ok": True, "run_id": run_id, "status": "running"})

    @app.get("/results/{relative_path:path}")
    def serve_result(relative_path: str) -> FileResponse:
        target = (RESULTS_DIR / relative_path).resolve()
        if RESULTS_DIR.resolve() not in target.parents and target != RESULTS_DIR.resolve():
            raise HTTPException(status_code=403, detail="Forbidden")
        if not target.exists():
            raise HTTPException(status_code=404, detail="Result not found")
        return FileResponse(target)

    return app


def build_startup_commands(node: dict[str, Any], panel_url: str, pair_code: str) -> tuple[str, str | None]:
    """Build primary and fallback node startup commands."""
    quoted_panel = panel_url
    node_name = str(node["node_name"])
    role = str(node["role"])
    runtime_mode = str(node["runtime_mode"])
    if runtime_mode == "docker-linux":
        command = (
            f"PANEL_URL='{quoted_panel}' PAIR_CODE='{pair_code}' NODE_NAME='{node_name}' ROLE='{role}' "
            "RUNTIME_MODE='docker-linux' AGENT_PORT='9870' "
            "docker compose -f docker/relay-agent.compose.yml up -d --build"
        )
        fallback = (
            f"python3 -m agents.service --config config/agent/{role}.yaml --panel-url '{quoted_panel}' "
            f"--pair-code '{pair_code}' --node-name '{node_name}' --role '{role}' --runtime-mode 'docker-linux' "
            "--listen-host 0.0.0.0 --listen-port 9870"
        )
        return command, fallback
    if runtime_mode == "native-macos":
        command = (
            f"bash bin/install_server_agent_launchd.sh --panel-url '{quoted_panel}' --pair-code '{pair_code}' "
            f"--node-name '{node_name}' --role '{role}' --listen-port 9870"
        )
        fallback = (
            f"bash bin/start_agent_tmux.sh --config config/agent/{role}.yaml --panel-url '{quoted_panel}' "
            f"--pair-code '{pair_code}' --node-name '{node_name}' --role '{role}' "
            "--runtime-mode native-macos --listen-port 9870"
        )
        return command, fallback
    command = (
        "powershell -ExecutionPolicy Bypass -File bin/install_client_agent.ps1 "
        f"-PanelUrl '{quoted_panel}' -PairCode '{pair_code}' -NodeName '{node_name}' "
        f"-Role '{role}' -ListenPort 9870"
    )
    fallback = (
        "powershell -ExecutionPolicy Bypass -Command "
        f"\"python -m agents.service --config config/agent/{role}.yaml --panel-url '{quoted_panel}' "
        f"--pair-code '{pair_code}' --node-name '{node_name}' --role '{role}' "
        "--runtime-mode native-windows --listen-host 0.0.0.0 --listen-port 9870\""
    )
    return command, fallback


def _parse_time_range(time_range: str) -> int:
    value = time_range.strip().lower()
    if value.endswith("h"):
        value = value[:-1]
    try:
        return max(1, int(value))
    except ValueError:
        return 24


def main() -> int:
    """Run the monitoring panel."""
    args = build_parser().parse_args()
    app = create_app(db_path=args.db_path, start_background=True)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main())
