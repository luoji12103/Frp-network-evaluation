"""Simple built-in Web UI for configuring and running network tests."""

from __future__ import annotations

import argparse
import json
import os
import threading
import traceback
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml
from jinja2 import Template

from controller.pipeline import RunArtifacts, execute_run
from controller.scenario import (
    ScenariosConfig,
    ThresholdsConfig,
    TopologyConfig,
    load_scenarios,
    load_thresholds,
)


WEBUI_CONFIG_DIR = Path("config/webui")
WEBUI_TOPOLOGY_PATH = WEBUI_CONFIG_DIR / "topology.webui.yaml"
WEBUI_THRESHOLDS_PATH = WEBUI_CONFIG_DIR / "thresholds.webui.yaml"
WEBUI_SCENARIOS_PATH = WEBUI_CONFIG_DIR / "scenarios.webui.yaml"
RESULTS_DIR = Path("results")
TEMPLATE_PATH = Path(__file__).with_name("webui_template.html")


@dataclass(slots=True)
class RunRecord:
    """Serializable run metadata for the dashboard."""

    run_id: str
    status: str
    started_at: str
    finished_at: str | None = None
    error: str | None = None
    output_dir: str | None = None
    report_url: str | None = None
    raw_url: str | None = None
    findings_count: int = 0
    conclusion: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "output_dir": self.output_dir,
            "report_url": self.report_url,
            "raw_url": self.raw_url,
            "findings_count": self.findings_count,
            "conclusion": self.conclusion,
        }


class WebUIState:
    """In-memory state and persisted config for the dashboard."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: list[RunRecord] = []
        self._is_running = False
        self.config = load_dashboard_payload()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            latest = self._runs[0].to_dict() if self._runs else None
            return {
                "config": self.config,
                "is_running": self._is_running,
                "latest_run": latest,
                "runs": [record.to_dict() for record in self._runs[:10]],
            }

    def save_config(self, payload: dict[str, Any]) -> dict[str, Any]:
        warnings = collect_config_warnings(payload)
        topology = TopologyConfig.model_validate(payload["topology"])
        thresholds = ThresholdsConfig.model_validate(payload["thresholds"])
        scenarios = ScenariosConfig.model_validate(payload["scenarios"])

        WEBUI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        WEBUI_TOPOLOGY_PATH.write_text(yaml.safe_dump(topology.model_dump(), sort_keys=False, allow_unicode=True), encoding="utf-8")
        WEBUI_THRESHOLDS_PATH.write_text(yaml.safe_dump(thresholds.model_dump(), sort_keys=False, allow_unicode=True), encoding="utf-8")
        WEBUI_SCENARIOS_PATH.write_text(yaml.safe_dump(scenarios.model_dump(), sort_keys=False, allow_unicode=True), encoding="utf-8")
        with self._lock:
            self.config = payload
        return {"warnings": warnings}

    def start_run(self, payload: dict[str, Any]) -> RunRecord:
        errors = collect_run_blockers(payload)
        if errors:
            raise ValueError("\n".join(errors))

        self.save_config(payload)
        with self._lock:
            if self._is_running:
                raise RuntimeError("A test run is already in progress.")
            self._is_running = True
            run_id = datetime.now().astimezone().strftime("run-%Y%m%d-%H%M%S")
            record = RunRecord(
                run_id=run_id,
                status="running",
                started_at=datetime.now().astimezone().isoformat(),
            )
            self._runs.insert(0, record)

        thread = threading.Thread(target=self._run_background, args=(record.run_id,), daemon=True)
        thread.start()
        return record

    def _run_background(self, run_id: str) -> None:
        try:
            topology = TopologyConfig.model_validate(self.config["topology"])
            thresholds = ThresholdsConfig.model_validate(self.config["thresholds"])
            scenarios = ScenariosConfig.model_validate(self.config["scenarios"])
            artifacts = run_async_pipeline(
                topology=topology,
                thresholds=thresholds,
                scenarios=scenarios,
                run_id=run_id,
            )
            self._mark_run_completed(run_id, artifacts)
        except Exception as exc:  # pragma: no cover - defensive path
            self._mark_run_failed(run_id, f"{exc}\n\n{traceback.format_exc()}")

    def _mark_run_completed(self, run_id: str, artifacts: RunArtifacts) -> None:
        with self._lock:
            self._is_running = False
            record = self._find_record(run_id)
            record.status = "completed"
            record.finished_at = datetime.now().astimezone().isoformat()
            record.output_dir = str(artifacts.output_dir)
            record.report_url = "/" + artifacts.html_path.as_posix()
            record.raw_url = "/" + artifacts.raw_path.as_posix()
            record.findings_count = len(artifacts.run_result.threshold_findings)
            record.conclusion = artifacts.run_result.conclusion

    def _mark_run_failed(self, run_id: str, error: str) -> None:
        with self._lock:
            self._is_running = False
            record = self._find_record(run_id)
            record.status = "failed"
            record.finished_at = datetime.now().astimezone().isoformat()
            record.error = error

    def _find_record(self, run_id: str) -> RunRecord:
        for record in self._runs:
            if record.run_id == run_id:
                return record
        raise KeyError(run_id)


def run_async_pipeline(
    topology: TopologyConfig,
    thresholds: ThresholdsConfig,
    scenarios: ScenariosConfig,
    run_id: str,
) -> RunArtifacts:
    """Run the async pipeline from a background thread."""
    import asyncio

    return asyncio.run(
        execute_run(
            topology=topology,
            thresholds=thresholds,
            scenarios=scenarios,
            output_root=RESULTS_DIR,
            run_id=run_id,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the Web UI server."""
    parser = argparse.ArgumentParser(description="mc-netprobe Web UI")
    parser.add_argument("--host", default=os.environ.get("MC_NETPROBE_WEBUI_HOST", "127.0.0.1"))
    parser.add_argument("--port", default=int(os.environ.get("MC_NETPROBE_WEBUI_PORT", "8765")), type=int)
    parser.add_argument("--open-browser", action="store_true")
    return parser


def main() -> int:
    """Run the Web UI HTTP server."""
    args = build_parser().parse_args()
    state = WebUIState()
    handler = build_handler(state)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}"
    print(f"Web UI running at {url}")
    if args.open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Web UI.")
    finally:
        server.server_close()
    return 0


def build_handler(state: WebUIState) -> type[BaseHTTPRequestHandler]:
    """Bind app state into a request handler type."""

    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "mc-netprobe-webui/0.1"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._render_dashboard()
                return
            if parsed.path == "/api/state":
                self._send_json(HTTPStatus.OK, state.snapshot())
                return
            if parsed.path.startswith("/results/"):
                self._serve_file(parsed.path.lstrip("/"))
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            payload = self._read_json_payload()
            if parsed.path == "/api/save":
                try:
                    result = state.save_config(payload)
                    self._send_json(HTTPStatus.OK, {"ok": True, **result})
                except Exception as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            if parsed.path == "/api/run":
                try:
                    record = state.start_run(payload)
                    self._send_json(HTTPStatus.ACCEPTED, {"ok": True, "run": record.to_dict()})
                except RuntimeError as exc:
                    self._send_json(HTTPStatus.CONFLICT, {"ok": False, "error": str(exc)})
                except Exception as exc:
                    self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
                return
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

        def _render_dashboard(self) -> None:
            snapshot = state.snapshot()
            template = Template(TEMPLATE_PATH.read_text(encoding="utf-8"))
            html = template.render(
                initial_config_json=json.dumps(snapshot["config"], ensure_ascii=False),
                initial_state_json=json.dumps(snapshot, ensure_ascii=False),
            )
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_payload(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            return json.loads(raw.decode("utf-8") or "{}")

        def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _serve_file(self, relative_path: str) -> None:
            file_path = (Path.cwd() / relative_path).resolve()
            results_root = RESULTS_DIR.resolve()
            if results_root not in file_path.parents and file_path != results_root:
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "Forbidden"})
                return
            if not file_path.exists() or not file_path.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "File not found"})
                return

            data = file_path.read_bytes()
            content_type = "text/plain; charset=utf-8"
            if file_path.suffix == ".html":
                content_type = "text/html; charset=utf-8"
            elif file_path.suffix == ".json":
                content_type = "application/json; charset=utf-8"
            elif file_path.suffix == ".csv":
                content_type = "text/csv; charset=utf-8"

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return DashboardHandler


def load_dashboard_payload() -> dict[str, Any]:
    """Load persisted dashboard config or build a remote-ready default."""
    topology_payload = None
    thresholds_payload = None
    scenarios_payload = None

    if WEBUI_TOPOLOGY_PATH.exists():
        topology_payload = yaml.safe_load(WEBUI_TOPOLOGY_PATH.read_text(encoding="utf-8"))
    if WEBUI_THRESHOLDS_PATH.exists():
        thresholds_payload = yaml.safe_load(WEBUI_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    if WEBUI_SCENARIOS_PATH.exists():
        scenarios_payload = yaml.safe_load(WEBUI_SCENARIOS_PATH.read_text(encoding="utf-8"))

    if topology_payload is None:
        topology_payload = build_default_topology_payload()
    if thresholds_payload is None:
        thresholds_payload = load_thresholds("config/thresholds.example.yaml").model_dump()
    if scenarios_payload is None:
        scenarios_payload = load_scenarios("config/scenarios.example.yaml").model_dump()

    return {
        "topology": topology_payload,
        "thresholds": thresholds_payload,
        "scenarios": scenarios_payload,
    }


def build_default_topology_payload() -> dict[str, Any]:
    """Build a remote-oriented default topology for the dashboard."""
    return {
        "project_name": "mc-frp-netprobe-webui",
        "nodes": {
            "client": {
                "role": "client",
                "host": "",
                "os": "windows",
                "local": False,
                "ssh_user": "",
                "ssh_port": 22,
                "project_root": "",
                "python_bin": "python",
            },
            "relay": {
                "role": "relay",
                "host": "",
                "os": "linux",
                "local": False,
                "ssh_user": "",
                "ssh_port": 22,
                "project_root": "",
                "python_bin": "python3",
            },
            "server": {
                "role": "server",
                "host": "",
                "os": "macos",
                "local": False,
                "ssh_user": "",
                "ssh_port": 22,
                "project_root": "",
                "python_bin": "python3",
            },
        },
        "services": {
            "relay_probe": {"host": "", "port": 22},
            "mc_public": {"host": "", "port": 25565},
            "iperf_public": {"host": "", "port": 5201},
            "mc_local": {"host": "127.0.0.1", "port": 25565},
            "iperf_local": {"host": "0.0.0.0", "port": 5201},
        },
    }


def collect_config_warnings(payload: dict[str, Any]) -> list[str]:
    """Return soft warnings for incomplete dashboard values."""
    warnings: list[str] = []
    for node_name, node in payload.get("topology", {}).get("nodes", {}).items():
        host = str(node.get("host", "")).strip()
        if not host:
            warnings.append(f"{node_name}.host is empty")
        if not node.get("local", False):
            for field_name in ("ssh_user", "project_root", "python_bin"):
                if not str(node.get(field_name, "")).strip():
                    warnings.append(f"{node_name}.{field_name} is empty")
    for service_name in ("mc_public", "iperf_public"):
        service = payload.get("topology", {}).get("services", {}).get(service_name, {})
        if not str(service.get("host", "")).strip():
            warnings.append(f"services.{service_name}.host is empty")
    return warnings


def collect_run_blockers(payload: dict[str, Any]) -> list[str]:
    """Return blocking validation errors before starting a run."""
    blockers: list[str] = []
    topology = payload.get("topology", {})
    nodes = topology.get("nodes", {})
    services = topology.get("services", {})

    for node_name in ("client", "relay", "server"):
        node = nodes.get(node_name, {})
        if not str(node.get("host", "")).strip():
            blockers.append(f"{node_name} host is required")
        if not node.get("local", False):
            for field_name in ("ssh_user", "project_root", "python_bin"):
                if not str(node.get(field_name, "")).strip():
                    blockers.append(f"{node_name} {field_name} is required for remote execution")
    for service_name in ("relay_probe", "mc_public", "iperf_public", "mc_local", "iperf_local"):
        service = services.get(service_name, {})
        if not str(service.get("host", "")).strip():
            blockers.append(f"{service_name} host is required")
        if not service.get("port"):
            blockers.append(f"{service_name} port is required")
    return blockers


if __name__ == "__main__":
    raise SystemExit(main())
