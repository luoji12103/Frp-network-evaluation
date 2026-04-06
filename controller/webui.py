"""FastAPI-based monitoring panel for persistent agents."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote

import uvicorn
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
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
    PublicDashboardSnapshot,
)
from controller.panel_orchestrator import PanelOrchestrator
from controller.panel_store import PanelStore


RESULTS_DIR = Path("results")
ADMIN_TEMPLATE_PATH = Path(__file__).with_name("webui_template.html")
PUBLIC_TEMPLATE_PATH = Path(__file__).with_name("public_webui_template.html")
LOGIN_TEMPLATE_PATH = Path(__file__).with_name("login_template.html")
ADMIN_COOKIE_NAME = "mc_netprobe_admin"


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


class AdminAuth:
    """Cookie-based administrator authentication for the management UI."""

    def __init__(
        self,
        username: str | None = None,
        password: str | None = None,
        password_path: str | Path = "data/admin-password.txt",
        secret_path: str | Path = "data/admin-session-secret.txt",
        session_ttl_sec: int = 12 * 60 * 60,
    ) -> None:
        self.username = username or os.getenv("MC_NETPROBE_ADMIN_USERNAME", "admin")
        password_file = os.getenv("MC_NETPROBE_ADMIN_PASSWORD_FILE")
        secret_file = os.getenv("MC_NETPROBE_ADMIN_SESSION_SECRET_FILE")
        self.password_path = Path(password_file) if password_file else Path(password_path)
        self.secret_path = Path(secret_file) if secret_file else Path(secret_path)
        self.session_ttl_sec = int(os.getenv("MC_NETPROBE_ADMIN_SESSION_TTL_SEC", str(session_ttl_sec)))
        self.password = password or os.getenv("MC_NETPROBE_ADMIN_PASSWORD") or self._load_or_create_password()
        self.secret = self._load_or_create_secret()

    def verify_credentials(self, username: str, password: str) -> bool:
        return hmac.compare_digest(username, self.username) and hmac.compare_digest(password, self.password)

    def is_authenticated(self, request: Request) -> bool:
        cookie = request.cookies.get(ADMIN_COOKIE_NAME)
        session = self._parse_cookie(cookie)
        if session is None:
            return False
        session_user, expires_at = session
        return hmac.compare_digest(session_user, self.username) and expires_at >= int(time.time())

    def apply_login(self, response: RedirectResponse, secure: bool) -> None:
        response.set_cookie(
            key=ADMIN_COOKIE_NAME,
            value=self._issue_cookie_value(),
            max_age=self.session_ttl_sec,
            httponly=True,
            samesite="lax",
            secure=secure,
            path="/",
        )

    def clear_login(self, response: RedirectResponse) -> None:
        response.delete_cookie(ADMIN_COOKIE_NAME, path="/")

    def _issue_cookie_value(self) -> str:
        expires_at = str(int(time.time()) + self.session_ttl_sec)
        payload = f"{self.username}|{expires_at}"
        encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")
        signature = self._sign(payload)
        return f"{encoded}.{signature}"

    def _parse_cookie(self, cookie: str | None) -> tuple[str, int] | None:
        if not cookie or "." not in cookie:
            return None
        encoded, provided_signature = cookie.rsplit(".", 1)
        try:
            padded = encoded + ("=" * (-len(encoded) % 4))
            payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
            username, expires_at_text = payload.split("|", 1)
            expires_at = int(expires_at_text)
        except Exception:
            return None
        expected_signature = self._sign(payload)
        if not hmac.compare_digest(provided_signature, expected_signature):
            return None
        return username, expires_at

    def _sign(self, payload: str) -> str:
        return hmac.new(
            self.secret.encode("utf-8"),
            f"{payload}|{self.password}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _load_or_create_password(self) -> str:
        self.password_path.parent.mkdir(parents=True, exist_ok=True)
        if self.password_path.exists():
            value = self.password_path.read_text(encoding="utf-8").strip()
            if value:
                return value
        value = secrets.token_urlsafe(18)
        self.password_path.write_text(f"{value}\n", encoding="utf-8")
        try:
            self.password_path.chmod(0o600)
        except OSError:
            pass
        print(f"Generated panel admin password at {self.password_path}")
        return value

    def _load_or_create_secret(self) -> str:
        self.secret_path.parent.mkdir(parents=True, exist_ok=True)
        if self.secret_path.exists():
            value = self.secret_path.read_text(encoding="utf-8").strip()
            if value:
                return value
        value = secrets.token_hex(32)
        self.secret_path.write_text(f"{value}\n", encoding="utf-8")
        try:
            self.secret_path.chmod(0o600)
        except OSError:
            pass
        return value


def build_parser() -> argparse.ArgumentParser:
    """Build CLI args for the panel server."""
    parser = argparse.ArgumentParser(description="mc-netprobe monitoring panel")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8765, type=int)
    parser.add_argument("--db-path", default="data/monitor.db")
    return parser


def create_app(
    db_path: str | Path = "data/monitor.db",
    start_background: bool = True,
    admin_username: str | None = None,
    admin_password: str | None = None,
) -> FastAPI:
    runtime = PanelRuntime(db_path=db_path, start_background=start_background)
    admin_auth = AdminAuth(username=admin_username, password=admin_password)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        app.state.admin_auth = admin_auth
        runtime.start()
        yield
        runtime.stop()

    app = FastAPI(title="mc-netprobe-panel", version="1.0", lifespan=lifespan)

    def render_template(path: Path, **context: Any) -> HTMLResponse:
        template = Template(path.read_text(encoding="utf-8"))
        return HTMLResponse(content=template.render(**context))

    def render_login_page(next_path: str, error_key: str = "", status_code: int = 200) -> HTMLResponse:
        template = Template(LOGIN_TEMPLATE_PATH.read_text(encoding="utf-8"))
        body = template.render(
            next_path=next_path,
            login_error_key_json=json.dumps(error_key, ensure_ascii=False),
        )
        return HTMLResponse(content=body, status_code=status_code)

    def require_admin_api(request: Request) -> None:
        if not admin_auth.is_authenticated(request):
            raise HTTPException(status_code=401, detail="Admin login required")

    @app.get("/", response_class=HTMLResponse)
    def public_dashboard_page():
        snapshot = runtime.store.build_public_dashboard_snapshot()
        return render_template(
            PUBLIC_TEMPLATE_PATH,
            initial_state_json=json.dumps(snapshot, ensure_ascii=False),
        )

    @app.get("/admin", response_class=HTMLResponse)
    def dashboard_page(request: Request):
        if not admin_auth.is_authenticated(request):
            return RedirectResponse(url=f"/login?next={quote('/admin', safe='/')}", status_code=303)
        snapshot = runtime.store.build_dashboard_snapshot()
        return render_template(
            ADMIN_TEMPLATE_PATH,
            initial_state_json=json.dumps(snapshot, ensure_ascii=False),
        )

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request):
        if admin_auth.is_authenticated(request):
            return RedirectResponse(url="/admin", status_code=303)
        next_path = _normalize_next_path(request.query_params.get("next", "/admin"))
        return render_login_page(next_path=next_path)

    @app.post("/login")
    async def login_action(request: Request):
        form = await _parse_form_body(request)
        username = form.get("username", "").strip()
        password = form.get("password", "")
        next_path = _normalize_next_path(form.get("next", "/admin"))
        if not admin_auth.verify_credentials(username=username, password=password):
            return render_login_page(next_path=next_path, error_key="invalidCredentials", status_code=401)
        response = RedirectResponse(url=next_path, status_code=303)
        admin_auth.apply_login(response, secure=request.url.scheme == "https")
        return response

    @app.post("/logout")
    def logout():
        response = RedirectResponse(url="/", status_code=303)
        admin_auth.clear_login(response)
        return response

    @app.get("/api/state")
    def legacy_state() -> dict[str, Any]:
        return runtime.store.build_public_dashboard_snapshot()

    @app.get("/api/v1/public-dashboard")
    def public_dashboard() -> PublicDashboardSnapshot:
        return PublicDashboardSnapshot.model_validate(runtime.store.build_public_dashboard_snapshot())

    @app.get("/api/v1/dashboard")
    def dashboard(request: Request) -> DashboardSnapshot:
        require_admin_api(request)
        return DashboardSnapshot.model_validate(runtime.store.build_dashboard_snapshot())

    @app.post("/api/v1/dashboard")
    def save_dashboard_settings(payload: PanelSettings, request: Request) -> dict[str, Any]:
        require_admin_api(request)
        runtime.store.update_settings(payload)
        runtime.store.update_schedule_intervals(payload)
        return {"ok": True, "settings": runtime.store.get_settings().model_dump()}

    @app.get("/api/v1/history")
    def history(
        request: Request,
        node: str | None = None,
        probe_name: str | None = None,
        metric_name: str | None = None,
        time_range: str = "24h",
    ) -> HistoryResponse:
        require_admin_api(request)
        hours = _parse_time_range(time_range)
        return HistoryResponse(samples=runtime.store.query_history(node=node, probe_name=probe_name, metric_name=metric_name, time_range_hours=hours))

    @app.post("/api/v1/nodes")
    def upsert_node(payload: NodeUpsertRequest, request: Request) -> dict[str, Any]:
        require_admin_api(request)
        return {"ok": True, "node": runtime.store.upsert_node(payload)}

    @app.get("/api/v1/nodes/{node_id}")
    def get_node(node_id: int, request: Request) -> dict[str, Any]:
        require_admin_api(request)
        node = runtime.store.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="Node not found")
        return node

    @app.post("/api/v1/nodes/{node_id}/pair-code")
    def create_pair_code(node_id: int, request: Request) -> PairCodeResponse:
        require_admin_api(request)
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
    def start_manual_run(payload: ManualRunRequest, request: Request) -> JSONResponse:
        require_admin_api(request)
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


def _normalize_next_path(value: str | None) -> str:
    if not value:
        return "/admin"
    candidate = value.strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return "/admin"
    return candidate


async def _parse_form_body(request: Request) -> dict[str, str]:
    body = await request.body()
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[-1] if values else "" for key, values in parsed.items()}


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
