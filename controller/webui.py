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
from fastapi.staticfiles import StaticFiles
from jinja2 import Template

from controller.agent_http_client import AgentHttpClient, AgentHttpError
from controller.build_info import get_build_info
from controller.control_bridge_client import ControlBridgeClient, ControlBridgeError
from controller.panel_models import (
    AdminControlActionCreateResponse,
    AdminControlActionRequest,
    AlertAcknowledgeRequest,
    AlertSilenceRequest,
    AgentHeartbeatRequest,
    AgentHeartbeatResponse,
    AgentIdentity,
    AgentPairRequest,
    AgentPairResponse,
    AgentTaskDispatch,
    DashboardSnapshot,
    HistoryResponse,
    ManualRunRequest,
    NodeUpsertRequest,
    PairCodeResponse,
    PanelSettings,
    PublicDashboardSnapshot,
    BridgeActionResponse,
    RunEventEnvelope,
    SuggestedAction,
    SUPPORTED_AGENT_PROTOCOL_VERSION,
    VersionProbeResponse,
)
from controller.panel_orchestrator import PanelOrchestrator
from controller.panel_store import PanelStore
from probes.common import now_iso


RESULTS_DIR = Path("results")
ADMIN_TEMPLATE_PATH = Path(__file__).with_name("webui_template.html")
PUBLIC_TEMPLATE_PATH = Path(__file__).with_name("public_webui_template.html")
LOGIN_TEMPLATE_PATH = Path(__file__).with_name("login_template.html")
ASSETS_DIR = Path(__file__).with_name("assets")
ADMIN_COOKIE_NAME = "mc_netprobe_admin"


def _suggested_action(
    *,
    kind: str,
    target_kind: str,
    label: str,
    target_id: int | None = None,
    run_id: str | None = None,
    action_id: int | None = None,
    dangerous: bool = False,
) -> dict[str, Any]:
    return SuggestedAction(
        kind=kind,  # type: ignore[arg-type]
        target_kind=target_kind,  # type: ignore[arg-type]
        target_id=target_id,
        run_id=run_id,
        action_id=action_id,
        label=label,
        dangerous=dangerous,
    ).model_dump(exclude_none=True)


class PanelRuntime:
    """Own long-lived services backing the FastAPI panel."""

    def __init__(self, db_path: str | Path = "data/monitor.db", start_background: bool = True) -> None:
        self._panel_bridge_url = os.getenv("MC_NETPROBE_PANEL_CONTROL_BRIDGE_URL")
        self._panel_log_file = os.getenv("MC_NETPROBE_PANEL_LOG_FILE")
        self._build_info = get_build_info()
        self.store = PanelStore(db_path=db_path)
        self.orchestrator = PanelOrchestrator(store=self.store, output_root=RESULTS_DIR)
        self.http = AgentHttpClient(store=self.store)
        self.control = ControlBridgeClient(
            store=self.store,
            panel_bridge_url=self._panel_bridge_url,
            panel_bridge_token_path=os.getenv("MC_NETPROBE_PANEL_CONTROL_BRIDGE_TOKEN_FILE", "data/panel-control-bridge-token.txt"),
        )
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._start_background = start_background
        self._started_at = now_iso()
        self._scheduler_paused = False
        self._last_loop_at: str | None = None
        self._last_loop_error: str | None = None
        self._last_runtime_sync_at = 0.0
        self._panel_bridge_state: dict[str, Any] = {
            "runtime": {"state": "unknown", "checked_at": None, "last_error": None, "details": {}},
            "supervisor": {
                "control_available": False,
                "bridge_url": self._panel_bridge_url,
                "supervisor_state": "unknown",
                "process_state": "unknown",
                "pid_or_container_id": None,
                "log_location": None,
                "last_error": None,
                "checked_at": None,
            },
        }
        if self._panel_bridge_url:
            self.control.ensure_panel_bridge_token()

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
            self.run_maintenance_cycle()
            self._stop_event.wait(3.0)

    def run_maintenance_cycle(self, force_runtime_sync: bool = False) -> None:
        self._last_loop_at = now_iso()
        try:
            self.store.mark_stale_nodes(stale_after_sec=45)
            self._refresh_pull_health()
            self._refresh_runtime_state(force=force_runtime_sync)
            self._process_control_actions()
            if not self._scheduler_paused and not self.store.has_active_run():
                for schedule in self.store.due_schedules():
                    self.store.mark_schedule_dispatched(schedule_id=int(schedule["id"]), interval_sec=int(schedule["interval_sec"]))
                    if not self._schedule_ready(str(schedule["run_kind"])):
                        continue
                    started = self.orchestrator.run_scheduled_due(run_kind=str(schedule["run_kind"]))
                    if started is not None:
                        break
            self._last_loop_error = None
        except Exception as exc:  # pragma: no cover - defensive loop protection
            self._last_loop_error = str(exc)

    def _refresh_pull_health(self) -> None:
        for node in self.store.list_nodes():
            if not node["paired"]:
                continue
            if not node.get("capabilities", {}).get("pull_http", True) or not node.get("endpoints", {}).get("effective_pull_url"):
                self.store.reset_pull_status(int(node["id"]))
                continue
            try:
                self.http.check_status(node)
                self.store.update_pull_status(int(node["id"]), ok=True)
            except AgentHttpError as exc:
                self.store.update_pull_status(int(node["id"]), ok=False, error=str(exc), error_code=exc.code)
            except Exception as exc:
                self.store.update_pull_status(int(node["id"]), ok=False, error=str(exc), error_code="pull_request_failed")

    def _schedule_ready(self, run_kind: str) -> bool:
        nodes = {role: self.store.get_node_by_role(role) for role in ("client", "relay", "server")}
        paired_enabled = [node for node in nodes.values() if node and node["paired"] and node["enabled"]]
        if run_kind == "system":
            return bool(paired_enabled)
        return len(paired_enabled) == 3

    def pause_scheduler(self) -> dict[str, Any]:
        self._scheduler_paused = True
        return self.runtime_snapshot()

    def resume_scheduler(self) -> dict[str, Any]:
        self._scheduler_paused = False
        return self.runtime_snapshot()

    def panel_action_supported(self, action: str) -> bool:
        if action in {"status", "sync_runtime", "pause_scheduler", "resume_scheduler"}:
            return True
        if action == "tail_log":
            return bool(self._existing_panel_log_path() or self._panel_bridge_control_available())
        if action in {"restart", "stop"}:
            return self._panel_bridge_control_available()
        return False

    def panel_action_unavailable_reason(self, action: str) -> str | None:
        if self.panel_action_supported(action):
            return None
        if action == "start":
            return "Panel start is only available through the host bridge, not the WebUI"
        if action == "tail_log":
            return (
                "Panel log tailing requires either a configured panel control bridge "
                "or a native log file such as MC_NETPROBE_PANEL_LOG_FILE / logs/panel-native.log"
            )
        if action in {"restart", "stop"}:
            if self._panel_bridge_url:
                return "Panel control bridge is configured but currently unreachable; retry sync runtime after the bridge recovers"
            return (
                "Native panel deployments expose read-only runtime plus scheduler control; "
                f"{action} requires a configured panel control bridge"
            )
        return f"Action {action} is not available for this panel deployment"

    def runtime_snapshot(self) -> dict[str, Any]:
        bridge_runtime = dict(self._panel_bridge_state.get("runtime") or {})
        active_action = self.store.get_active_control_action("panel", None)
        details = {
            "started_at": self._started_at,
            "last_loop_at": self._last_loop_at,
            "scheduler_paused": self._scheduler_paused,
            "background_loop_active": self._thread is not None,
            "panel_release_version": self._build_info["release_version"],
            "panel_build_ref": self._build_info["build_ref"],
            "panel_version_label": self._build_info["display_label"],
            "deployment_mode": "docker-bridge" if self._panel_bridge_url else "native",
            "control_mode": "bridge-managed" if self._panel_bridge_url else "native-readonly",
            "control_bridge_configured": bool(self._panel_bridge_url),
            "available_actions": self._panel_available_actions(),
            "readonly_reason": self._panel_readonly_reason(),
            "active_action_id": active_action.get("id") if active_action else None,
            "active_action_summary": self._active_action_summary(active_action),
            "pid": os.getpid(),
            "db_path": str(self.store.db_path.resolve()),
            "log_location": self._panel_log_location(),
        }
        if self._panel_bridge_url and bridge_runtime:
            details["bridge_runtime_state"] = bridge_runtime.get("state")
            details["bridge_checked_at"] = bridge_runtime.get("checked_at")
            details["bridge_last_error"] = bridge_runtime.get("last_error")
            bridge_runtime_details = bridge_runtime.get("details") or {}
            if isinstance(bridge_runtime_details, dict) and bridge_runtime_details.get("bridge_error_code"):
                details["bridge_error_code"] = bridge_runtime_details.get("bridge_error_code")
        operator_summary, operator_severity, operator_recommended_step = self._panel_operator_hint(
            details=details,
            last_error=self._last_loop_error or (bridge_runtime.get("last_error") if self._panel_bridge_url else None),
        )
        details["operator_summary"] = operator_summary
        details["operator_severity"] = operator_severity
        details["operator_recommended_step"] = operator_recommended_step
        details["suggested_action"] = self._panel_suggested_action(
            details=details,
            last_error=self._last_loop_error or (bridge_runtime.get("last_error") if self._panel_bridge_url else None),
        )
        return {
            "runtime": {
                "state": "running",
                "checked_at": now_iso(),
                "last_error": self._last_loop_error or (bridge_runtime.get("last_error") if self._panel_bridge_url else None),
                "details": details,
            },
            "supervisor": self._panel_supervisor_snapshot(),
        }

    def admin_runtime_payload(self) -> dict[str, Any]:
        panel = self.runtime_snapshot()
        active_run = self.store.get_active_run()
        nodes = self._attach_run_attention(self.store.list_nodes(), active_run=active_run)
        return {
            "panel": panel,
            "nodes": nodes,
            "active_run": active_run,
            "attention": self._build_attention_payload(panel=panel, nodes=nodes, active_run=active_run),
        }

    def control_action_target_snapshot(self, action: dict[str, Any]) -> dict[str, Any]:
        target_kind = str(action.get("target_kind") or "")
        target_id = action.get("target_id")
        target_name = action.get("target_name")
        if target_kind == "node" and target_id is not None:
            active_run = self.store.get_active_run()
            nodes = self._attach_run_attention(self.store.list_nodes(), active_run=active_run)
            node = next((item for item in nodes if int(item.get("id") or 0) == int(target_id)), None)
            if node is not None:
                runtime_details = dict((node.get("runtime") or {}).get("details") or {})
                return {
                    "target_kind": "node",
                    "target_id": node.get("id"),
                    "target_name": node.get("node_name"),
                    "status": node.get("status"),
                    "runtime": node.get("runtime") or {},
                    "supervisor": node.get("supervisor") or {},
                    "connectivity": node.get("connectivity") or {},
                    "endpoints": node.get("endpoints") or {},
                    "operator_summary": runtime_details.get("operator_summary"),
                    "operator_severity": runtime_details.get("operator_severity"),
                    "operator_recommended_step": runtime_details.get("operator_recommended_step"),
                    "suggested_action": runtime_details.get("suggested_action"),
                    "active_run_id": runtime_details.get("active_run_id"),
                    "active_action_id": runtime_details.get("active_action_id"),
                }
        if target_kind == "panel":
            panel = self.runtime_snapshot()
            details = dict((panel.get("runtime") or {}).get("details") or {})
            return {
                "target_kind": "panel",
                "target_id": None,
                "target_name": "panel",
                "status": (panel.get("runtime") or {}).get("state"),
                "runtime": panel.get("runtime") or {},
                "supervisor": panel.get("supervisor") or {},
                "connectivity": None,
                "endpoints": None,
                "operator_summary": details.get("operator_summary"),
                "operator_severity": details.get("operator_severity"),
                "operator_recommended_step": details.get("operator_recommended_step"),
                "suggested_action": details.get("suggested_action"),
                "active_run_id": None,
                "active_action_id": details.get("active_action_id"),
            }
        return {
            "target_kind": target_kind or None,
            "target_id": target_id,
            "target_name": target_name,
            "status": None,
            "runtime": {},
            "supervisor": {},
            "connectivity": None,
            "endpoints": None,
            "operator_summary": None,
            "operator_severity": "info",
            "operator_recommended_step": None,
            "suggested_action": None,
            "active_run_id": None,
            "active_action_id": None,
        }

    def enrich_control_action(self, action: dict[str, Any], include_snapshot: bool = False) -> dict[str, Any]:
        snapshot = self.control_action_target_snapshot(action)
        runtime = snapshot.get("runtime") or {}
        runtime_details = runtime.get("details") or {}
        connectivity = snapshot.get("connectivity") or {}
        action["target_status"] = snapshot.get("status")
        action["target_runtime_state"] = runtime.get("state")
        action["target_attention_level"] = connectivity.get("attention_level")
        action["target_operator_summary"] = runtime_details.get("operator_summary") or snapshot.get("operator_summary")
        action["target_operator_severity"] = runtime_details.get("operator_severity") or snapshot.get("operator_severity") or "info"
        action["target_operator_recommended_step"] = (
            runtime_details.get("operator_recommended_step") or snapshot.get("operator_recommended_step")
        )
        action["target_suggested_action"] = runtime_details.get("suggested_action") or snapshot.get("suggested_action")
        action["target_active_run_id"] = snapshot.get("active_run_id")
        action["target_active_action_id"] = snapshot.get("active_action_id")
        if include_snapshot:
            action["target_snapshot"] = snapshot
        return action

    def _attach_run_attention(self, nodes: list[dict[str, Any]], active_run: dict[str, Any] | None) -> list[dict[str, Any]]:
        if active_run is None:
            return nodes
        progress = active_run.get("progress") or {}
        current_blocker = progress.get("current_blocker") or {}
        latest_probe = progress.get("latest_probe") or {}
        target_node_id = current_blocker.get("node_id") or latest_probe.get("node_id")
        target_node_name = current_blocker.get("node_name") or latest_probe.get("node_name")
        if not target_node_id and not target_node_name:
            return nodes
        if current_blocker.get("summary"):
            summary = str(current_blocker.get("summary"))
        else:
            summary = (
                f"Active run last touched {latest_probe.get('task') or 'probe'}"
                + (f" on {latest_probe.get('path_label')}" if latest_probe.get("path_label") else "")
            )
        severity = str(current_blocker.get("severity") or "info")
        attention_payload = {
            "run_id": active_run.get("run_id"),
            "summary": summary,
            "severity": severity,
            "node_id": target_node_id,
            "recommended_step": current_blocker.get("recommended_step") or progress.get("recommended_step"),
            "suggested_action": _suggested_action(
                kind="open_run",
                target_kind="run",
                run_id=str(active_run.get("run_id") or ""),
                label="View run",
            ),
        }
        for node in nodes:
            if target_node_id and int(node.get("id") or 0) != int(target_node_id):
                continue
            if not target_node_id and str(node.get("node_name") or "") != str(target_node_name):
                continue
            node["run_attention"] = attention_payload
            runtime_details = dict((node.get("runtime") or {}).get("details") or {})
            runtime_details["active_run_id"] = active_run.get("run_id")
            runtime_details["active_run_summary"] = summary
            runtime_details["active_run_severity"] = severity
            runtime_details["operator_summary"] = summary
            runtime_details["operator_severity"] = severity
            runtime_details["operator_recommended_step"] = attention_payload.get("recommended_step")
            runtime_details["suggested_action"] = attention_payload.get("suggested_action")
            node.setdefault("runtime", {})["details"] = runtime_details
            break
        return nodes

    def refresh_runtime_snapshots(self, force: bool = True) -> None:
        self._refresh_runtime_state(force=force)

    def _refresh_runtime_state(self, force: bool = False) -> None:
        if not force and (time.time() - self._last_runtime_sync_at) < 12.0:
            return
        self._last_runtime_sync_at = time.time()
        for node in self.store.list_nodes():
            if not node.get("paired"):
                continue
            try:
                bridge_state = self.control.node_runtime(node)
                self.store.update_node_runtime_summaries(
                    node_id=int(node["id"]),
                    runtime_summary=bridge_state.runtime.model_dump(),
                    supervisor_summary=bridge_state.supervisor.model_dump(),
                )
            except Exception as exc:
                runtime_summary, supervisor_summary = self._node_bridge_failure_payload(node=node, exc=exc)
                self.store.update_node_runtime_summaries(
                    node_id=int(node["id"]),
                    runtime_summary=runtime_summary,
                    supervisor_summary=supervisor_summary,
                )
        if not self._panel_bridge_url:
            self._panel_bridge_state = self.runtime_snapshot()
            return
        try:
            response = self.control.panel_runtime()
            self._panel_bridge_state = {
                "runtime": response.runtime.model_dump(),
                "supervisor": response.supervisor.model_dump(),
            }
        except Exception as exc:
            self._panel_bridge_state = self._panel_bridge_failure_state(exc)

    def _process_control_actions(self) -> None:
        for action in self.store.list_pending_control_actions(limit=8):
            self._execute_control_action(action)

    def _execute_control_action(self, action: dict[str, Any]) -> None:
        target_kind = str(action["target_kind"])
        target_id = action.get("target_id")
        name = str(action["action"])
        tail_lines = action.get("audit_payload", {}).get("request", {}).get("tail_lines")
        transport = "panel_internal" if target_kind == "panel" and name in {"pause_scheduler", "resume_scheduler"} else f"{target_kind}_bridge"
        node: dict[str, Any] | None = None
        self.store.start_control_action(int(action["id"]), transport=transport)
        try:
            if target_kind == "panel":
                response, result_summary = self._execute_panel_action(name=name, tail_lines=tail_lines)
            else:
                node = self.store.get_node(int(target_id))
                if node is None:
                    raise KeyError(f"Node {target_id} not found")
                response = self.control.node_action(node=node, action=name, tail_lines=tail_lines)
                self.store.update_node_runtime_summaries(
                    node_id=int(node["id"]),
                    runtime_summary=response.runtime.model_dump(),
                    supervisor_summary=response.supervisor.model_dump(),
                )
                result_summary = response.human_summary
            self.store.finish_control_action(
                int(action["id"]),
                status="completed",
                result_summary=result_summary,
                transport=transport,
                audit_payload={"response": response.model_dump()},
            )
        except Exception as exc:
            error_code = exc.code if isinstance(exc, (ControlBridgeError,)) else "control_action_failed"
            if target_kind == "panel" and isinstance(exc, ControlBridgeError):
                self._panel_bridge_state = self._panel_bridge_failure_state(exc)
            if target_kind == "node" and isinstance(exc, ControlBridgeError) and node is not None:
                runtime_summary, supervisor_summary = self._node_bridge_failure_payload(node=node, exc=exc)
                self.store.update_node_runtime_summaries(
                    node_id=int(node["id"]),
                    runtime_summary=runtime_summary,
                    supervisor_summary=supervisor_summary,
                )
            self.store.finish_control_action(
                int(action["id"]),
                status="failed",
                result_summary=None,
                error_code=error_code,
                error_detail=str(exc),
                transport=transport,
                audit_payload={"response": {"error": str(exc)}},
            )

    def _node_bridge_failure_payload(self, node: dict[str, Any], exc: Exception) -> tuple[dict[str, Any], dict[str, Any]]:
        error_code = exc.code if isinstance(exc, ControlBridgeError) else "control_bridge_unreachable"
        current = now_iso()
        return (
            {
                "state": "unknown",
                "checked_at": current,
                "last_error": str(exc),
                "details": {"bridge_error_code": error_code},
            },
            {
                "control_available": False,
                "bridge_url": node.get("endpoints", {}).get("control_bridge_url"),
                "supervisor_state": "unknown",
                "process_state": "unknown",
                "pid_or_container_id": None,
                "log_location": None,
                "last_error": str(exc),
                "checked_at": current,
            },
        )

    def _panel_bridge_failure_state(self, exc: Exception) -> dict[str, Any]:
        error_code = exc.code if isinstance(exc, ControlBridgeError) else "control_bridge_unreachable"
        current = now_iso()
        return {
            "runtime": {
                "state": "running",
                "checked_at": current,
                "last_error": str(exc),
                "details": {
                    "started_at": self._started_at,
                    "last_loop_at": self._last_loop_at,
                    "scheduler_paused": self._scheduler_paused,
                    "bridge_error_code": error_code,
                },
            },
            "supervisor": {
                "control_available": False,
                "bridge_url": self._panel_bridge_url,
                "supervisor_state": "unknown",
                "process_state": "unknown",
                "pid_or_container_id": None,
                "log_location": None,
                "last_error": str(exc),
                "checked_at": current,
            },
        }

    def _execute_panel_action(self, name: str, tail_lines: int | None) -> tuple[Any, str]:
        if name == "pause_scheduler":
            runtime_payload = self.pause_scheduler()
            return _panel_internal_bridge_response(runtime_payload, "Scheduler paused"), "Scheduler paused"
        if name == "resume_scheduler":
            runtime_payload = self.resume_scheduler()
            return _panel_internal_bridge_response(runtime_payload, "Scheduler resumed"), "Scheduler resumed"
        if name in {"status", "sync_runtime"}:
            self._refresh_runtime_state(force=True)
            runtime_payload = self.runtime_snapshot()
            summary = "Panel runtime synchronized" if name == "sync_runtime" else "Panel runtime reported"
            return _panel_internal_bridge_response(runtime_payload, summary), summary
        if name == "tail_log" and not self._panel_bridge_url:
            response = self._native_panel_tail_log(tail_lines=tail_lines or 40)
            self._panel_bridge_state = {
                "runtime": response.runtime.model_dump(),
                "supervisor": response.supervisor.model_dump(),
            }
            return response, response.human_summary
        if not self._panel_bridge_url:
            raise ControlBridgeError(
                "missing_panel_bridge",
                self.panel_action_unavailable_reason(name) or "Panel control bridge is not configured",
            )
        response = self.control.panel_action(action=name, tail_lines=tail_lines)
        self._panel_bridge_state = {
            "runtime": response.runtime.model_dump(),
            "supervisor": response.supervisor.model_dump(),
        }
        return response, response.human_summary

    def _panel_available_actions(self) -> list[str]:
        actions = ["sync_runtime", "pause_scheduler", "resume_scheduler"]
        if self._existing_panel_log_path() or self._panel_bridge_control_available():
            actions.append("tail_log")
        if self._panel_bridge_control_available():
            actions.extend(["restart", "stop"])
        return actions

    def _panel_bridge_control_available(self) -> bool:
        if not self._panel_bridge_url:
            return False
        supervisor = self._panel_bridge_state.get("supervisor") or {}
        if supervisor.get("checked_at") is None:
            return True
        return bool(supervisor.get("control_available"))

    def _panel_readonly_reason(self) -> str | None:
        if not self._panel_bridge_url:
            return "Native panel deployments expose read-only runtime, scheduler control, and optional local log tailing."
        if not self._panel_bridge_control_available():
            return "Panel control bridge is configured but currently unreachable; only scheduler control and any local log tailing remain available."
        return None

    def _panel_operator_hint(self, details: dict[str, Any], last_error: str | None) -> tuple[str | None, str, str | None]:
        if details.get("active_action_summary"):
            return (
                str(details.get("active_action_summary")),
                "info",
                "Open the action detail to follow progress before issuing another panel action.",
            )
        if last_error:
            return (
                str(last_error),
                "warning",
                "Sync runtime or inspect panel logs before issuing more control actions.",
            )
        readonly_reason = details.get("readonly_reason")
        if readonly_reason:
            return str(readonly_reason), "info", None
        if details.get("scheduler_paused"):
            return "Scheduler is paused.", "info", "Resume the scheduler when you are ready to restart automatic monitoring."
        return None, "info", None

    def _panel_suggested_action(self, details: dict[str, Any], last_error: str | None) -> dict[str, Any] | None:
        active_action_id = details.get("active_action_id")
        if active_action_id:
            return _suggested_action(
                kind="open_action",
                target_kind="action",
                action_id=int(active_action_id),
                label="View action",
            )
        available_actions = set(details.get("available_actions") or [])
        if last_error and "sync_runtime" in available_actions:
            return _suggested_action(
                kind="sync_runtime",
                target_kind="panel",
                label="Sync panel runtime",
            )
        readonly_reason = str(details.get("readonly_reason") or "")
        if readonly_reason and "tail_log" in available_actions:
            return _suggested_action(
                kind="tail_log",
                target_kind="panel",
                label="Tail panel log",
            )
        return None

    def _active_action_summary(self, action: dict[str, Any] | None) -> str | None:
        if not action:
            return None
        return f"{action.get('action')} ({action.get('status')})"

    def _build_attention_payload(
        self,
        panel: dict[str, Any],
        nodes: list[dict[str, Any]],
        active_run: dict[str, Any] | None,
    ) -> dict[str, Any]:
        items: list[dict[str, Any]] = []
        if active_run is not None:
            progress = active_run.get("progress") or {}
            phase = progress.get("active_phase")
            last_event = progress.get("last_event_message") or progress.get("last_event_kind")
            current_blocker = progress.get("current_blocker") or {}
            latest_queue_job = progress.get("latest_queue_job") or {}
            run_failure_code = current_blocker.get("code")
            queue_summary = ""
            if current_blocker.get("job_id"):
                queue_summary = (
                    f"; queue job {current_blocker.get('job_id')} "
                    f"{current_blocker.get('status') or current_blocker.get('code') or 'queued'}"
                )
            items.append(
                {
                    "severity": str(current_blocker.get("severity") or ("warning" if run_failure_code else "info")),
                    "kind": "run",
                    "title": "Monitoring run in progress",
                    "summary": (
                        f"{active_run.get('run_kind')} run {active_run.get('run_id')} is active"
                        + (f" in phase {phase}" if phase else "")
                        + (f"; latest event: {last_event}" if last_event else "")
                        + queue_summary
                    ),
                    "run_id": active_run.get("run_id"),
                    "code": run_failure_code,
                    "target_kind": "run",
                    "target_name": active_run.get("run_id"),
                    "suggested_action": _suggested_action(
                        kind="open_run",
                        target_kind="run",
                        run_id=str(active_run.get("run_id") or ""),
                        label="View run",
                    ),
                    "recommended_step": current_blocker.get("recommended_step")
                    or progress.get("recommended_step")
                    or "Open the run detail to follow progress before starting another monitoring run.",
                }
            )
            if current_blocker.get("kind") == "queue" and current_blocker.get("job_id"):
                lease_expires_at = current_blocker.get("lease_expires_at")
                items.append(
                    {
                        "severity": str(current_blocker.get("severity") or "info"),
                        "kind": "run-queue",
                        "title": "Queued job needs attention",
                        "summary": (
                            f"Job {current_blocker.get('job_id')} for {current_blocker.get('task') or 'queued task'} "
                            f"on {current_blocker.get('node_name') or 'node'} is "
                            f"{current_blocker.get('status') or current_blocker.get('code') or 'queued'}"
                            + (f"; lease expires at {lease_expires_at}" if lease_expires_at else "")
                        ),
                        "run_id": active_run.get("run_id"),
                        "code": run_failure_code or current_blocker.get("status"),
                        "target_kind": "run",
                        "target_name": active_run.get("run_id"),
                        "suggested_action": (
                            _suggested_action(
                                kind="open_node",
                                target_kind="node",
                                target_id=int(current_blocker["node_id"]),
                                label="Open node",
                            )
                            if current_blocker.get("node_id") is not None
                            else _suggested_action(
                                kind="open_run",
                                target_kind="run",
                                run_id=str(active_run.get("run_id") or ""),
                                label="View run",
                            )
                        ),
                        "recommended_step": current_blocker.get("recommended_step")
                        or progress.get("recommended_step")
                        or "Open the run detail and inspect the queued job timeline before rerunning the phase.",
                    }
                )

        panel_runtime = panel.get("runtime", {})
        panel_runtime_details = panel_runtime.get("details", {})
        panel_error = panel_runtime.get("last_error") or (panel.get("supervisor") or {}).get("last_error")
        if panel_runtime_details.get("active_action_id"):
            items.append(
                {
                    "severity": "info",
                    "kind": "panel-action",
                    "title": "Panel action in progress",
                    "summary": panel_runtime_details.get("active_action_summary") or "Panel lifecycle action is running.",
                    "code": None,
                    "target_kind": "panel",
                    "target_name": "panel",
                    "action_id": panel_runtime_details.get("active_action_id"),
                    "suggested_action": _suggested_action(
                        kind="open_action",
                        target_kind="action",
                        action_id=int(panel_runtime_details["active_action_id"]),
                        label="View action",
                    ),
                    "recommended_step": "Open the action detail to follow progress before issuing another panel action.",
                }
            )
        if panel_error:
            items.append(
                {
                    "severity": "warning",
                    "kind": "panel",
                    "title": "Panel runtime needs attention",
                    "summary": str(panel_error),
                    "code": panel_runtime_details.get("bridge_error_code") or "panel_runtime_error",
                    "target_kind": "panel",
                    "target_name": "panel",
                    "suggested_action": panel_runtime_details.get("suggested_action")
                    or _suggested_action(kind="open_panel", target_kind="panel", label="Open panel"),
                    "recommended_step": "Sync runtime or inspect panel logs before issuing more control actions.",
                }
            )

        for node in nodes:
            connectivity = node.get("connectivity") or {}
            level = str(connectivity.get("attention_level") or "ok")
            runtime_details = node.get("runtime", {}).get("details", {})
            supervisor = node.get("supervisor", {})
            if runtime_details.get("active_action_id"):
                items.append(
                    {
                        "severity": "info",
                        "kind": "node-action",
                        "title": f"{node.get('role')} action in progress",
                        "summary": runtime_details.get("active_action_summary") or "Node lifecycle action is running.",
                        "code": None,
                        "target_kind": "node",
                        "target_id": node.get("id"),
                        "target_name": node.get("node_name"),
                        "action_id": runtime_details.get("active_action_id"),
                        "suggested_action": _suggested_action(
                            kind="open_action",
                            target_kind="action",
                            action_id=int(runtime_details["active_action_id"]),
                            label="View action",
                        ),
                        "recommended_step": "Open the action detail to follow progress before issuing another lifecycle action for this node.",
                    }
                )
            if level != "ok":
                items.append(
                    {
                        "severity": level,
                        "kind": "node",
                        "title": f"{node.get('role')} node {node.get('status')}",
                        "summary": connectivity.get("summary"),
                        "code": connectivity.get("diagnostic_code"),
                        "target_kind": "node",
                        "target_id": node.get("id"),
                        "target_name": node.get("node_name"),
                        "suggested_action": runtime_details.get("suggested_action")
                        or _suggested_action(
                            kind="open_node",
                            target_kind="node",
                            target_id=int(node["id"]),
                            label="Open node",
                        ),
                        "recommended_step": connectivity.get("recommended_step"),
                    }
                )
            bridge_error_code = runtime_details.get("bridge_error_code")
            if bridge_error_code and supervisor.get("control_available") is False:
                items.append(
                    {
                        "severity": "warning",
                        "kind": "node-control",
                        "title": f"{node.get('role')} control bridge unavailable",
                        "summary": supervisor.get("last_error") or runtime_details.get("readonly_reason"),
                        "code": bridge_error_code,
                        "target_kind": "node",
                        "target_id": node.get("id"),
                        "target_name": node.get("node_name"),
                        "suggested_action": _suggested_action(
                            kind="open_node",
                            target_kind="node",
                            target_id=int(node["id"]),
                            label="Open node",
                        ),
                        "recommended_step": "Wait for the control bridge to recover or restart the host-managed bridge before issuing lifecycle actions.",
                    }
                )

        severity_order = {"error": 0, "warning": 1, "info": 2, "ok": 3}
        items.sort(key=lambda item: (severity_order.get(str(item.get("severity")), 99), str(item.get("title") or "")))
        summary = {
            "total": len(items),
            "error": sum(1 for item in items if item.get("severity") == "error"),
            "warning": sum(1 for item in items if item.get("severity") == "warning"),
            "info": sum(1 for item in items if item.get("severity") == "info"),
        }
        return {"summary": summary, "items": items[:8]}

    def _panel_supervisor_snapshot(self) -> dict[str, Any]:
        if self._panel_bridge_url:
            return dict(self._panel_bridge_state.get("supervisor") or {})
        return {
            "control_available": False,
            "bridge_url": None,
            "supervisor_state": "native-readonly",
            "process_state": "running",
            "pid_or_container_id": str(os.getpid()),
            "log_location": self._panel_log_location(),
            "last_error": self._last_loop_error,
            "checked_at": now_iso(),
        }

    def _configured_panel_log_path(self) -> Path | None:
        if not self._panel_log_file:
            return None
        return Path(self._panel_log_file).expanduser().resolve()

    def _existing_panel_log_path(self) -> Path | None:
        candidates: list[Path] = []
        configured = self._configured_panel_log_path()
        if configured is not None:
            candidates.append(configured)
        candidates.extend(
            [
                Path("logs/panel-native.log").resolve(),
                Path("logs/panel.log").resolve(),
                Path("logs/webui.log").resolve(),
            ]
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _panel_log_location(self) -> str | None:
        configured = self._configured_panel_log_path()
        if configured is not None:
            return str(configured)
        existing = self._existing_panel_log_path()
        return str(existing) if existing is not None else None

    def _native_panel_tail_log(self, tail_lines: int) -> BridgeActionResponse:
        log_path = self._existing_panel_log_path()
        if log_path is None:
            raise ControlBridgeError(
                "missing_panel_log",
                self.panel_action_unavailable_reason("tail_log") or "Native panel log file is not configured",
            )
        runtime_payload = self.runtime_snapshot()
        lines = _tail_local_file(log_path, tail_lines)
        return BridgeActionResponse(
            accepted=True,
            state=str(runtime_payload.get("runtime", {}).get("state") or "running"),
            human_summary=f"Read {len(lines)} log lines from {log_path}",
            runtime=runtime_payload.get("runtime", {}),
            supervisor=runtime_payload.get("supervisor", {}),
            raw_runtime=runtime_payload,
            log_location=str(log_path),
            log_excerpt=lines,
        )


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
    build_info = get_build_info()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.runtime = runtime
        app.state.admin_auth = admin_auth
        app.state.build_info = build_info
        runtime.start()
        yield
        runtime.stop()

    app = FastAPI(title="mc-netprobe-panel", version=str(build_info["release_version"]), lifespan=lifespan)
    if ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

    @app.middleware("http")
    async def attach_build_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-MC-Netprobe-Release-Version"] = str(build_info["release_version"])
        response.headers["X-MC-Netprobe-Build"] = str(build_info["header_label"])
        if build_info.get("build_ref"):
            response.headers["X-MC-Netprobe-Build-Ref"] = str(build_info["build_ref"])
        return response

    def build_payload() -> dict[str, str | None]:
        return {
            "release_version": build_info["release_version"],
            "build_ref": build_info["build_ref"],
            "display_label": build_info["display_label"],
            "header_label": build_info["header_label"],
        }

    def attach_build(payload: dict[str, Any]) -> dict[str, Any]:
        if "build" in payload:
            return payload
        enriched = dict(payload)
        enriched["build"] = build_payload()
        return enriched

    def render_template(path: Path, **context: Any) -> HTMLResponse:
        template = Template(path.read_text(encoding="utf-8"))
        return HTMLResponse(content=template.render(**context))

    def render_login_page(next_path: str, error_key: str = "", status_code: int = 200) -> HTMLResponse:
        template = Template(LOGIN_TEMPLATE_PATH.read_text(encoding="utf-8"))
        body = template.render(
            next_path=next_path,
            login_error_key_json=json.dumps(error_key, ensure_ascii=False),
            panel_build_label=build_info["display_label"],
        )
        return HTMLResponse(content=body, status_code=status_code)

    def require_admin_api(request: Request) -> None:
        if not admin_auth.is_authenticated(request):
            raise HTTPException(status_code=401, detail="Admin login required")

    @app.get("/", response_class=HTMLResponse)
    def public_dashboard_page():
        snapshot = runtime.store.build_public_dashboard_snapshot()
        snapshot["build"] = build_payload()
        return render_template(
            PUBLIC_TEMPLATE_PATH,
            initial_state_json=json.dumps(snapshot, ensure_ascii=False),
            panel_build_label=build_info["display_label"],
        )

    @app.get("/admin", response_class=HTMLResponse)
    def dashboard_page(request: Request):
        if not admin_auth.is_authenticated(request):
            return RedirectResponse(url=f"/login?next={quote('/admin', safe='/')}", status_code=303)
        snapshot = runtime.store.build_dashboard_snapshot()
        snapshot["build"] = build_payload()
        return render_template(
            ADMIN_TEMPLATE_PATH,
            initial_state_json=json.dumps(snapshot, ensure_ascii=False),
            panel_build_label=build_info["display_label"],
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
    def public_dashboard(time_range: str = "24h") -> PublicDashboardSnapshot:
        snapshot = runtime.store.build_public_dashboard_snapshot(time_range_hours=_parse_time_range(time_range))
        snapshot["build"] = build_payload()
        return PublicDashboardSnapshot.model_validate(snapshot)

    @app.get("/api/v1/dashboard")
    def dashboard(request: Request) -> DashboardSnapshot:
        require_admin_api(request)
        snapshot = runtime.store.build_dashboard_snapshot()
        snapshot["build"] = build_payload()
        return DashboardSnapshot.model_validate(snapshot)

    @app.get("/api/v1/version")
    def version_probe() -> VersionProbeResponse:
        return VersionProbeResponse(
            service="panel",
            build=build_payload(),
            started_at=runtime._started_at,
            protocol_version=SUPPORTED_AGENT_PROTOCOL_VERSION,
        )

    @app.post("/api/v1/dashboard")
    def save_dashboard_settings(payload: PanelSettings, request: Request) -> dict[str, Any]:
        require_admin_api(request)
        runtime.store.update_settings(payload)
        runtime.store.update_schedule_intervals(payload)
        return attach_build({"ok": True, "settings": runtime.store.get_settings().model_dump()})

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

    @app.get("/api/v1/admin/filters")
    def admin_filters(request: Request) -> dict[str, Any]:
        require_admin_api(request)
        return attach_build(runtime.store.list_filter_options())

    @app.get("/api/v1/admin/runtime")
    def admin_runtime(request: Request) -> dict[str, Any]:
        require_admin_api(request)
        runtime.refresh_runtime_snapshots(force=True)
        return attach_build(runtime.admin_runtime_payload())

    @app.get("/api/v1/admin/actions")
    def admin_actions(request: Request, limit: int = 50) -> dict[str, Any]:
        require_admin_api(request)
        actions = runtime.store.list_control_actions(limit=max(1, min(limit, 200)))
        return attach_build({"items": [runtime.enrich_control_action(action, include_snapshot=False) for action in actions]})

    @app.get("/api/v1/admin/actions/{action_id}")
    def admin_action_detail(action_id: int, request: Request) -> dict[str, Any]:
        require_admin_api(request)
        action = runtime.store.get_control_action(action_id)
        if action is None:
            raise HTTPException(status_code=404, detail="Action not found")
        return attach_build(runtime.enrich_control_action(action, include_snapshot=True))

    @app.get("/api/v1/admin/overview")
    def admin_overview(
        request: Request,
        time_range: str = "24h",
        role: str | None = None,
        node: str | None = None,
        path_label: str | None = None,
    ) -> dict[str, Any]:
        require_admin_api(request)
        return attach_build(runtime.store.build_admin_overview(
            time_range_hours=_parse_time_range(time_range),
            roles=_parse_csv_list(role),
            nodes=_parse_csv_list(node),
            path_labels=_parse_csv_list(path_label),
        ))

    @app.get("/api/v1/admin/timeseries")
    def admin_timeseries(
        request: Request,
        time_range: str = "24h",
        role: str | None = None,
        node: str | None = None,
        path_label: str | None = None,
        probe_name: str | None = None,
        metric_name: str | None = None,
        bucket: str = "auto",
    ) -> dict[str, Any]:
        require_admin_api(request)
        return attach_build(runtime.store.query_metric_series(
            time_range_hours=_parse_time_range(time_range),
            roles=_parse_csv_list(role),
            nodes=_parse_csv_list(node),
            path_labels=_parse_csv_list(path_label),
            probe_names=_parse_csv_list(probe_name),
            metric_name=metric_name,
            bucket=bucket,
        ))

    @app.get("/api/v1/admin/path-health")
    def admin_path_health(
        request: Request,
        time_range: str = "24h",
        role: str | None = None,
        node: str | None = None,
        path_label: str | None = None,
    ) -> dict[str, Any]:
        require_admin_api(request)
        return attach_build(runtime.store.build_path_health(
            time_range_hours=_parse_time_range(time_range),
            roles=_parse_csv_list(role),
            nodes=_parse_csv_list(node),
            path_labels=_parse_csv_list(path_label),
        ))

    @app.get("/api/v1/admin/runs")
    def admin_runs(
        request: Request,
        time_range: str = "24h",
        run_kind: str | None = None,
        status: str | None = None,
        path_label: str | None = None,
        has_findings: str | None = None,
    ) -> dict[str, Any]:
        require_admin_api(request)
        items = runtime.store.query_runs(
            time_range_hours=_parse_time_range(time_range),
            run_kinds=_parse_csv_list(run_kind),
            statuses=_parse_csv_list(status),
            path_labels=_parse_csv_list(path_label),
            has_findings=_parse_optional_bool(has_findings),
        )
        return attach_build({"items": items})

    @app.get("/api/v1/admin/runs/{run_id}")
    def admin_run_detail(run_id: str, request: Request) -> dict[str, Any]:
        require_admin_api(request)
        payload = runtime.store.get_run_detail(run_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return attach_build(payload)

    @app.get("/api/v1/admin/runs/{run_id}/events")
    def admin_run_events(run_id: str, request: Request) -> dict[str, Any]:
        require_admin_api(request)
        if runtime.store.get_run_detail(run_id) is None:
            raise HTTPException(status_code=404, detail="Run not found")
        items = [RunEventEnvelope.model_validate(item).model_dump() for item in runtime.store.list_run_events(run_id)]
        return attach_build({"items": items})

    @app.get("/api/v1/admin/alerts")
    def admin_alerts(
        request: Request,
        time_range: str = "24h",
        severity: str | None = None,
        status: str | None = None,
        kind: str | None = None,
        path_label: str | None = None,
        metric_name: str | None = None,
        acknowledged: str | None = None,
        anomaly_only: bool = False,
        fingerprint: str | None = None,
    ) -> dict[str, Any]:
        require_admin_api(request)
        return attach_build(runtime.store.query_alert_events(
            time_range_hours=_parse_time_range(time_range),
            severities=_parse_csv_list(severity),
            statuses=_parse_csv_list(status),
            kinds=_parse_csv_list(kind),
            path_labels=_parse_csv_list(path_label),
            metric_names=_parse_csv_list(metric_name),
            acknowledged=_parse_optional_bool(acknowledged),
            anomaly_only=anomaly_only,
            fingerprint=fingerprint,
        ))

    @app.post("/api/v1/admin/alerts/{alert_id}/ack")
    def admin_ack_alert(alert_id: int, payload: AlertAcknowledgeRequest, request: Request) -> dict[str, Any]:
        require_admin_api(request)
        alert = runtime.store.acknowledge_alert(alert_id=alert_id, actor=payload.actor)
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        return attach_build({"ok": True, "alert": alert})

    @app.post("/api/v1/admin/alerts/{alert_id}/silence")
    def admin_silence_alert(alert_id: int, payload: AlertSilenceRequest, request: Request) -> dict[str, Any]:
        require_admin_api(request)
        alert = runtime.store.silence_alert(
            alert_id=alert_id,
            silenced_until=payload.silenced_until,
            reason=payload.reason,
            actor=payload.actor,
        )
        if alert is None:
            raise HTTPException(status_code=404, detail="Alert not found")
        return attach_build({"ok": True, "alert": alert})

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

    @app.post("/api/v1/admin/nodes/{node_id}/actions")
    def admin_node_action(node_id: int, payload: AdminControlActionRequest, request: Request) -> AdminControlActionCreateResponse:
        require_admin_api(request)
        node = runtime.store.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="Node not found")
        unavailable_reason = _node_action_unavailable_reason(node=node, action=payload.action)
        if unavailable_reason is not None:
            raise HTTPException(status_code=409, detail=unavailable_reason)
        conflict = runtime.store.get_active_control_action("node", node_id)
        if conflict is not None:
            raise HTTPException(
                status_code=409,
                detail=_control_action_conflict_detail(
                    target_name=str(node.get("node_name") or node_id),
                    conflict=conflict,
                ),
            )
        confirmation_token = _validate_or_issue_confirmation_token(
            admin_auth=admin_auth,
            target_kind="node",
            target_id=node_id,
            action=payload.action,
            confirmation_token=payload.confirmation_token,
        )
        if confirmation_token is not None:
            return AdminControlActionCreateResponse(
                queued=False,
                confirmation_required=True,
                confirmation_token=confirmation_token,
                action=None,
            )
        action = runtime.store.create_control_action(
            target_kind="node",
            target_id=node_id,
            action=payload.action,
            requested_by=payload.actor,
            confirmation_required=_action_requires_confirmation(payload.action),
            audit_payload={"request": payload.model_dump(exclude_none=True), "target_name": node["node_name"]},
        )
        return AdminControlActionCreateResponse(queued=True, action=action)

    @app.post("/api/v1/admin/panel/actions")
    def admin_panel_action(payload: AdminControlActionRequest, request: Request) -> AdminControlActionCreateResponse:
        require_admin_api(request)
        if payload.action == "start":
            raise HTTPException(status_code=400, detail="Panel start is only available through the host bridge, not the WebUI")
        unavailable_reason = runtime.panel_action_unavailable_reason(payload.action)
        if unavailable_reason is not None:
            raise HTTPException(status_code=409, detail=unavailable_reason)
        conflict = runtime.store.get_active_control_action("panel", None)
        if conflict is not None:
            raise HTTPException(
                status_code=409,
                detail=_control_action_conflict_detail(target_name="panel", conflict=conflict),
            )
        confirmation_token = _validate_or_issue_confirmation_token(
            admin_auth=admin_auth,
            target_kind="panel",
            target_id=None,
            action=payload.action,
            confirmation_token=payload.confirmation_token,
        )
        if confirmation_token is not None:
            return AdminControlActionCreateResponse(
                queued=False,
                confirmation_required=True,
                confirmation_token=confirmation_token,
                action=None,
            )
        action = runtime.store.create_control_action(
            target_kind="panel",
            target_id=None,
            action=payload.action,
            requested_by=payload.actor,
            confirmation_required=_action_requires_confirmation(payload.action),
            audit_payload={"request": payload.model_dump(exclude_none=True), "target_name": "panel"},
        )
        return AdminControlActionCreateResponse(queued=True, action=action)

    @app.post("/api/v1/agents/pair")
    def pair_agent(payload: AgentPairRequest, request: Request) -> AgentPairResponse:
        if payload.identity.protocol_version != SUPPORTED_AGENT_PROTOCOL_VERSION:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Unsupported protocol_version {payload.identity.protocol_version}; "
                    f"expected {SUPPORTED_AGENT_PROTOCOL_VERSION}"
                ),
            )
        node, node_token = runtime.store.pair_agent(
            identity=payload.identity,
            pair_code=payload.pair_code,
            endpoint=payload.endpoint,
            capabilities=payload.capabilities,
        )
        return AgentPairResponse(
            node_id=int(node["id"]),
            topology_id=int(node["topology_id"]),
            node_token=node_token,
            panel_url=str(request.base_url).rstrip("/"),
            identity=AgentIdentity.model_validate(node.get("identity") or payload.identity.model_dump()),
            endpoint=payload.endpoint,
            capabilities=payload.capabilities,
        )

    @app.post("/api/v1/agents/heartbeat")
    def agent_heartbeat(payload: AgentHeartbeatRequest, x_node_token: str | None = Header(default=None)) -> AgentHeartbeatResponse:
        if not x_node_token:
            raise HTTPException(status_code=401, detail="Missing node token")
        try:
            node = runtime.store.resolve_node_from_token(x_node_token)
        except ValueError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

        for completed in payload.completed_jobs:
            if completed.job_id is None:
                continue
            accepted = runtime.store.complete_job(job_id=completed.job_id, node_id=int(node["id"]), result=completed.result)
            job_snapshot = runtime.store.get_job_snapshot(completed.job_id)
            result_metadata = completed.result.get("metadata") if isinstance(completed.result, dict) else {}
            run_id = completed.run_id or (job_snapshot.get("run_id") if isinstance(job_snapshot, dict) else None)
            if run_id:
                runtime.store.record_run_event(
                    str(run_id),
                    "queue_completed" if accepted else "queue_completion_ignored",
                    (
                        f"{completed.task or (job_snapshot or {}).get('task') or 'queued task'} completed on {node['node_name']}"
                        if accepted
                        else f"{completed.task or (job_snapshot or {}).get('task') or 'queued task'} completion ignored on {node['node_name']}"
                    ),
                    {
                        "job_id": completed.job_id,
                        "task": completed.task or (job_snapshot or {}).get("task"),
                        "node_name": node["node_name"],
                        "path_label": (result_metadata or {}).get("path_label"),
                        "queue_status": "completed" if accepted else "completion_ignored",
                        "job": job_snapshot,
                        "success": completed.result.get("success") if isinstance(completed.result, dict) else None,
                        "error": completed.result.get("error") if isinstance(completed.result, dict) else None,
                        "error_code": (result_metadata or {}).get("error_code"),
                    },
                )

        runtime.store.record_heartbeat(
            node_id=int(node["id"]),
            endpoint=payload.endpoint,
            runtime_status=payload.runtime_status,
        )
        leased_rows = runtime.store.lease_jobs(node_id=int(node["id"]))
        for job in leased_rows:
            try:
                runtime.store.record_run_event(
                    str(job["run_id"]),
                    "queue_leased",
                    f"{job['job_kind']} leased to {node['node_name']}",
                    {
                        "job_id": int(job["id"]),
                        "task": str(job["job_kind"]),
                        "node_name": node["node_name"],
                        "path_label": None,
                        "timeout_sec": float(job["timeout_sec"]) if job.get("timeout_sec") is not None else None,
                        "queue_status": "leased",
                        "job": runtime.store.get_job_snapshot(int(job["id"])),
                    },
                )
            except Exception:
                continue
        jobs = [
            AgentTaskDispatch(
                job_id=int(job["id"]),
                run_id=str(job["run_id"]),
                task=str(job["job_kind"]),
                payload=json.loads(job["payload_json"]),
                created_at=str(job["created_at"]),
                lease_expires_at=job.get("lease_expires_at"),
                timeout_sec=float(job["timeout_sec"]) if job.get("timeout_sec") is not None else None,
            )
            for job in leased_rows
        ]
        return AgentHeartbeatResponse(ok=True, jobs=jobs)

    @app.post("/api/v1/runs")
    def start_manual_run(payload: ManualRunRequest, request: Request) -> JSONResponse:
        require_admin_api(request)
        active_run = runtime.store.get_active_run()
        if active_run is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "A monitoring run is already in progress",
                    "active_run": active_run,
                    "suggested_action": _suggested_action(
                        kind="open_run",
                        target_kind="run",
                        run_id=str(active_run.get("run_id") or ""),
                        label="View run",
                    ),
                    "recommended_step": "Open the current run detail to follow progress before starting another monitoring run.",
                },
            )
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
    control_port = 9871
    if runtime_mode == "docker-linux":
        command = (
            f"PANEL_URL='{quoted_panel}' PAIR_CODE='{pair_code}' NODE_NAME='{node_name}' ROLE='{role}' "
            "RUNTIME_MODE='docker-linux' AGENT_PORT='9870' CONTROL_PORT='9871' "
            "docker compose -f docker/relay-agent.compose.yml up -d --build"
        )
        fallback = (
            f"python3 -m agents.service --config config/agent/{role}.yaml --panel-url '{quoted_panel}' "
            f"--pair-code '{pair_code}' --node-name '{node_name}' --role '{role}' --runtime-mode 'docker-linux' "
            f"--listen-host 0.0.0.0 --listen-port 9870 --control-port {control_port}"
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
            f"--runtime-mode native-macos --listen-port 9870 --control-port {control_port}"
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
        f"--runtime-mode native-windows --listen-host 0.0.0.0 --listen-port 9870 --control-port {control_port}\""
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
        try:
            return max(1, int(value[:-1]))
        except ValueError:
            return 24
    if value.endswith("d"):
        try:
            return max(24, int(value[:-1]) * 24)
        except ValueError:
            return 24
    try:
        return max(1, int(value))
    except ValueError:
        return 24


def _parse_csv_list(value: str | None) -> list[str] | None:
    if not value:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    return items or None


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return None


def _action_requires_confirmation(action: str) -> bool:
    return action in {"stop", "restart", "pause_scheduler", "resume_scheduler"}


def _node_action_unavailable_reason(node: dict[str, Any], action: str) -> str | None:
    available_actions = set(node.get("runtime", {}).get("details", {}).get("available_actions") or [])
    if action in available_actions:
        return None
    readonly_reason = node.get("runtime", {}).get("details", {}).get("readonly_reason")
    return str(readonly_reason or f"Node does not support action {action}")


def _control_action_conflict_detail(target_name: str, conflict: dict[str, Any]) -> dict[str, Any]:
    suggested_action = _suggested_action(
        kind="open_action",
        target_kind="action",
        action_id=int(conflict["id"]),
        label="View action",
    )
    return {
        "message": (
            f"{target_name} already has an active action: "
            f"{conflict.get('action')} ({conflict.get('status')})"
        ),
        "suggested_action": suggested_action,
        "recommended_step": "Open the action detail to follow progress before issuing another lifecycle action for this target.",
        "active_action": {
            "id": conflict.get("id"),
            "action": conflict.get("action"),
            "status": conflict.get("status"),
            "requested_at": conflict.get("requested_at"),
            "target_name": conflict.get("target_name"),
            "result_summary": conflict.get("result_summary"),
            "suggested_action": suggested_action,
        },
    }


def _validate_or_issue_confirmation_token(
    admin_auth: AdminAuth,
    target_kind: str,
    target_id: int | None,
    action: str,
    confirmation_token: str | None,
) -> str | None:
    if not _action_requires_confirmation(action):
        return None
    payload = json.dumps(
        {
            "target_kind": target_kind,
            "target_id": target_id,
            "action": action,
            "expires_at": int(time.time()) + 300,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    signature = hmac.new(admin_auth.secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    issued_token = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=") + "." + signature
    if confirmation_token is None:
        return issued_token
    if "." not in confirmation_token:
        raise HTTPException(status_code=400, detail="Invalid confirmation token")
    encoded, provided_signature = confirmation_token.rsplit(".", 1)
    padded = encoded + ("=" * (-len(encoded) % 4))
    try:
        raw_payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid confirmation token") from exc
    expected_signature = hmac.new(admin_auth.secret.encode("utf-8"), raw_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise HTTPException(status_code=400, detail="Invalid confirmation token")
    try:
        decoded = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid confirmation token") from exc
    if int(decoded.get("expires_at") or 0) < int(time.time()):
        raise HTTPException(status_code=400, detail="Confirmation token has expired")
    if decoded.get("target_kind") != target_kind or decoded.get("target_id") != target_id or decoded.get("action") != action:
        raise HTTPException(status_code=400, detail="Confirmation token does not match the requested action")
    return None


def _panel_internal_bridge_response(runtime_payload: dict[str, Any], summary: str) -> BridgeActionResponse:
    return BridgeActionResponse(
        accepted=True,
        state=str(runtime_payload.get("runtime", {}).get("state") or "running"),
        human_summary=summary,
        runtime=runtime_payload.get("runtime", {}),
        supervisor=runtime_payload.get("supervisor", {}),
        raw_runtime=runtime_payload,
        log_location=runtime_payload.get("supervisor", {}).get("log_location"),
    )


def _tail_local_file(path: str | Path, line_count: int) -> list[str]:
    target = Path(path)
    if line_count <= 0:
        return []
    try:
        lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError as exc:
        raise ControlBridgeError("missing_panel_log", f"Log file not found: {target}") from exc
    return lines[-line_count:]


def main() -> int:
    """Run the monitoring panel."""
    args = build_parser().parse_args()
    app = create_app(db_path=args.db_path, start_background=True)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


app = create_app()


if __name__ == "__main__":
    raise SystemExit(main())
