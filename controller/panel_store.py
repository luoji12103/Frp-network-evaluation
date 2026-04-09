"""SQLite-backed persistence for the monitoring panel."""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import secrets
import sqlite3
import statistics
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from controller.panel_models import (
    AgentCapabilities,
    AgentEndpointReport,
    AgentIdentity,
    AgentRuntimeStatus,
    NodeUpsertRequest,
    PanelSettings,
    RuntimeSummary,
    SuggestedAction,
    SupervisorSummary,
)
from probes.common import ProbeResult, RunResult, ThresholdFinding, now_iso


DEFAULT_SCHEDULES = (
    ("system", 30),
    ("baseline", 60),
    ("capacity", 300),
)

DEFAULT_PATH_ORDER = (
    "client_to_relay",
    "relay_to_server",
    "client_to_mc_public",
    "client_to_iperf_public",
    "client_to_mc_public_load",
    "client_system",
    "relay_system",
    "server_system",
    "server_to_local_mc",
    "server_iperf_direct",
    "server_iperf_public",
)

ANOMALY_HIGH_METRICS = {
    "packet_loss_pct",
    "rtt_avg_ms",
    "rtt_p95_ms",
    "jitter_ms",
    "connect_avg_ms",
    "connect_p95_ms",
    "connect_timeout_or_error_pct",
    "load_rtt_inflation_ms",
    "cpu_usage_pct",
    "memory_usage_pct",
}

ANOMALY_LOW_METRICS = {
    "throughput_up_mbps",
    "throughput_down_mbps",
}

PATH_CATEGORY_METRICS = {
    "latency": ("rtt_avg_ms", "connect_avg_ms"),
    "jitter": ("jitter_ms",),
    "loss": ("packet_loss_pct", "connect_timeout_or_error_pct"),
    "throughput": ("throughput_up_mbps", "throughput_down_mbps"),
    "load": ("load_rtt_inflation_ms",),
    "system": ("cpu_usage_pct", "memory_usage_pct"),
}


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


class PanelStore:
    """Own the panel database and all persistence helpers."""

    def __init__(self, db_path: str | Path = "data/monitor.db", secret_path: str | Path = "data/panel-secret.txt") -> None:
        self.db_path = Path(db_path)
        self.secret_path = Path(secret_path)
        self._lock = threading.Lock()
        self._panel_secret = self._load_or_create_panel_secret()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def get_settings(self) -> PanelSettings:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM topology ORDER BY id LIMIT 1").fetchone()
        if row is None:
            settings = PanelSettings()
            self.update_settings(settings)
            return settings
        return PanelSettings(
            topology_name=row["name"],
            services=_loads(row["services_json"]),
            thresholds=_loads(row["thresholds_json"]),
            scenarios=_loads(row["scenarios_json"]),
        )

    def update_settings(self, settings: PanelSettings) -> dict[str, Any]:
        payload = settings.model_dump()
        updated_at = now_iso()
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT id FROM topology ORDER BY id LIMIT 1").fetchone()
            if row is None:
                conn.execute(
                    """
                    INSERT INTO topology (name, services_json, thresholds_json, scenarios_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        settings.topology_name,
                        _dumps(payload["services"]),
                        _dumps(payload["thresholds"]),
                        _dumps(payload["scenarios"]),
                        updated_at,
                        updated_at,
                    ),
                )
                topology_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            else:
                topology_id = int(row["id"])
                conn.execute(
                    """
                    UPDATE topology
                    SET name = ?, services_json = ?, thresholds_json = ?, scenarios_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        settings.topology_name,
                        _dumps(payload["services"]),
                        _dumps(payload["thresholds"]),
                        _dumps(payload["scenarios"]),
                        updated_at,
                        topology_id,
                    ),
                )
            conn.commit()
        return {"topology_id": topology_id, **payload}

    def get_topology_id(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM topology ORDER BY id LIMIT 1").fetchone()
        if row is None:
            return int(self.update_settings(PanelSettings())["topology_id"])
        return int(row["id"])

    def list_nodes(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT n.*, ns.pair_code_expires_at, ns.token_issued_at
                FROM node n
                LEFT JOIN node_secret ns ON ns.node_id = n.id
                ORDER BY CASE n.role WHEN 'client' THEN 1 WHEN 'relay' THEN 2 ELSE 3 END, n.id
                """
            ).fetchall()
        active_actions = self._active_control_action_map()
        return [self._decorate_node(dict(row), active_actions=active_actions) for row in rows]

    def get_node(self, node_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, ns.pair_code_expires_at, ns.token_issued_at
                FROM node n
                LEFT JOIN node_secret ns ON ns.node_id = n.id
                WHERE n.id = ?
                """,
                (node_id,),
            ).fetchone()
        if row is None:
            return None
        return self._decorate_node(dict(row), active_actions=self._active_control_action_map(target_kind="node", target_id=node_id))

    def get_node_by_name(self, node_name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, ns.pair_code_expires_at, ns.token_issued_at
                FROM node n
                LEFT JOIN node_secret ns ON ns.node_id = n.id
                WHERE n.node_name = ?
                """,
                (node_name,),
            ).fetchone()
        if row is None:
            return None
        return self._decorate_node(dict(row), active_actions=self._active_control_action_map(target_kind="node", target_id=int(row["id"])))

    def get_node_by_role(self, role: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, ns.pair_code_expires_at, ns.token_issued_at
                FROM node n
                LEFT JOIN node_secret ns ON ns.node_id = n.id
                WHERE n.role = ?
                ORDER BY n.id
                LIMIT 1
                """,
                (role,),
            ).fetchone()
        if row is None:
            return None
        return self._decorate_node(dict(row), active_actions=self._active_control_action_map(target_kind="node", target_id=int(row["id"])))

    def get_active_control_action(self, target_kind: str, target_id: int | None) -> dict[str, Any] | None:
        actions = self._active_control_action_map(target_kind=target_kind, target_id=target_id)
        return actions.get((target_kind, target_id))

    def upsert_node(self, payload: NodeUpsertRequest) -> dict[str, Any]:
        now = now_iso()
        topology_id = self.get_topology_id()
        node_id = payload.id
        with self._lock, self._connect() as conn:
            if node_id is None:
                existing = conn.execute("SELECT id FROM node WHERE role = ?", (payload.role,)).fetchone()
                if existing is not None:
                    node_id = int(existing["id"])

            if node_id is None:
                conn.execute(
                    """
                    INSERT INTO node (
                        topology_id, node_name, role, runtime_mode, configured_pull_url, enabled,
                        paired, created_at, updated_at, last_status, push_state, pull_state
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 'unpaired', 'unknown', 'unknown')
                    """,
                    (
                        topology_id,
                        payload.node_name,
                        payload.role,
                        payload.runtime_mode,
                        payload.configured_pull_url,
                        1 if payload.enabled else 0,
                        now,
                        now,
                    ),
                )
                node_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                conn.execute("INSERT OR IGNORE INTO node_secret (node_id) VALUES (?)", (node_id,))
            else:
                conn.execute(
                    """
                    UPDATE node
                    SET node_name = ?, role = ?, runtime_mode = ?, configured_pull_url = ?, enabled = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload.node_name,
                        payload.role,
                        payload.runtime_mode,
                        payload.configured_pull_url,
                        1 if payload.enabled else 0,
                        now,
                        node_id,
                    ),
                )
                conn.execute("INSERT OR IGNORE INTO node_secret (node_id) VALUES (?)", (node_id,))
            conn.commit()
        node = self.get_node(int(node_id))
        if node is None:
            raise KeyError(node_id)
        return node

    def list_schedules(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM schedule ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def update_schedule_intervals(self, settings: PanelSettings) -> None:
        mapping = {
            "system": 30,
            "baseline": 60,
            "capacity": 300,
        }
        with self._lock, self._connect() as conn:
            for run_kind, interval_sec in mapping.items():
                conn.execute(
                    "UPDATE schedule SET interval_sec = ?, updated_at = ? WHERE run_kind = ?",
                    (interval_sec, now_iso(), run_kind),
                )
            conn.commit()

    def due_schedules(self) -> list[dict[str, Any]]:
        current = now_iso()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schedule WHERE enabled = 1 AND next_run_at <= ? ORDER BY next_run_at, id",
                (current,),
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_schedule_dispatched(self, schedule_id: int, interval_sec: int) -> None:
        next_run = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + interval_sec))
        next_run_at = f"{next_run}+00:00"
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE schedule SET next_run_at = ?, updated_at = ? WHERE id = ?",
                (next_run_at, now_iso(), schedule_id),
            )
            conn.commit()

    def create_pair_code(self, node_id: int, expires_in_sec: int = 1800) -> tuple[str, str]:
        pair_code = secrets.token_urlsafe(18)
        expires_at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + expires_in_sec)) + "+00:00"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO node_secret (node_id, pair_code_hash, pair_code_expires_at)
                VALUES (?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    pair_code_hash = excluded.pair_code_hash,
                    pair_code_expires_at = excluded.pair_code_expires_at
                """,
                (node_id, _hash_token(pair_code), expires_at),
            )
            conn.commit()
        return pair_code, expires_at

    def pair_agent(
        self,
        identity: AgentIdentity,
        pair_code: str,
        endpoint: AgentEndpointReport,
        capabilities: AgentCapabilities,
    ) -> tuple[dict[str, Any], str]:
        node = self.get_node_by_name(identity.node_name)
        if node is None:
            raise ValueError(f"Unknown node: {identity.node_name}")
        if node["role"] != identity.role:
            raise ValueError("Role does not match the paired node")
        if node["runtime_mode"] != identity.runtime_mode:
            raise ValueError("Runtime mode does not match the paired node")

        with self._connect() as conn:
            secret_row = conn.execute("SELECT * FROM node_secret WHERE node_id = ?", (node["id"],)).fetchone()
        if secret_row is None or not secret_row["pair_code_hash"]:
            raise ValueError("Pair code has not been generated for this node")
        if secret_row["pair_code_expires_at"] and _parse_iso_timestamp(str(secret_row["pair_code_expires_at"])) < _parse_iso_timestamp(now_iso()):
            raise ValueError("Pair code has expired")
        if not hmac.compare_digest(str(secret_row["pair_code_hash"]), _hash_token(pair_code)):
            raise ValueError("Pair code is invalid")

        token_salt = secrets.token_hex(12)
        node_token = self._derive_node_token(node["id"], token_salt)
        current = now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE node_secret
                SET pair_code_hash = NULL,
                    pair_code_expires_at = NULL,
                    token_hash = ?,
                    token_salt = ?,
                    token_issued_at = ?
                WHERE node_id = ?
                """,
                (_hash_token(node_token), token_salt, current, node["id"]),
            )
            conn.execute(
                """
                UPDATE node
                SET paired = 1,
                    last_seen_at = ?,
                    advertised_pull_url = ?,
                    endpoint_report_json = ?,
                    identity_json = ?,
                    capabilities_json = ?,
                    push_state = 'ok',
                    push_checked_at = ?,
                    push_error = NULL,
                    last_status = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    current,
                    endpoint.advertise_url,
                    _dumps(endpoint.model_dump()),
                    _dumps(identity.model_dump()),
                    _dumps(capabilities.model_dump()),
                    current,
                    current,
                    node["id"],
                ),
            )
            conn.commit()
        paired = self.refresh_node_status(node["id"])
        if paired is None:
            raise KeyError(node["id"])
        return paired, node_token

    def resolve_node_from_token(self, token: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, ns.token_hash, ns.token_salt
                FROM node n
                JOIN node_secret ns ON ns.node_id = n.id
                WHERE ns.token_hash = ?
                """,
                (_hash_token(token),),
            ).fetchone()
        if row is None or not row["token_hash"]:
            raise ValueError("Node is not paired")
        return self._decorate_node(dict(row))

    def build_node_token(self, node_id: int) -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT token_salt FROM node_secret WHERE node_id = ?", (node_id,)).fetchone()
        if row is None or not row["token_salt"]:
            raise ValueError("Node token has not been issued")
        return self._derive_node_token(node_id, str(row["token_salt"]))

    def record_heartbeat(
        self,
        node_id: int,
        endpoint: AgentEndpointReport,
        runtime_status: AgentRuntimeStatus,
    ) -> dict[str, Any]:
        current = now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE node
                SET advertised_pull_url = ?,
                    endpoint_report_json = ?,
                    runtime_status_json = ?,
                    last_seen_at = ?,
                    last_heartbeat_at = ?,
                    push_state = 'ok',
                    push_checked_at = ?,
                    push_error_code = NULL,
                    push_error = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    endpoint.advertise_url,
                    _dumps(endpoint.model_dump()),
                    _dumps(runtime_status.model_dump()),
                    current,
                    current,
                    current,
                    current,
                    node_id,
                ),
            )
            conn.commit()
        return self.refresh_node_status(node_id)

    def mark_push_error(self, node_id: int, error: str, error_code: str | None = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE node
                SET push_state = 'error',
                    push_checked_at = ?,
                    push_error_code = ?,
                    push_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (now_iso(), error_code, error, now_iso(), node_id),
            )
            conn.commit()
        self.refresh_node_status(node_id)

    def update_pull_status(
        self,
        node_id: int,
        ok: bool,
        error: str | None = None,
        error_code: str | None = None,
    ) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE node
                SET pull_state = ?, pull_error_code = ?, pull_error = ?, pull_checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                ("ok" if ok else "error", None if ok else error_code, None if ok else error, now_iso(), now_iso(), node_id),
            )
            conn.commit()
        return self.refresh_node_status(node_id)

    def reset_pull_status(self, node_id: int) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE node
                SET pull_state = 'unknown',
                    pull_error_code = NULL,
                    pull_error = NULL,
                    pull_checked_at = NULL,
                    updated_at = ?
                WHERE id = ?
                """,
                (now_iso(), node_id),
            )
            conn.commit()
        return self.refresh_node_status(node_id)

    def mark_stale_nodes(self, stale_after_sec: int = 45) -> None:
        cutoff = time.time() - stale_after_sec
        cutoff_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(cutoff)) + "+00:00"
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT id, last_seen_at FROM node WHERE paired = 1").fetchall()
            for row in rows:
                if row["last_seen_at"] and _parse_iso_timestamp(str(row["last_seen_at"])) < _parse_iso_timestamp(cutoff_iso):
                    conn.execute(
                        """
                        UPDATE node
                        SET push_state = 'error',
                            push_checked_at = ?,
                            push_error_code = ?,
                            push_error = ?,
                            updated_at = ?
                        WHERE id = ?
                        """,
                        (now_iso(), "heartbeat_timeout", "Heartbeat timeout", now_iso(), row["id"]),
                    )
            conn.commit()
        for node in self.list_nodes():
            if node["paired"]:
                self.refresh_node_status(node["id"])

    def refresh_node_status(self, node_id: int) -> dict[str, Any]:
        node = self.get_node(node_id)
        if node is None:
            raise KeyError(node_id)
        next_status = self._classify_node(node)
        previous_status = node.get("last_status")
        if previous_status != next_status:
            self.insert_alert(
                kind="node_status",
                severity="warning" if next_status != "online" else "info",
                status="open" if next_status != "online" else "resolved",
                message=f"{node['node_name']} changed status from {previous_status or 'unknown'} to {next_status}",
                node_id=node_id,
            )
        with self._lock, self._connect() as conn:
            conn.execute("UPDATE node SET last_status = ?, updated_at = ? WHERE id = ?", (next_status, now_iso(), node_id))
            conn.commit()
        refreshed = self.get_node(node_id)
        if refreshed is None:
            raise KeyError(node_id)
        return refreshed

    def update_node_runtime_summaries(
        self,
        node_id: int,
        runtime_summary: RuntimeSummary | dict[str, Any],
        supervisor_summary: SupervisorSummary | dict[str, Any],
    ) -> dict[str, Any]:
        runtime_payload = RuntimeSummary.model_validate(runtime_summary).model_dump()
        supervisor_payload = SupervisorSummary.model_validate(supervisor_summary).model_dump()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE node
                SET runtime_summary_json = ?,
                    supervisor_summary_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (_dumps(runtime_payload), _dumps(supervisor_payload), now_iso(), node_id),
            )
            conn.commit()
        node = self.get_node(node_id)
        if node is None:
            raise KeyError(node_id)
        return node

    def create_control_action(
        self,
        target_kind: str,
        target_id: int | None,
        action: str,
        requested_by: str,
        confirmation_required: bool,
        audit_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        requested_at = now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO control_action (
                    target_kind, target_id, action, status, confirmation_required,
                    requested_by, requested_at, audit_payload_json
                )
                VALUES (?, ?, ?, 'queued', ?, ?, ?, ?)
                """,
                (
                    target_kind,
                    target_id,
                    action,
                    1 if confirmation_required else 0,
                    requested_by,
                    requested_at,
                    _dumps(audit_payload or {}),
                ),
            )
            action_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.commit()
        created = self.get_control_action(action_id)
        if created is None:
            raise KeyError(action_id)
        return created

    def list_control_actions(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM control_action ORDER BY requested_at DESC, id DESC LIMIT ?", (limit,)).fetchall()
        return [self._decorate_control_action(dict(row), include_detail=False) for row in rows]

    def list_pending_control_actions(self, limit: int = 10) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM control_action
                WHERE status = 'queued'
                ORDER BY requested_at, id
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._decorate_control_action(dict(row), include_detail=True) for row in rows]

    def get_control_action(self, action_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM control_action WHERE id = ?", (action_id,)).fetchone()
        return self._decorate_control_action(dict(row), include_detail=True) if row is not None else None

    def start_control_action(self, action_id: int, transport: str) -> dict[str, Any]:
        started_at = now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE control_action
                SET status = 'running', started_at = ?, transport = ?
                WHERE id = ? AND status = 'queued'
                """,
                (started_at, transport, action_id),
            )
            conn.commit()
        action = self.get_control_action(action_id)
        if action is None:
            raise KeyError(action_id)
        return action

    def finish_control_action(
        self,
        action_id: int,
        status: str,
        result_summary: str | None = None,
        error_code: str | None = None,
        error_detail: str | None = None,
        transport: str | None = None,
        audit_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        finished_at = now_iso()
        with self._lock, self._connect() as conn:
            existing = conn.execute("SELECT audit_payload_json FROM control_action WHERE id = ?", (action_id,)).fetchone()
            merged_payload = _loads(existing["audit_payload_json"]) if existing is not None else {}
            if audit_payload:
                merged_payload.update(audit_payload)
            conn.execute(
                """
                UPDATE control_action
                SET status = ?,
                    finished_at = ?,
                    result_summary = ?,
                    error_code = ?,
                    error_detail = ?,
                    transport = COALESCE(?, transport),
                    audit_payload_json = ?
                WHERE id = ?
                """,
                (
                    status,
                    finished_at,
                    result_summary,
                    error_code,
                    error_detail,
                    transport,
                    _dumps(merged_payload),
                    action_id,
                ),
            )
            conn.commit()
        action = self.get_control_action(action_id)
        if action is None:
            raise KeyError(action_id)
        return action

    def record_run_event(self, run_id: str, event_kind: str, message: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        created_at = now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_event (run_id, event_kind, message, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, event_kind, message, _dumps(payload or {}), created_at),
            )
            event_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.commit()
        event = self.get_run_event(event_id)
        if event is None:
            raise KeyError(event_id)
        return event

    def list_run_events(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM run_event
                WHERE run_id = ?
                ORDER BY created_at ASC, id ASC
                LIMIT ?
                """,
                (run_id, limit),
            ).fetchall()
        return [self._decorate_run_event(dict(row)) for row in rows]

    def get_run_event(self, event_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM run_event WHERE id = ?", (event_id,)).fetchone()
        return self._decorate_run_event(dict(row)) if row is not None else None

    def enqueue_job(self, node_id: int, run_id: str, task: str, payload: dict[str, Any], timeout_sec: float | None = None) -> int:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job (
                    topology_id, node_id, run_id, job_kind, payload_json, status,
                    created_at, available_at, timeout_sec
                )
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    self.get_topology_id(),
                    node_id,
                    run_id,
                    task,
                    _dumps(payload),
                    now_iso(),
                    now_iso(),
                    float(timeout_sec) if timeout_sec is not None else None,
                ),
            )
            job_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.commit()
        return job_id

    def lease_jobs(self, node_id: int, limit: int = 5) -> list[dict[str, Any]]:
        leased_at = now_iso()
        leased_rows: list[dict[str, Any]] = []
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM job
                WHERE node_id = ?
                  AND (
                    status = 'pending'
                    OR (status = 'leased' AND COALESCE(lease_expires_at, '') < ?)
                  )
                ORDER BY id
                LIMIT ?
                """,
                (node_id, leased_at, limit),
            ).fetchall()
            job_updates = []
            for row in rows:
                timeout_sec = float(row["timeout_sec"] or 0.0)
                lease_window = max(timeout_sec, 45.0)
                lease_expires_at = datetime.fromtimestamp(time.time() + lease_window, tz=timezone.utc).isoformat()
                job_updates.append((leased_at, lease_expires_at, int(row["id"])))
                job_payload = dict(row)
                job_payload["leased_at"] = leased_at
                job_payload["lease_expires_at"] = lease_expires_at
                leased_rows.append(job_payload)
            if job_updates:
                conn.executemany(
                    "UPDATE job SET status = 'leased', leased_at = ?, lease_expires_at = ? WHERE id = ?",
                    job_updates,
                )
                conn.commit()
        return leased_rows

    def complete_job(self, job_id: int, node_id: int, result: dict[str, Any]) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT node_id, status FROM job WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                return False
            if int(row["node_id"]) != int(node_id):
                return False
            if str(row["status"]) in {"completed", "failed"}:
                return False
            conn.execute(
                """
                UPDATE job
                SET status = 'completed',
                    result_json = ?,
                    completed_at = ?,
                    lease_expires_at = NULL,
                    error = NULL
                WHERE id = ?
                """,
                (_dumps(result), now_iso(), job_id),
            )
            conn.commit()
        return True

    def fail_job(self, job_id: int, error: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE job
                SET status = 'failed',
                    completed_at = ?,
                    lease_expires_at = NULL,
                    error = ?
                WHERE id = ?
                """,
                (now_iso(), error, job_id),
            )
            conn.commit()

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM job WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row is not None else None

    def get_job_snapshot(self, job_id: int) -> dict[str, Any] | None:
        job = self.get_job(job_id)
        if job is None:
            return None
        return self._job_snapshot(job)

    def wait_for_job(self, job_id: int, timeout_sec: float) -> dict[str, Any]:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            job = self.get_job(job_id)
            if job is None:
                raise KeyError(job_id)
            if job["status"] in {"completed", "failed"}:
                return job
            time.sleep(0.2)
        raise TimeoutError(f"Timed out waiting for job {job_id}")

    def create_run(self, run_kind: str, source: str) -> str:
        run_id = f"run-{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{secrets.token_hex(3)}"
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run (id, topology_id, run_kind, status, source, started_at)
                VALUES (?, ?, ?, 'running', ?, ?)
                """,
                (run_id, self.get_topology_id(), run_kind, source, now_iso()),
            )
            conn.commit()
        self.record_run_event(run_id=run_id, event_kind="run_created", message=f"{run_kind} run created", payload={"source": source})
        return run_id

    def has_active_run(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM run WHERE status = 'running' LIMIT 1").fetchone()
        return row is not None

    def get_active_run(self) -> dict[str, Any] | None:
        with self._connect() as conn:
            run_row = conn.execute(
                "SELECT * FROM run WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
            if run_row is None:
                return None
            event_rows = conn.execute(
                "SELECT * FROM run_event WHERE run_id = ? ORDER BY created_at ASC, id ASC",
                (run_row["id"],),
            ).fetchall()
        run = self._decorate_run(dict(run_row))
        run["active"] = True
        run["progress"] = self._summarize_run_events([self._decorate_run_event(dict(row)) for row in event_rows])
        return run

    def finish_run(
        self,
        run_id: str,
        status: str,
        run_result: RunResult | None = None,
        raw_path: str | None = None,
        csv_path: str | None = None,
        html_path: str | None = None,
        error: str | None = None,
    ) -> None:
        finished_at = now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE run
                SET status = ?, finished_at = ?, raw_path = ?, csv_path = ?, html_path = ?,
                    error = ?, findings_count = ?, conclusion_json = ?, threshold_findings_json = ?
                WHERE id = ?
                """,
                (
                    status,
                    finished_at,
                    raw_path,
                    csv_path,
                    html_path,
                    error,
                    len(run_result.threshold_findings) if run_result else 0,
                    _dumps(run_result.conclusion if run_result else []),
                    _dumps([finding.to_dict() for finding in run_result.threshold_findings] if run_result else []),
                    run_id,
                ),
            )
            if run_result is not None:
                conn.execute("DELETE FROM probe_result WHERE run_id = ?", (run_id,))
                conn.execute("DELETE FROM metric_sample WHERE run_id = ?", (run_id,))
                inserted_samples: list[dict[str, Any]] = []
                for probe in run_result.probes:
                    path_label = probe.metadata.get("path_label")
                    row = conn.execute(
                        """
                        INSERT INTO probe_result (
                            run_id, node_id, probe_name, path_label, success, error,
                            metrics_json, metadata_json, samples_json, started_at, duration_ms
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            self._node_id_from_role(probe.metadata.get("source_node")),
                            probe.name,
                            path_label,
                            1 if probe.success else 0,
                            probe.error,
                            _dumps(probe.metrics),
                            _dumps(probe.metadata),
                            _dumps(probe.samples),
                            probe.started_at,
                            probe.duration_ms,
                        ),
                    )
                    probe_result_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                    for metric_name, metric_value in probe.metrics.items():
                        if isinstance(metric_value, (int, float)) and metric_value is not None:
                            conn.execute(
                                """
                                INSERT INTO metric_sample (
                                    node_id, run_id, probe_result_id, probe_name, metric_name, metric_value, path_label, captured_at
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    self._node_id_from_role(probe.metadata.get("source_node")),
                                    run_id,
                                    probe_result_id,
                                    probe.name,
                                    metric_name,
                                    float(metric_value),
                                    path_label,
                                    finished_at,
                                ),
                            )
                            sample_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
                            inserted_samples.append(
                                {
                                    "id": sample_id,
                                    "node_id": self._node_id_from_role(probe.metadata.get("source_node")),
                                    "run_id": run_id,
                                    "probe_name": probe.name,
                                    "metric_name": metric_name,
                                    "metric_value": float(metric_value),
                                    "path_label": path_label,
                                    "captured_at": finished_at,
                                }
                            )
                for finding in run_result.threshold_findings:
                    fingerprint = self._alert_fingerprint(
                        kind="threshold",
                        path_label=finding.path_label,
                        probe_name=finding.probe_name,
                        metric_name=finding.metric,
                    )
                    if self._is_fingerprint_silenced(conn, fingerprint=fingerprint, current_time=finished_at):
                        continue
                    self._insert_alert_row(
                        conn=conn,
                        kind="threshold",
                        severity=finding.severity,
                        status="open",
                        message=f"{finding.path_label} {finding.metric} actual={finding.actual} threshold={finding.threshold}",
                        created_at=finished_at,
                        node_id=self._node_id_from_path(finding.path_label),
                        run_id=run_id,
                        path_label=finding.path_label,
                        probe_name=finding.probe_name,
                        metric_name=finding.metric,
                        actual_value=float(finding.actual),
                        threshold_value=float(finding.threshold),
                        fingerprint=fingerprint,
                    )
                self._detect_metric_anomalies(conn=conn, inserted_samples=inserted_samples)
            conn.commit()
        self.record_run_event(
            run_id=run_id,
            event_kind="run_finished" if status == "completed" else "run_failed",
            message=f"Run finished with status {status}",
            payload={"status": status, "error": error, "findings_count": len(run_result.threshold_findings) if run_result else 0},
        )

    def list_recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM run ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decorate_run(dict(row)) for row in rows]

    def list_recent_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM alert_event ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decorate_alert(dict(row)) for row in rows]

    def insert_alert(
        self,
        kind: str,
        severity: str,
        status: str,
        message: str,
        node_id: int | None = None,
        run_id: str | None = None,
        path_label: str | None = None,
        probe_name: str | None = None,
        metric_name: str | None = None,
        actual_value: float | None = None,
        threshold_value: float | None = None,
        fingerprint: str | None = None,
        acknowledged_at: str | None = None,
        acknowledged_by: str | None = None,
        silenced_until: str | None = None,
        silence_reason: str | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            self._insert_alert_row(
                conn=conn,
                kind=kind,
                severity=severity,
                status=status,
                message=message,
                created_at=now_iso(),
                node_id=node_id,
                run_id=run_id,
                path_label=path_label,
                probe_name=probe_name,
                metric_name=metric_name,
                actual_value=actual_value,
                threshold_value=threshold_value,
                fingerprint=fingerprint,
                acknowledged_at=acknowledged_at,
                acknowledged_by=acknowledged_by,
                silenced_until=silenced_until,
                silence_reason=silence_reason,
            )
            conn.commit()

    def list_filter_options(self) -> dict[str, Any]:
        with self._connect() as conn:
            node_rows = conn.execute(
                "SELECT role, node_name FROM node ORDER BY CASE role WHEN 'client' THEN 1 WHEN 'relay' THEN 2 ELSE 3 END, node_name"
            ).fetchall()
            path_rows = conn.execute(
                """
                SELECT DISTINCT COALESCE(ms.path_label, pr.path_label) AS path_label
                FROM metric_sample ms
                LEFT JOIN probe_result pr ON pr.id = ms.probe_result_id
                WHERE COALESCE(ms.path_label, pr.path_label) IS NOT NULL
                ORDER BY path_label
                """
            ).fetchall()
            probe_rows = conn.execute("SELECT DISTINCT probe_name FROM probe_result ORDER BY probe_name").fetchall()
            metric_rows = conn.execute("SELECT DISTINCT metric_name FROM metric_sample ORDER BY metric_name").fetchall()
            run_kind_rows = conn.execute("SELECT DISTINCT run_kind FROM run ORDER BY run_kind").fetchall()
            severity_rows = conn.execute("SELECT DISTINCT severity FROM alert_event ORDER BY severity").fetchall()
            status_rows = conn.execute("SELECT DISTINCT status FROM alert_event ORDER BY status").fetchall()

        paths = [row["path_label"] for row in path_rows if row["path_label"]]
        ordered_paths = [path for path in DEFAULT_PATH_ORDER if path in paths]
        ordered_paths.extend(path for path in paths if path not in ordered_paths)
        return {
            "roles": ["client", "relay", "server"],
            "nodes": [{"role": row["role"], "node_name": row["node_name"]} for row in node_rows],
            "paths": ordered_paths,
            "probes": [row["probe_name"] for row in probe_rows if row["probe_name"]],
            "metrics": [row["metric_name"] for row in metric_rows if row["metric_name"]],
            "run_kinds": [row["run_kind"] for row in run_kind_rows if row["run_kind"]],
            "severities": [row["severity"] for row in severity_rows if row["severity"]],
            "statuses": [row["status"] for row in status_rows if row["status"]],
            "time_ranges": ["1h", "6h", "24h", "7d", "30d"],
        }

    def build_admin_overview(
        self,
        time_range_hours: int,
        roles: list[str] | None = None,
        nodes: list[str] | None = None,
        path_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        all_nodes = self.list_nodes()
        filtered_nodes = [
            node
            for node in all_nodes
            if (not roles or node["role"] in roles) and (not nodes or node["node_name"] in nodes)
        ]
        alerts_payload = self.query_alert_events(
            time_range_hours=time_range_hours,
            severities=None,
            statuses=["open", "acknowledged", "resolved"],
            kinds=None,
            path_labels=path_labels,
            metric_names=None,
            acknowledged=None,
            anomaly_only=False,
            limit=20,
        )
        anomalies_payload = self.query_alert_events(
            time_range_hours=time_range_hours,
            severities=None,
            statuses=["open", "acknowledged"],
            kinds=["anomaly"],
            path_labels=path_labels,
            metric_names=None,
            acknowledged=None,
            anomaly_only=True,
            limit=12,
        )
        path_summaries = self._build_path_summaries(
            time_range_hours=time_range_hours,
            roles=roles,
            nodes=nodes,
            path_labels=path_labels,
        )
        latest_full = next((run for run in self.list_recent_runs(limit=20) if run["run_kind"] == "full"), None)
        online_nodes = sum(1 for node in filtered_nodes if node["status"] == "online")
        degraded_nodes = sum(1 for node in filtered_nodes if node["status"] in {"push-only", "pull-only"})
        offline_nodes = sum(1 for node in filtered_nodes if node["status"] in {"offline", "unpaired", "disabled"})
        total_nodes = len(filtered_nodes)
        active_alerts = sum(1 for item in alerts_payload["items"] if item["status"] in {"open", "acknowledged"} and not item["is_silenced"])
        health_score = max(0, 100 - (offline_nodes * 30) - (degraded_nodes * 12) - (active_alerts * 4))
        return {
            "kpis": {
                "total_nodes": total_nodes,
                "online_rate_pct": round((online_nodes / total_nodes) * 100.0, 1) if total_nodes else 0.0,
                "degraded_nodes": degraded_nodes,
                "offline_nodes": offline_nodes,
                "active_alerts": active_alerts,
                "health_score": health_score,
                "last_full_run_started_at": latest_full.get("started_at") if latest_full else None,
                "last_full_run_status": latest_full.get("status") if latest_full else None,
            },
            "status_distribution": {
                "online": online_nodes,
                "degraded": degraded_nodes,
                "offline": offline_nodes,
            },
            "recent_anomalies": anomalies_payload["items"],
            "path_health": path_summaries,
            "trend_groups": self._build_trend_groups(time_range_hours=time_range_hours, public_mode=False),
            "alert_summary": alerts_payload["summary"],
        }

    def query_metric_series(
        self,
        time_range_hours: int,
        roles: list[str] | None = None,
        nodes: list[str] | None = None,
        path_labels: list[str] | None = None,
        probe_names: list[str] | None = None,
        metric_name: str | None = None,
        bucket: str = "auto",
        limit: int = 2000,
    ) -> dict[str, Any]:
        rows = self._select_metric_rows(
            time_range_hours=time_range_hours,
            roles=roles,
            nodes=nodes,
            path_labels=path_labels,
            probe_names=probe_names,
            metric_names=[metric_name] if metric_name else None,
            limit=limit,
        )
        threshold_value = self._metric_threshold(metric_name) if metric_name else None
        if not rows:
            return {
                "metric_name": metric_name,
                "threshold": threshold_value,
                "direction": self._metric_direction(metric_name),
                "unit": self._metric_unit(metric_name),
                "series": [],
            }

        bucket_sec = self._bucket_seconds_for(time_range_hours, bucket)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            series_name = row["path_label"] or row.get("node_name") or row["probe_name"]
            grouped[series_name].append(row)

        alert_rows = self._select_alert_rows(
            time_range_hours=time_range_hours,
            severities=None,
            statuses=["open", "acknowledged", "resolved"],
            kinds=["anomaly"],
            path_labels=path_labels,
            metric_names=[metric_name] if metric_name else None,
            acknowledged=None,
            anomaly_only=True,
            limit=300,
        )
        alert_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for alert in alert_rows:
            alert_groups[alert.get("path_label") or ""].append(alert)

        series_payload = []
        for series_name, series_rows in grouped.items():
            series_points = self._bucket_metric_rows(series_rows, bucket_sec=bucket_sec)
            values = [point["value"] for point in series_points]
            series_payload.append(
                {
                    "name": series_name,
                    "metric_name": metric_name,
                    "path_label": series_rows[0].get("path_label"),
                    "probe_name": series_rows[0].get("probe_name"),
                    "points": series_points,
                    "summary": {
                        "latest": values[-1] if values else None,
                        "min": min(values) if values else None,
                        "max": max(values) if values else None,
                        "avg": round(sum(values) / len(values), 3) if values else None,
                    },
                    "anomalies": [
                        {
                            "id": alert["id"],
                            "timestamp": alert["created_at"],
                            "value": alert.get("actual_value"),
                            "message": alert["message"],
                            "severity": alert["severity"],
                        }
                        for alert in alert_groups.get(series_rows[0].get("path_label") or "", [])
                    ],
                }
            )

        return {
            "metric_name": metric_name,
            "threshold": threshold_value,
            "direction": self._metric_direction(metric_name),
            "unit": self._metric_unit(metric_name),
            "series": sorted(series_payload, key=lambda item: DEFAULT_PATH_ORDER.index(item["name"]) if item["name"] in DEFAULT_PATH_ORDER else 999),
        }

    def build_path_health(
        self,
        time_range_hours: int,
        roles: list[str] | None = None,
        nodes: list[str] | None = None,
        path_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        summaries = self._build_path_summaries(
            time_range_hours=time_range_hours,
            roles=roles,
            nodes=nodes,
            path_labels=path_labels,
        )
        return {
            "paths": summaries,
            "trend_groups": {
                "latency": self.query_metric_series(
                    time_range_hours=time_range_hours,
                    roles=roles,
                    nodes=nodes,
                    path_labels=path_labels,
                    metric_name="connect_avg_ms",
                    bucket="auto",
                ),
                "throughput_down": self.query_metric_series(
                    time_range_hours=time_range_hours,
                    roles=roles,
                    nodes=nodes,
                    path_labels=path_labels,
                    metric_name="throughput_down_mbps",
                    bucket="auto",
                ),
                "throughput_up": self.query_metric_series(
                    time_range_hours=time_range_hours,
                    roles=roles,
                    nodes=nodes,
                    path_labels=path_labels,
                    metric_name="throughput_up_mbps",
                    bucket="auto",
                ),
                "loss": self.query_metric_series(
                    time_range_hours=time_range_hours,
                    roles=roles,
                    nodes=nodes,
                    path_labels=path_labels,
                    metric_name="packet_loss_pct",
                    bucket="auto",
                ),
                "load": self.query_metric_series(
                    time_range_hours=time_range_hours,
                    roles=roles,
                    nodes=nodes,
                    path_labels=path_labels,
                    metric_name="load_rtt_inflation_ms",
                    bucket="auto",
                ),
            },
        }

    def query_runs(
        self,
        time_range_hours: int,
        run_kinds: list[str] | None = None,
        statuses: list[str] | None = None,
        path_labels: list[str] | None = None,
        has_findings: bool | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [self._cutoff_iso(time_range_hours)]
        clauses = ["r.started_at >= ?"]
        if run_kinds:
            clauses.append(_sql_in_clause("r.run_kind", run_kinds, params))
        if statuses:
            clauses.append(_sql_in_clause("r.status", statuses, params))
        if has_findings is True:
            clauses.append("r.findings_count > 0")
        if has_findings is False:
            clauses.append("r.findings_count = 0")
        if path_labels:
            clauses.append(
                f"""EXISTS (
                        SELECT 1 FROM probe_result pr
                        WHERE pr.run_id = r.id AND { _sql_in_clause('pr.path_label', path_labels, params) }
                    )"""
            )
        params.append(limit)
        sql = f"""
            SELECT r.*
            FROM run r
            WHERE {' AND '.join(clauses)}
            ORDER BY r.started_at DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        decorated = [self._decorate_run(dict(row)) for row in rows]
        progress_map = self._build_run_progress_map([str(run["run_id"]) for run in decorated])
        for run in decorated:
            run["active"] = str(run.get("status") or "") == "running"
            run["progress"] = progress_map.get(str(run["run_id"]), _empty_run_progress())
        return decorated

    def get_run_detail(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            run_row = conn.execute("SELECT * FROM run WHERE id = ?", (run_id,)).fetchone()
            probe_rows = conn.execute(
                """
                SELECT pr.*, n.node_name, n.role
                FROM probe_result pr
                LEFT JOIN node n ON n.id = pr.node_id
                WHERE pr.run_id = ?
                ORDER BY COALESCE(pr.path_label, ''), pr.probe_name, pr.id
                """,
                (run_id,),
            ).fetchall()
            alert_rows = conn.execute(
                "SELECT * FROM alert_event WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall()
            event_rows = conn.execute(
                "SELECT * FROM run_event WHERE run_id = ? ORDER BY created_at ASC, id ASC",
                (run_id,),
            ).fetchall()
        if run_row is None:
            return None
        run = self._decorate_run(dict(run_row))
        if not run["threshold_findings"] and run.get("raw_path"):
            threshold_findings = self._load_threshold_findings_from_raw(run["raw_path"])
            if threshold_findings:
                run["threshold_findings"] = threshold_findings
        run["probes"] = [self._decorate_probe_result(dict(row)) for row in probe_rows]
        run["alerts"] = [self._decorate_alert(dict(row)) for row in alert_rows]
        run["active"] = str(run.get("status") or "") == "running"
        run["progress"] = self._summarize_run_events([self._decorate_run_event(dict(row)) for row in event_rows])
        return run

    def query_alert_events(
        self,
        time_range_hours: int,
        severities: list[str] | None = None,
        statuses: list[str] | None = None,
        kinds: list[str] | None = None,
        path_labels: list[str] | None = None,
        metric_names: list[str] | None = None,
        acknowledged: bool | None = None,
        anomaly_only: bool = False,
        fingerprint: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        rows = self._select_alert_rows(
            time_range_hours=time_range_hours,
            severities=severities,
            statuses=statuses,
            kinds=kinds,
            path_labels=path_labels,
            metric_names=metric_names,
            acknowledged=acknowledged,
            anomaly_only=anomaly_only,
            fingerprint=fingerprint,
            limit=limit,
        )
        decorated = [self._decorate_alert(dict(row)) for row in rows]
        summary = {
            "total": len(decorated),
            "open": sum(1 for item in decorated if item["status"] == "open"),
            "acknowledged": sum(1 for item in decorated if item["status"] == "acknowledged"),
            "resolved": sum(1 for item in decorated if item["status"] == "resolved"),
            "silenced": sum(1 for item in decorated if item["is_silenced"]),
        }
        return {"items": decorated, "summary": summary}

    def acknowledge_alert(self, alert_id: int, actor: str = "admin") -> dict[str, Any] | None:
        current = now_iso()
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM alert_event WHERE id = ?", (alert_id,)).fetchone()
            if row is None:
                return None
            conn.execute(
                """
                UPDATE alert_event
                SET status = CASE WHEN status = 'open' THEN 'acknowledged' ELSE status END,
                    acknowledged_at = COALESCE(acknowledged_at, ?),
                    acknowledged_by = COALESCE(acknowledged_by, ?)
                WHERE id = ?
                """,
                (current, actor, alert_id),
            )
            conn.commit()
            updated = conn.execute("SELECT * FROM alert_event WHERE id = ?", (alert_id,)).fetchone()
        return self._decorate_alert(dict(updated)) if updated is not None else None

    def silence_alert(self, alert_id: int, silenced_until: str, reason: str = "", actor: str = "admin") -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM alert_event WHERE id = ?", (alert_id,)).fetchone()
            if row is None:
                return None
            fingerprint = row["fingerprint"]
            if fingerprint:
                conn.execute(
                    """
                    UPDATE alert_event
                    SET silenced_until = ?, silence_reason = ?, acknowledged_at = COALESCE(acknowledged_at, ?),
                        acknowledged_by = COALESCE(acknowledged_by, ?),
                        status = CASE WHEN status = 'open' THEN 'acknowledged' ELSE status END
                    WHERE fingerprint = ?
                    """,
                    (silenced_until, reason, now_iso(), actor, fingerprint),
                )
            else:
                conn.execute(
                    """
                    UPDATE alert_event
                    SET silenced_until = ?, silence_reason = ?, acknowledged_at = COALESCE(acknowledged_at, ?),
                        acknowledged_by = COALESCE(acknowledged_by, ?),
                        status = CASE WHEN status = 'open' THEN 'acknowledged' ELSE status END
                    WHERE id = ?
                    """,
                    (silenced_until, reason, now_iso(), actor, alert_id),
                )
            conn.commit()
            updated = conn.execute("SELECT * FROM alert_event WHERE id = ?", (alert_id,)).fetchone()
        return self._decorate_alert(dict(updated)) if updated is not None else None

    def query_history(
        self,
        node: str | None = None,
        probe_name: str | None = None,
        metric_name: str | None = None,
        time_range_hours: int = 24,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return self._select_metric_rows(
            time_range_hours=time_range_hours,
            roles=None,
            nodes=[node] if node else None,
            path_labels=None,
            probe_names=[probe_name] if probe_name else None,
            metric_names=[metric_name] if metric_name else None,
            limit=limit,
        )

    def build_dashboard_snapshot(self) -> dict[str, Any]:
        topology_id = self.get_topology_id()
        settings = self.get_settings().model_dump()
        nodes = self.list_nodes()
        return {
            "topology_id": topology_id,
            "settings": settings,
            "schedules": self.list_schedules(),
            "nodes": nodes,
            "latest_runs": self.list_recent_runs(limit=12),
            "alerts": self.list_recent_alerts(limit=12),
            "history": {
                "samples": self.query_history(metric_name="cpu_usage_pct", time_range_hours=24, limit=180),
            },
        }

    def build_public_dashboard_snapshot(self, time_range_hours: int = 24) -> dict[str, Any]:
        settings = self.get_settings().model_dump()
        nodes = [self._public_node(node) for node in self.list_nodes()]
        runs = [self._public_run(run) for run in self.list_recent_runs(limit=12)]
        alerts = [self._public_alert(alert) for alert in self.list_recent_alerts(limit=12)]
        degraded_statuses = {"push-only", "pull-only"}
        offline_statuses = {"offline", "unpaired", "disabled"}
        online_nodes = sum(1 for node in nodes if node["status"] == "online")
        abnormal_nodes = sum(1 for node in nodes if node["status"] in degraded_statuses | offline_statuses)
        last_full = next((run for run in runs if run["run_kind"] == "full"), None)
        return {
            "topology_id": self.get_topology_id(),
            "topology_name": settings["topology_name"],
            "summary": {
                "total_nodes": len(nodes),
                "online_nodes": online_nodes,
                "degraded_nodes": sum(1 for node in nodes if node["status"] in degraded_statuses),
                "offline_nodes": sum(1 for node in nodes if node["status"] in offline_statuses),
                "active_alerts": sum(1 for alert in alerts if alert["status"] == "open"),
                "online_rate_pct": round((online_nodes / len(nodes)) * 100.0, 1) if nodes else 0.0,
                "abnormal_nodes": abnormal_nodes,
                "last_full_run_started_at": last_full.get("started_at") if last_full else None,
                "last_full_run_status": last_full.get("status") if last_full else None,
            },
            "nodes": nodes,
            "latest_runs": runs,
            "alerts": alerts[:8],
            "paths": self._build_path_summaries(
                time_range_hours=time_range_hours,
                roles=None,
                nodes=None,
                path_labels=["client_to_relay", "relay_to_server", "client_to_mc_public", "client_to_iperf_public"],
            ),
            "history": {
                "time_range_hours": time_range_hours,
                "trend_groups": self._build_trend_groups(time_range_hours=time_range_hours, public_mode=True),
            },
        }

    def _select_metric_rows(
        self,
        time_range_hours: int,
        roles: list[str] | None,
        nodes: list[str] | None,
        path_labels: list[str] | None,
        probe_names: list[str] | None,
        metric_names: list[str] | None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [self._cutoff_iso(time_range_hours)]
        clauses = ["ms.captured_at >= ?"]
        if roles:
            clauses.append(_sql_in_clause("n.role", roles, params))
        if nodes:
            clauses.append(_sql_in_clause("n.node_name", nodes, params))
        if path_labels:
            clauses.append(_sql_in_clause("ms.path_label", path_labels, params))
        if probe_names:
            clauses.append(_sql_in_clause("ms.probe_name", probe_names, params))
        if metric_names:
            clauses.append(_sql_in_clause("ms.metric_name", metric_names, params))
        params.append(limit)
        sql = f"""
            SELECT ms.*, n.node_name, n.role
            FROM metric_sample ms
            LEFT JOIN node n ON n.id = ms.node_id
            WHERE {' AND '.join(clauses)}
            ORDER BY ms.captured_at ASC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def _select_alert_rows(
        self,
        time_range_hours: int,
        severities: list[str] | None,
        statuses: list[str] | None,
        kinds: list[str] | None,
        path_labels: list[str] | None,
        metric_names: list[str] | None,
        acknowledged: bool | None,
        anomaly_only: bool,
        fingerprint: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [self._cutoff_iso(time_range_hours)]
        clauses = ["ae.created_at >= ?"]
        if severities:
            clauses.append(_sql_in_clause("ae.severity", severities, params))
        if statuses:
            clauses.append(_sql_in_clause("ae.status", statuses, params))
        if kinds:
            clauses.append(_sql_in_clause("ae.kind", kinds, params))
        if anomaly_only:
            clauses.append("ae.kind = 'anomaly'")
        if path_labels:
            clauses.append(_sql_in_clause("ae.path_label", path_labels, params))
        if metric_names:
            clauses.append(_sql_in_clause("ae.metric_name", metric_names, params))
        if fingerprint:
            clauses.append("ae.fingerprint = ?")
            params.append(fingerprint)
        if acknowledged is True:
            clauses.append("ae.acknowledged_at IS NOT NULL")
        if acknowledged is False:
            clauses.append("ae.acknowledged_at IS NULL")
        params.append(limit)
        sql = f"""
            SELECT ae.*, n.node_name, n.role
            FROM alert_event ae
            LEFT JOIN node n ON n.id = ae.node_id
            WHERE {' AND '.join(clauses)}
            ORDER BY ae.created_at DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def _build_path_summaries(
        self,
        time_range_hours: int,
        roles: list[str] | None,
        nodes: list[str] | None,
        path_labels: list[str] | None,
    ) -> list[dict[str, Any]]:
        metric_names = list({metric for metrics in PATH_CATEGORY_METRICS.values() for metric in metrics})
        rows = self._select_metric_rows(
            time_range_hours=time_range_hours,
            roles=roles,
            nodes=nodes,
            path_labels=path_labels,
            probe_names=None,
            metric_names=metric_names,
            limit=4000,
        )
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            label = row.get("path_label")
            if label:
                grouped[label].append(row)

        alert_rows = self._select_alert_rows(
            time_range_hours=time_range_hours,
            severities=None,
            statuses=["open", "acknowledged"],
            kinds=None,
            path_labels=path_labels,
            metric_names=None,
            acknowledged=None,
            anomaly_only=False,
            limit=500,
        )
        alert_counts: dict[str, int] = defaultdict(int)
        anomaly_counts: dict[str, int] = defaultdict(int)
        for alert in alert_rows:
            if alert.get("path_label"):
                alert_counts[alert["path_label"]] += 1
                if alert["kind"] == "anomaly":
                    anomaly_counts[alert["path_label"]] += 1

        ordered_labels = path_labels[:] if path_labels else list(grouped.keys())
        ordered = [label for label in DEFAULT_PATH_ORDER if label in ordered_labels or label in grouped]
        ordered.extend(label for label in ordered_labels if label not in ordered)

        payload = []
        for label in ordered:
            label_rows = grouped.get(label, [])
            latest_by_metric: dict[str, float] = {}
            avg_by_metric: dict[str, float] = {}
            for metric in metric_names:
                metric_rows = [row for row in label_rows if row["metric_name"] == metric]
                if metric_rows:
                    latest_by_metric[metric] = float(metric_rows[-1]["metric_value"])
                    avg_by_metric[metric] = round(sum(float(row["metric_value"]) for row in metric_rows) / len(metric_rows), 3)
            path_status = "healthy"
            if alert_counts.get(label):
                path_status = "degraded"
            if any(alert["severity"] == "error" for alert in alert_rows if alert.get("path_label") == label):
                path_status = "critical"
            payload.append(
                {
                    "path_label": label,
                    "status": path_status,
                    "latest": latest_by_metric,
                    "averages": avg_by_metric,
                    "open_alerts": alert_counts.get(label, 0),
                    "open_anomalies": anomaly_counts.get(label, 0),
                    "last_captured_at": label_rows[-1]["captured_at"] if label_rows else None,
                }
            )
        return payload

    def _build_trend_groups(self, time_range_hours: int, public_mode: bool) -> dict[str, Any]:
        if public_mode:
            specs = {
                "latency": [
                    ("client_to_relay", "rtt_avg_ms"),
                    ("relay_to_server", "rtt_avg_ms"),
                    ("client_to_mc_public", "connect_avg_ms"),
                ],
                "jitter": [
                    ("client_to_relay", "jitter_ms"),
                    ("relay_to_server", "jitter_ms"),
                ],
                "loss": [
                    ("client_to_relay", "packet_loss_pct"),
                    ("relay_to_server", "packet_loss_pct"),
                    ("client_to_mc_public", "connect_timeout_or_error_pct"),
                ],
                "throughput": [
                    ("client_to_iperf_public", "throughput_down_mbps"),
                    ("client_to_iperf_public", "throughput_up_mbps"),
                    ("relay_to_server", "throughput_down_mbps"),
                ],
            }
        else:
            specs = {
                "latency": [
                    ("client_to_relay", "rtt_avg_ms"),
                    ("relay_to_server", "rtt_avg_ms"),
                    ("client_to_mc_public", "connect_avg_ms"),
                ],
                "loss": [
                    ("client_to_relay", "packet_loss_pct"),
                    ("relay_to_server", "packet_loss_pct"),
                    ("client_to_mc_public", "connect_timeout_or_error_pct"),
                ],
                "throughput": [
                    ("client_to_iperf_public", "throughput_down_mbps"),
                    ("client_to_iperf_public", "throughput_up_mbps"),
                    ("relay_to_server", "throughput_down_mbps"),
                    ("relay_to_server", "throughput_up_mbps"),
                ],
                "system": [
                    ("client_system", "cpu_usage_pct"),
                    ("relay_system", "cpu_usage_pct"),
                    ("server_system", "cpu_usage_pct"),
                ],
            }

        payload: dict[str, Any] = {}
        for group_name, group_specs in specs.items():
            series_items = []
            for path_label, metric_name in group_specs:
                result = self.query_metric_series(
                    time_range_hours=time_range_hours,
                    roles=None,
                    nodes=None,
                    path_labels=[path_label],
                    probe_names=None,
                    metric_name=metric_name,
                    bucket="auto",
                    limit=800,
                )
                if result["series"]:
                    series_items.extend(result["series"])
            payload[group_name] = {
                "metric_names": [metric_name for _, metric_name in group_specs],
                "series": series_items,
            }
        return payload

    def _bucket_metric_rows(self, rows: list[dict[str, Any]], bucket_sec: int | None) -> list[dict[str, Any]]:
        if not bucket_sec:
            return [
                {
                    "timestamp": row["captured_at"],
                    "value": round(float(row["metric_value"]), 4),
                }
                for row in rows
            ]
        buckets: dict[int, list[float]] = defaultdict(list)
        for row in rows:
            timestamp = _parse_iso_timestamp(str(row["captured_at"]))
            bucket_key = int(timestamp.timestamp()) // bucket_sec
            buckets[bucket_key].append(float(row["metric_value"]))
        payload = []
        for bucket_key in sorted(buckets):
            bucket_time = datetime.fromtimestamp(bucket_key * bucket_sec, tz=timezone.utc).isoformat()
            values = buckets[bucket_key]
            payload.append({"timestamp": bucket_time, "value": round(sum(values) / len(values), 4)})
        return payload

    def _bucket_seconds_for(self, time_range_hours: int, bucket: str) -> int | None:
        if bucket == "raw":
            return None
        if time_range_hours <= 1:
            return 60
        if time_range_hours <= 6:
            return 300
        if time_range_hours <= 24:
            return 900
        if time_range_hours <= 24 * 7:
            return 3600
        return 14400

    def _metric_threshold(self, metric_name: str | None) -> float | None:
        if not metric_name:
            return None
        thresholds = self.get_settings().thresholds
        mapping = {
            "packet_loss_pct": thresholds.ping.packet_loss_pct_max,
            "rtt_avg_ms": thresholds.ping.rtt_avg_ms_max,
            "rtt_p95_ms": thresholds.ping.rtt_p95_ms_max,
            "jitter_ms": thresholds.ping.jitter_ms_max,
            "connect_avg_ms": thresholds.tcp.connect_avg_ms_max,
            "connect_p95_ms": thresholds.tcp.connect_p95_ms_max,
            "connect_timeout_or_error_pct": thresholds.tcp.timeout_or_error_pct_max,
            "throughput_up_mbps": thresholds.throughput.throughput_up_mbps_min,
            "throughput_down_mbps": thresholds.throughput.throughput_down_mbps_min,
            "load_rtt_inflation_ms": thresholds.load_inflation.load_rtt_inflation_ms_max,
            "cpu_usage_pct": thresholds.system.cpu_usage_pct_max,
            "memory_usage_pct": thresholds.system.memory_usage_pct_max,
        }
        return mapping.get(metric_name)

    def _metric_direction(self, metric_name: str | None) -> str:
        if metric_name in ANOMALY_LOW_METRICS:
            return "low"
        return "high"

    def _metric_unit(self, metric_name: str | None) -> str:
        if not metric_name:
            return ""
        if metric_name.endswith("_pct"):
            return "%"
        if metric_name.endswith("_mbps"):
            return "Mbps"
        if metric_name.endswith("_ms"):
            return "ms"
        if metric_name.endswith("_sec"):
            return "sec"
        return ""

    def _cutoff_iso(self, time_range_hours: int) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - (time_range_hours * 3600))) + "+00:00"

    def _load_threshold_findings_from_raw(self, raw_path: str) -> list[dict[str, Any]]:
        try:
            target = Path(raw_path)
            if not target.exists():
                target = Path.cwd() / raw_path
            payload = json.loads(target.read_text(encoding="utf-8"))
            return list(payload.get("threshold_findings") or [])
        except Exception:
            return []

    def _detect_metric_anomalies(self, conn: sqlite3.Connection, inserted_samples: list[dict[str, Any]]) -> None:
        current_time = now_iso()
        for sample in inserted_samples:
            metric_name = str(sample["metric_name"])
            if metric_name not in ANOMALY_HIGH_METRICS and metric_name not in ANOMALY_LOW_METRICS:
                continue
            path_label = sample.get("path_label")
            if not path_label:
                continue
            cutoff = (_parse_iso_timestamp(sample["captured_at"]) - timedelta(hours=24)).isoformat()
            history_rows = conn.execute(
                """
                SELECT metric_value
                FROM metric_sample
                WHERE path_label = ? AND probe_name = ? AND metric_name = ? AND captured_at >= ? AND id < ?
                ORDER BY captured_at DESC
                LIMIT 500
                """,
                (path_label, sample["probe_name"], metric_name, cutoff, sample["id"]),
            ).fetchall()
            values = [float(row["metric_value"]) for row in history_rows]
            if len(values) < 12:
                continue
            median = statistics.median(values)
            deviations = [abs(value - median) for value in values]
            mad = statistics.median(deviations)
            actual = float(sample["metric_value"])
            if mad == 0:
                if math.isclose(actual, median, rel_tol=0.0, abs_tol=1e-9):
                    continue
                robust_z = 999.0
            else:
                robust_z = 0.6745 * (actual - median) / mad
            direction = self._metric_direction(metric_name)
            if direction == "high" and robust_z < 3.5:
                continue
            if direction == "low" and robust_z > -3.5:
                continue
            threshold_value = median + ((3.5 * mad) / 0.6745) if direction == "high" else median - ((3.5 * mad) / 0.6745)
            fingerprint = self._alert_fingerprint(
                kind="anomaly",
                path_label=str(path_label),
                probe_name=str(sample["probe_name"]),
                metric_name=metric_name,
            )
            if self._is_fingerprint_silenced(conn, fingerprint=fingerprint, current_time=current_time):
                continue
            if self._has_recent_fingerprint(conn, fingerprint=fingerprint, current_time=current_time, within_minutes=30):
                continue
            self._insert_alert_row(
                conn=conn,
                kind="anomaly",
                severity="error" if abs(robust_z) >= 5.0 else "warning",
                status="open",
                message=f"{path_label} {metric_name} anomaly actual={actual:.3f} expected={threshold_value:.3f} z={robust_z:.2f}",
                created_at=current_time,
                node_id=sample.get("node_id"),
                run_id=sample.get("run_id"),
                path_label=str(path_label),
                probe_name=str(sample["probe_name"]),
                metric_name=metric_name,
                actual_value=actual,
                threshold_value=float(threshold_value),
                fingerprint=fingerprint,
            )

    def _insert_alert_row(
        self,
        conn: sqlite3.Connection,
        kind: str,
        severity: str,
        status: str,
        message: str,
        created_at: str,
        node_id: int | None = None,
        run_id: str | None = None,
        path_label: str | None = None,
        probe_name: str | None = None,
        metric_name: str | None = None,
        actual_value: float | None = None,
        threshold_value: float | None = None,
        fingerprint: str | None = None,
        acknowledged_at: str | None = None,
        acknowledged_by: str | None = None,
        silenced_until: str | None = None,
        silence_reason: str | None = None,
    ) -> None:
        conn.execute(
            """
            INSERT INTO alert_event (
                topology_id, node_id, run_id, kind, severity, status, message, created_at,
                path_label, probe_name, metric_name, actual_value, threshold_value, fingerprint,
                acknowledged_at, acknowledged_by, silenced_until, silence_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.get_topology_id(),
                node_id,
                run_id,
                kind,
                severity,
                status,
                message,
                created_at,
                path_label,
                probe_name,
                metric_name,
                actual_value,
                threshold_value,
                fingerprint,
                acknowledged_at,
                acknowledged_by,
                silenced_until,
                silence_reason,
            ),
        )

    def _alert_fingerprint(self, kind: str, path_label: str | None, probe_name: str | None, metric_name: str | None) -> str:
        payload = "|".join([kind or "", path_label or "", probe_name or "", metric_name or ""])
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _has_recent_fingerprint(self, conn: sqlite3.Connection, fingerprint: str, current_time: str, within_minutes: int) -> bool:
        cutoff = (_parse_iso_timestamp(current_time) - timedelta(minutes=within_minutes)).isoformat()
        row = conn.execute(
            "SELECT 1 FROM alert_event WHERE fingerprint = ? AND created_at >= ? LIMIT 1",
            (fingerprint, cutoff),
        ).fetchone()
        return row is not None

    def _is_fingerprint_silenced(self, conn: sqlite3.Connection, fingerprint: str, current_time: str) -> bool:
        row = conn.execute(
            """
            SELECT silenced_until
            FROM alert_event
            WHERE fingerprint = ? AND silenced_until IS NOT NULL
            ORDER BY silenced_until DESC
            LIMIT 1
            """,
            (fingerprint,),
        ).fetchone()
        return bool(
            row
            and row["silenced_until"]
            and _parse_iso_timestamp(str(row["silenced_until"])) > _parse_iso_timestamp(current_time)
        )

    def _public_node(self, node: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(node["id"]),
            "role": str(node["role"]),
            "node_name": str(node["node_name"]),
            "status": str(node["status"]),
            "enabled": bool(node["enabled"]),
            "paired": bool(node["paired"]),
            "last_seen_at": node.get("last_seen_at"),
            "connectivity": {
                "push": dict(node.get("connectivity", {}).get("push", {})),
                "pull": dict(node.get("connectivity", {}).get("pull", {})),
            },
        }

    def _public_run(self, run: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": str(run["run_id"]),
            "run_kind": str(run["run_kind"]),
            "status": str(run["status"]),
            "started_at": run.get("started_at"),
            "finished_at": run.get("finished_at"),
            "findings_count": int(run.get("findings_count") or 0),
            "conclusion": list(run.get("conclusion") or []),
            "error": run.get("error"),
            "html_path": run.get("html_path"),
        }

    def _public_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(alert["id"]),
            "kind": str(alert["kind"]),
            "severity": str(alert["severity"]),
            "status": str(alert["status"]),
            "message": str(alert["message"]),
            "created_at": alert.get("created_at"),
            "path_label": alert.get("path_label"),
            "metric_name": alert.get("metric_name"),
            "actual_value": alert.get("actual_value"),
            "threshold_value": alert.get("threshold_value"),
        }

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            existing_tables = {
                str(row["name"])
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
            }
            node_columns_before = self._table_columns(conn, "node") if "node" in existing_tables else set()
            job_columns_before = self._table_columns(conn, "job") if "job" in existing_tables else set()
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS topology (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    services_json TEXT NOT NULL,
                    thresholds_json TEXT NOT NULL,
                    scenarios_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS node (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topology_id INTEGER NOT NULL,
                    node_name TEXT NOT NULL UNIQUE,
                    role TEXT NOT NULL UNIQUE,
                    runtime_mode TEXT NOT NULL,
                    agent_url TEXT,
                    configured_pull_url TEXT,
                    advertised_pull_url TEXT,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    paired INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_seen_at TEXT,
                    last_heartbeat_at TEXT,
                    last_pull_checked_at TEXT,
                    last_status TEXT,
                    last_push_ok INTEGER NOT NULL DEFAULT 0,
                    last_pull_ok INTEGER NOT NULL DEFAULT 0,
                    last_push_error TEXT,
                    last_pull_error TEXT,
                    status_payload_json TEXT DEFAULT '{}',
                    endpoint_report_json TEXT DEFAULT '{}',
                    identity_json TEXT DEFAULT '{}',
                    capabilities_json TEXT DEFAULT '{}',
                    runtime_status_json TEXT DEFAULT '{}',
                    runtime_summary_json TEXT DEFAULT '{}',
                    supervisor_summary_json TEXT DEFAULT '{}',
                    push_state TEXT NOT NULL DEFAULT 'unknown',
                    push_checked_at TEXT,
                    push_error TEXT,
                    pull_state TEXT NOT NULL DEFAULT 'unknown',
                    pull_checked_at TEXT,
                    pull_error TEXT
                );
                CREATE TABLE IF NOT EXISTS node_secret (
                    node_id INTEGER PRIMARY KEY,
                    pair_code_hash TEXT,
                    pair_code_expires_at TEXT,
                    token_hash TEXT,
                    token_salt TEXT,
                    token_issued_at TEXT
                );
                CREATE TABLE IF NOT EXISTS schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topology_id INTEGER NOT NULL,
                    run_kind TEXT NOT NULL UNIQUE,
                    interval_sec INTEGER NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    next_run_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run (
                    id TEXT PRIMARY KEY,
                    topology_id INTEGER NOT NULL,
                    run_kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    source TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    error TEXT,
                    raw_path TEXT,
                    csv_path TEXT,
                    html_path TEXT,
                    findings_count INTEGER NOT NULL DEFAULT 0,
                    conclusion_json TEXT DEFAULT '[]',
                    threshold_findings_json TEXT DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS job (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topology_id INTEGER NOT NULL,
                    node_id INTEGER NOT NULL,
                    run_id TEXT NOT NULL,
                    job_kind TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    available_at TEXT NOT NULL,
                    timeout_sec REAL,
                    leased_at TEXT,
                    lease_expires_at TEXT,
                    completed_at TEXT,
                    result_json TEXT,
                    error TEXT
                );
                CREATE TABLE IF NOT EXISTS probe_result (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    node_id INTEGER,
                    probe_name TEXT NOT NULL,
                    path_label TEXT,
                    success INTEGER NOT NULL,
                    error TEXT,
                    metrics_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    samples_json TEXT DEFAULT '[]',
                    started_at TEXT,
                    duration_ms REAL NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS metric_sample (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id INTEGER,
                    run_id TEXT,
                    probe_result_id INTEGER,
                    probe_name TEXT NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    path_label TEXT,
                    captured_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS alert_event (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topology_id INTEGER NOT NULL,
                    node_id INTEGER,
                    run_id TEXT,
                    kind TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    path_label TEXT,
                    probe_name TEXT,
                    metric_name TEXT,
                    actual_value REAL,
                    threshold_value REAL,
                    fingerprint TEXT,
                    acknowledged_at TEXT,
                    acknowledged_by TEXT,
                    silenced_until TEXT,
                    silence_reason TEXT
                );
                CREATE TABLE IF NOT EXISTS control_action (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_kind TEXT NOT NULL,
                    target_id INTEGER,
                    action TEXT NOT NULL,
                    status TEXT NOT NULL,
                    confirmation_required INTEGER NOT NULL DEFAULT 0,
                    requested_by TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    started_at TEXT,
                    finished_at TEXT,
                    transport TEXT,
                    result_summary TEXT,
                    error_code TEXT,
                    error_detail TEXT,
                    audit_payload_json TEXT DEFAULT '{}'
                );
                CREATE TABLE IF NOT EXISTS run_event (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    event_kind TEXT NOT NULL,
                    message TEXT NOT NULL,
                    payload_json TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL
                );
                """
            )
            self._ensure_column(conn, "node", "configured_pull_url", "TEXT")
            self._ensure_column(conn, "node", "advertised_pull_url", "TEXT")
            self._ensure_column(conn, "node", "endpoint_report_json", "TEXT DEFAULT '{}'")
            self._ensure_column(conn, "node", "identity_json", "TEXT DEFAULT '{}'")
            self._ensure_column(conn, "node", "capabilities_json", "TEXT DEFAULT '{}'")
            self._ensure_column(conn, "node", "runtime_status_json", "TEXT DEFAULT '{}'")
            self._ensure_column(conn, "node", "runtime_summary_json", "TEXT DEFAULT '{}'")
            self._ensure_column(conn, "node", "supervisor_summary_json", "TEXT DEFAULT '{}'")
            self._ensure_column(conn, "node", "push_state", "TEXT NOT NULL DEFAULT 'unknown'")
            self._ensure_column(conn, "node", "push_checked_at", "TEXT")
            self._ensure_column(conn, "node", "push_error_code", "TEXT")
            self._ensure_column(conn, "node", "push_error", "TEXT")
            self._ensure_column(conn, "node", "pull_state", "TEXT NOT NULL DEFAULT 'unknown'")
            self._ensure_column(conn, "node", "pull_checked_at", "TEXT")
            self._ensure_column(conn, "node", "pull_error_code", "TEXT")
            self._ensure_column(conn, "node", "pull_error", "TEXT")
            self._ensure_column(conn, "run", "threshold_findings_json", "TEXT DEFAULT '[]'")
            self._ensure_column(conn, "job", "timeout_sec", "REAL")
            self._ensure_column(conn, "job", "lease_expires_at", "TEXT")
            self._ensure_column(conn, "probe_result", "samples_json", "TEXT DEFAULT '[]'")
            self._ensure_column(conn, "metric_sample", "path_label", "TEXT")
            self._ensure_column(conn, "alert_event", "path_label", "TEXT")
            self._ensure_column(conn, "alert_event", "probe_name", "TEXT")
            self._ensure_column(conn, "alert_event", "metric_name", "TEXT")
            self._ensure_column(conn, "alert_event", "actual_value", "REAL")
            self._ensure_column(conn, "alert_event", "threshold_value", "REAL")
            self._ensure_column(conn, "alert_event", "fingerprint", "TEXT")
            self._ensure_column(conn, "alert_event", "acknowledged_at", "TEXT")
            self._ensure_column(conn, "alert_event", "acknowledged_by", "TEXT")
            self._ensure_column(conn, "alert_event", "silenced_until", "TEXT")
            self._ensure_column(conn, "alert_event", "silence_reason", "TEXT")
            conn.execute("UPDATE run SET threshold_findings_json = '[]' WHERE threshold_findings_json IS NULL")
            conn.execute("UPDATE probe_result SET samples_json = '[]' WHERE samples_json IS NULL")
            conn.execute("UPDATE node SET identity_json = '{}' WHERE identity_json IS NULL")
            conn.execute("UPDATE node SET capabilities_json = '{}' WHERE capabilities_json IS NULL")
            conn.execute("UPDATE node SET endpoint_report_json = '{}' WHERE endpoint_report_json IS NULL")
            conn.execute("UPDATE node SET runtime_status_json = '{}' WHERE runtime_status_json IS NULL")
            conn.execute("UPDATE node SET runtime_summary_json = '{}' WHERE runtime_summary_json IS NULL")
            conn.execute("UPDATE node SET supervisor_summary_json = '{}' WHERE supervisor_summary_json IS NULL")
            conn.execute(
                """
                UPDATE node
                SET configured_pull_url = agent_url
                WHERE configured_pull_url IS NULL AND agent_url IS NOT NULL
                """
            )
            communication_migration_needed = (
                "configured_pull_url" not in node_columns_before
                or "advertised_pull_url" not in node_columns_before
                or "push_state" not in node_columns_before
                or "pull_state" not in node_columns_before
                or "lease_expires_at" not in job_columns_before
            )
            if communication_migration_needed:
                conn.execute(
                    """
                    UPDATE node
                    SET advertised_pull_url = NULL,
                        endpoint_report_json = '{}',
                        runtime_status_json = '{}',
                        runtime_summary_json = '{}',
                        supervisor_summary_json = '{}',
                        push_state = 'unknown',
                        push_checked_at = NULL,
                        push_error = NULL,
                        pull_state = 'unknown',
                        pull_checked_at = NULL,
                        pull_error = NULL,
                        last_status = NULL
                    """
                )
                conn.execute("DELETE FROM job WHERE status IN ('pending', 'leased')")
            conn.execute(
                """
                UPDATE metric_sample
                SET path_label = (
                    SELECT pr.path_label
                    FROM probe_result pr
                    WHERE pr.id = metric_sample.probe_result_id
                )
                WHERE path_label IS NULL AND probe_result_id IS NOT NULL
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metric_sample_metric_path_time ON metric_sample(metric_name, path_label, captured_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_metric_sample_node_probe_time ON metric_sample(node_id, probe_name, captured_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_event_status_severity_time ON alert_event(status, severity, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_event_fingerprint_status ON alert_event(fingerprint, status)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_control_action_status_requested ON control_action(status, requested_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_event_run_created ON run_event(run_id, created_at)"
            )
            conn.commit()
        if self.get_topology_id() <= 0:
            self.update_settings(PanelSettings())
        if not self.list_schedules():
            created_at = now_iso()
            topology_id = self.get_topology_id()
            with self._lock, self._connect() as conn:
                for run_kind, interval_sec in DEFAULT_SCHEDULES:
                    next_run = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + interval_sec)) + "+00:00"
                    conn.execute(
                        """
                        INSERT INTO schedule (topology_id, run_kind, interval_sec, enabled, next_run_at, created_at, updated_at)
                        VALUES (?, ?, ?, 1, ?, ?, ?)
                        """,
                        (topology_id, run_kind, interval_sec, next_run, created_at, created_at),
                    )
                conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _load_or_create_panel_secret(self) -> bytes:
        self.secret_path.parent.mkdir(parents=True, exist_ok=True)
        if self.secret_path.exists():
            return self.secret_path.read_text(encoding="utf-8").strip().encode("utf-8")
        secret = secrets.token_hex(32)
        self.secret_path.write_text(secret, encoding="utf-8")
        return secret.encode("utf-8")

    def _derive_node_token(self, node_id: int, token_salt: str) -> str:
        digest = hmac.new(self._panel_secret, f"{node_id}:{token_salt}".encode("utf-8"), hashlib.sha256).hexdigest()
        return digest

    def _classify_node(self, node: dict[str, Any]) -> str:
        if not node.get("enabled", True):
            return "disabled"
        if not node.get("paired"):
            return "unpaired"
        push_ok = self._channel_is_ok(node.get("push_state"))
        pull_ok = self._channel_is_ok(node.get("pull_state"))
        if push_ok and pull_ok:
            return "online"
        if push_ok:
            return "push-only"
        if pull_ok:
            return "pull-only"
        return "offline"

    def _decorate_node(
        self,
        node: dict[str, Any],
        active_actions: dict[tuple[str, int | None], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        node["enabled"] = bool(node.get("enabled"))
        node["paired"] = bool(node.get("paired"))
        node["push_state"] = str(node.get("push_state") or "unknown")
        node["pull_state"] = str(node.get("pull_state") or "unknown")
        identity = _loads(node.get("identity_json") or "{}")
        identity.setdefault("node_name", node.get("node_name"))
        identity.setdefault("role", node.get("role"))
        identity.setdefault("runtime_mode", node.get("runtime_mode"))
        capabilities = _loads(node.get("capabilities_json") or "{}")
        capabilities = AgentCapabilities.model_validate(capabilities or {}).model_dump()
        endpoint_report = _loads(node.get("endpoint_report_json") or "{}")
        endpoint_report.setdefault("advertise_url", node.get("advertised_pull_url"))
        endpoint_report.setdefault("control_listen_port", None)
        runtime_status = _loads(node.get("runtime_status_json") or "{}")
        runtime_status.setdefault("paired", bool(node.get("paired")))
        runtime_status.setdefault("last_heartbeat_at", node.get("last_heartbeat_at"))
        runtime_summary = RuntimeSummary.model_validate(_loads(node.get("runtime_summary_json") or "{}") or {}).model_dump()
        supervisor_summary = SupervisorSummary.model_validate(_loads(node.get("supervisor_summary_json") or "{}") or {}).model_dump()
        configured_pull_url = node.get("configured_pull_url")
        advertised_pull_url = node.get("advertised_pull_url") or endpoint_report.get("advertise_url")
        effective_pull_url = configured_pull_url or advertised_pull_url
        control_bridge_url = endpoint_report.get("control_url") or _derive_control_bridge_url(
            base_url=effective_pull_url,
            control_port=endpoint_report.get("control_listen_port"),
        )
        supervisor_summary.setdefault("bridge_url", control_bridge_url)
        endpoint_report.setdefault("control_url", control_bridge_url)
        endpoint_mismatch = bool(configured_pull_url and advertised_pull_url and not _urls_match(configured_pull_url, advertised_pull_url))
        action_lookup = active_actions or self._active_control_action_map(target_kind="node", target_id=int(node["id"]))
        active_action = action_lookup.get(("node", int(node["id"])))
        node["runtime"] = runtime_summary
        node["supervisor"] = supervisor_summary
        runtime_details = dict(runtime_summary.get("details") or {})
        available_actions, readonly_reason = self._derive_node_available_actions(node=node, control_bridge_url=control_bridge_url)
        runtime_details["available_actions"] = available_actions
        runtime_details["readonly_reason"] = readonly_reason
        runtime_details["active_action_id"] = active_action.get("id") if active_action else None
        runtime_details["active_action_summary"] = self._control_action_brief(active_action) if active_action else None
        runtime_summary["details"] = runtime_details
        node["identity"] = identity
        node["capabilities"] = capabilities
        node["endpoint_report"] = endpoint_report
        node["runtime_status"] = runtime_status
        node["active_action"] = active_action
        connectivity_status = self._classify_node(node)
        connectivity_diagnostic = self._build_connectivity_diagnostic(
            node=node,
            status=connectivity_status,
            endpoint_mismatch=endpoint_mismatch,
        )
        node["endpoints"] = {
            "configured_pull_url": configured_pull_url,
            "advertised_pull_url": advertised_pull_url,
            "effective_pull_url": effective_pull_url,
            "control_bridge_url": control_bridge_url,
        }
        node["connectivity"] = {
            "status": connectivity_status,
            "push": {
                "state": node["push_state"],
                "checked_at": node.get("push_checked_at"),
                "code": node.get("push_error_code"),
                "error": node.get("push_error"),
            },
            "pull": {
                "state": node["pull_state"],
                "checked_at": node.get("pull_checked_at"),
                "code": node.get("pull_error_code"),
                "error": node.get("pull_error"),
            },
            "endpoint_mismatch": endpoint_mismatch,
            "endpoint_mismatch_detail": (
                "Configured pull URL differs from the agent-advertised URL" if endpoint_mismatch else None
            ),
            "diagnostic_code": connectivity_diagnostic["diagnostic_code"],
            "attention_level": connectivity_diagnostic["attention_level"],
            "summary": connectivity_diagnostic["summary"],
            "recommended_step": connectivity_diagnostic["recommended_step"],
        }
        operator_summary, operator_severity, operator_recommended_step = self._node_operator_hint(
            runtime_details=runtime_details,
            connectivity=node["connectivity"],
        )
        runtime_details["operator_summary"] = operator_summary
        runtime_details["operator_severity"] = operator_severity
        runtime_details["operator_recommended_step"] = operator_recommended_step
        runtime_details["suggested_action"] = self._node_suggested_action(
            node_id=int(node["id"]),
            runtime_details=runtime_details,
            connectivity=node["connectivity"],
        )
        runtime_summary["details"] = runtime_details
        node["status"] = connectivity_status
        for key in (
            "agent_url",
            "last_push_ok",
            "last_pull_ok",
            "last_push_error",
            "last_pull_error",
            "last_pull_checked_at",
            "status_payload_json",
            "identity_json",
            "capabilities_json",
            "runtime_status_json",
            "runtime_summary_json",
            "supervisor_summary_json",
            "endpoint_report_json",
        ):
            node.pop(key, None)
        return node

    def _decorate_run(self, run: dict[str, Any]) -> dict[str, Any]:
        run["run_id"] = str(run.get("id") or "")
        run["findings_count"] = int(run.get("findings_count") or 0)
        run["conclusion"] = _loads(run.get("conclusion_json") or "[]")
        run["threshold_findings"] = _loads(run.get("threshold_findings_json") or "[]")
        return run

    def _decorate_probe_result(self, probe_result: dict[str, Any]) -> dict[str, Any]:
        probe_result["success"] = bool(probe_result.get("success"))
        probe_result["metrics"] = _loads(probe_result.get("metrics_json") or "{}")
        probe_result["metadata"] = _loads(probe_result.get("metadata_json") or "{}")
        probe_result["samples"] = _loads(probe_result.get("samples_json") or "[]")
        return probe_result

    def _decorate_alert(self, alert: dict[str, Any]) -> dict[str, Any]:
        alert["actual_value"] = float(alert["actual_value"]) if alert.get("actual_value") is not None else None
        alert["threshold_value"] = float(alert["threshold_value"]) if alert.get("threshold_value") is not None else None
        alert["acknowledged"] = alert.get("acknowledged_at") is not None
        alert["is_silenced"] = bool(
            alert.get("silenced_until")
            and _parse_iso_timestamp(str(alert.get("silenced_until"))) > _parse_iso_timestamp(now_iso())
        )
        alert["legacy_unstructured"] = not any(
            alert.get(key) for key in ("path_label", "probe_name", "metric_name", "fingerprint")
        )
        return alert

    def _decorate_control_action(self, action: dict[str, Any], include_detail: bool = True) -> dict[str, Any]:
        action["confirmation_required"] = bool(action.get("confirmation_required"))
        action["audit_payload"] = _loads(action.get("audit_payload_json") or "{}")
        target_name = self._control_action_target_name(action)
        request_payload = action["audit_payload"].get("request") if isinstance(action["audit_payload"], dict) else {}
        response_payload = action["audit_payload"].get("response") if isinstance(action["audit_payload"], dict) else {}
        if not isinstance(request_payload, dict):
            request_payload = {}
        if not isinstance(response_payload, dict):
            response_payload = {}
        log_excerpt = response_payload.get("log_excerpt") if isinstance(response_payload.get("log_excerpt"), list) else []
        log_location = response_payload.get("log_location") or (response_payload.get("supervisor") or {}).get("log_location")
        runtime_snapshot = {
            "runtime": response_payload.get("runtime") or {},
            "supervisor": response_payload.get("supervisor") or {},
        }
        failure = {}
        if action.get("error_code") or action.get("error_detail"):
            failure = {
                "code": action.get("error_code"),
                "detail": action.get("error_detail"),
            }
        summary, severity, code = self._control_action_summary(action)
        action["target_name"] = target_name
        action["is_dangerous"] = _is_dangerous_control_action(str(action.get("action") or ""))
        action["has_log_excerpt"] = bool(log_excerpt)
        action["has_runtime_snapshot"] = bool(runtime_snapshot["runtime"] or runtime_snapshot["supervisor"])
        action["active"] = str(action.get("status") or "") in {"queued", "running"}
        action["summary"] = summary
        action["severity"] = severity
        action["code"] = code
        if include_detail:
            action["request"] = request_payload
            action["response"] = response_payload
            action["log_excerpt"] = log_excerpt
            action["log_location"] = log_location
            action["runtime_snapshot"] = runtime_snapshot
            action["failure"] = failure
        else:
            action.pop("audit_payload", None)
        action.pop("audit_payload_json", None)
        return action

    def _control_action_summary(self, action: dict[str, Any]) -> tuple[str | None, str, str | None]:
        status = str(action.get("status") or "")
        result_summary = action.get("result_summary")
        error_code = action.get("error_code")
        error_detail = action.get("error_detail")
        action_name = str(action.get("action") or "action")
        if status in {"queued", "running"}:
            return (
                result_summary or f"{action_name} is {status}",
                "info",
                None,
            )
        if status == "failed":
            return (
                error_detail or result_summary or f"{action_name} failed",
                "warning",
                str(error_code) if error_code else None,
            )
        if status == "canceled":
            return (
                result_summary or f"{action_name} was canceled",
                "warning",
                str(error_code) if error_code else None,
            )
        if status == "completed":
            return (
                result_summary or f"{action_name} completed",
                "info",
                str(error_code) if error_code else None,
            )
        return (result_summary or error_detail or None, "info", str(error_code) if error_code else None)

    def _decorate_run_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event["payload"] = _loads(event.get("payload_json") or "{}")
        payload = event.get("payload") or {}
        if isinstance(payload, dict):
            event["node_id"] = self._node_id_from_name(payload.get("node_name"))
        else:
            event["node_id"] = None
        summary, severity, code = self._summarize_run_event(event)
        event["summary"] = summary
        event["severity"] = severity
        event["code"] = code
        event.pop("payload_json", None)
        return event

    def _build_run_progress_map(self, run_ids: list[str]) -> dict[str, dict[str, Any]]:
        run_ids = [run_id for run_id in run_ids if run_id]
        if not run_ids:
            return {}
        params: list[Any] = []
        clause = _sql_in_clause("run_id", run_ids, params)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM run_event WHERE {clause} ORDER BY run_id ASC, created_at ASC, id ASC",
                params,
            ).fetchall()
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            event = self._decorate_run_event(dict(row))
            grouped[str(event["run_id"])].append(event)
        return {run_id: self._summarize_run_events(grouped.get(run_id, [])) for run_id in run_ids}

    def _build_connectivity_diagnostic(
        self,
        node: dict[str, Any],
        status: str,
        endpoint_mismatch: bool,
    ) -> dict[str, str | None]:
        push_error_code = node.get("push_error_code")
        push_error = node.get("push_error")
        pull_error_code = node.get("pull_error_code")
        pull_error = node.get("pull_error")
        if status == "disabled":
            return {
                "diagnostic_code": "node_disabled",
                "attention_level": "info",
                "summary": "Node is disabled in the panel configuration.",
                "recommended_step": "Enable the node before expecting pairing, pull checks, or lifecycle control.",
            }
        if status == "unpaired":
            return {
                "diagnostic_code": "node_unpaired",
                "attention_level": "warning",
                "summary": "Node exists in the panel but has not paired with an agent yet.",
                "recommended_step": "Generate a pair command, start the agent, and wait for the first heartbeat.",
            }
        if endpoint_mismatch:
            summary = "Configured pull URL differs from the agent-advertised URL."
            if status == "online":
                summary = "Node is reachable, but the configured pull URL differs from the agent-advertised URL."
            elif status == "push-only":
                summary = "Heartbeat is healthy, but the configured pull URL differs from the agent-advertised URL."
            return {
                "diagnostic_code": "endpoint_mismatch",
                "attention_level": "warning",
                "summary": summary,
                "recommended_step": "Review configured_pull_url or save the agent-advertised URL if the node endpoint changed.",
            }
        if status == "online":
            return {
                "diagnostic_code": "healthy",
                "attention_level": "ok",
                "summary": "Heartbeat and pull checks are both healthy.",
                "recommended_step": None,
            }
        if status == "push-only":
            code = str(pull_error_code or "pull_unhealthy")
            detail = f" Pull error: {pull_error}" if pull_error else ""
            return {
                "diagnostic_code": code,
                "attention_level": "warning",
                "summary": f"Heartbeat is healthy, but pull checks are failing.{detail}".strip(),
                "recommended_step": self._connectivity_recommended_step(code, fallback="Use sync runtime or tail log, then verify the effective pull URL and agent listener."),
            }
        if status == "pull-only":
            code = str(push_error_code or "heartbeat_stale")
            detail = f" Push error: {push_error}" if push_error else ""
            return {
                "diagnostic_code": code,
                "attention_level": "warning",
                "summary": f"Panel can reach the agent, but heartbeats are missing.{detail}".strip(),
                "recommended_step": self._connectivity_recommended_step(code, fallback="Verify panel_url, node token, and the agent's outbound connectivity to the panel."),
            }
        code = str(push_error_code or pull_error_code or "connectivity_failed")
        detail_parts = [part for part in (push_error, pull_error) if part]
        detail = f" Details: {' | '.join(detail_parts)}" if detail_parts else ""
        return {
            "diagnostic_code": code,
            "attention_level": "error",
            "summary": f"Neither heartbeat nor pull checks are healthy.{detail}".strip(),
            "recommended_step": self._connectivity_recommended_step(code, fallback="Verify the configured pull URL, panel reachability, and agent health before retrying control actions."),
        }

    def _connectivity_recommended_step(self, code: str, fallback: str) -> str:
        mapping = {
            "missing_endpoint": "Save a configured pull URL or wait for the agent to advertise one before retrying pull-mode actions.",
            "timeout": "Check the effective pull URL, node listener, and any firewall or tailnet policy blocking pull-mode access.",
            "connect_error": "Verify the host and port in the effective pull URL and confirm the agent is listening there.",
            "auth_error": "Re-pair the node or verify the stored node token if pull-mode calls are rejected.",
            "protocol_mismatch": "Align panel and agent protocol versions before retrying pull-mode operations.",
            "heartbeat_timeout": "Restart the agent or inspect control bridge logs to restore outbound heartbeats.",
        }
        return mapping.get(code, fallback)

    def _summarize_run_events(self, events: list[dict[str, Any]]) -> dict[str, Any]:
        if not events:
            return _empty_run_progress()
        latest = events[-1]
        active_phase: str | None = None
        phase_started_at: str | None = None
        latest_probe: dict[str, Any] | None = None
        latest_queue_job: dict[str, Any] | None = None
        last_failure_code: str | None = None
        last_failure_message: str | None = None
        last_failure_at: str | None = None
        for event in events:
            payload = event.get("payload") or {}
            phase = payload.get("phase") if isinstance(payload, dict) else None
            if event.get("event_kind") == "phase_started":
                active_phase = str(phase) if phase else None
                phase_started_at = event.get("created_at")
            elif event.get("event_kind") == "phase_completed" and phase and phase == active_phase:
                active_phase = None
                phase_started_at = None
            elif event.get("event_kind") in {"run_finished", "run_failed"}:
                active_phase = None
                phase_started_at = None
            if event.get("event_kind") in {"probe_dispatched", "probe_completed"} and isinstance(payload, dict):
                latest_probe = {
                    "task": payload.get("task"),
                    "node_name": payload.get("node_name"),
                    "node_id": self._node_id_from_name(payload.get("node_name")),
                    "path_label": payload.get("path_label"),
                    "created_at": event.get("created_at"),
                }
            if event.get("event_kind") in {
                "queue_enqueued",
                "queue_leased",
                "queue_timeout",
                "queue_failed",
                "queue_completed",
                "queue_completion_ignored",
            } and isinstance(payload, dict):
                job_payload = payload.get("job") if isinstance(payload.get("job"), dict) else {}
                latest_queue_job = {
                    "event_kind": event.get("event_kind"),
                    "created_at": event.get("created_at"),
                    "job_id": payload.get("job_id") or job_payload.get("job_id"),
                    "task": payload.get("task") or job_payload.get("task"),
                    "node_name": payload.get("node_name"),
                    "node_id": self._node_id_from_name(payload.get("node_name")),
                    "path_label": payload.get("path_label"),
                    "status": payload.get("queue_status") or job_payload.get("status"),
                    "timeout_sec": payload.get("timeout_sec") or job_payload.get("timeout_sec"),
                    "lease_expires_at": job_payload.get("lease_expires_at"),
                    "lease_state": job_payload.get("lease_state"),
                    "success": payload.get("success"),
                    "error_code": payload.get("error_code"),
                    "error": payload.get("error"),
                }
            if isinstance(payload, dict):
                failure_code = payload.get("error_code")
                failure_message = payload.get("error")
                if failure_code or (event.get("event_kind") == "run_failed" and failure_message):
                    last_failure_code = str(failure_code) if failure_code else "run_failed"
                    last_failure_message = str(failure_message or event.get("message") or "")
                    last_failure_at = event.get("created_at")
        current_blocker = self._build_current_run_blocker(
            latest=latest,
            latest_probe=latest_probe,
            latest_queue_job=latest_queue_job,
        )
        headline, headline_severity = self._run_progress_headline(
            latest=latest,
            active_phase=active_phase,
            current_blocker=current_blocker,
        )
        recommended_step = self._run_progress_recommended_step(
            latest=latest,
            current_blocker=current_blocker,
            last_failure_code=last_failure_code,
            last_failure_at=last_failure_at,
        )
        return {
            "events_count": len(events),
            "last_event_kind": latest.get("event_kind"),
            "last_event_message": latest.get("message"),
            "last_event_at": latest.get("created_at"),
            "active_phase": active_phase,
            "phase_started_at": phase_started_at,
            "latest_probe": latest_probe,
            "latest_queue_job": latest_queue_job,
            "current_blocker": current_blocker,
            "headline": headline,
            "headline_severity": headline_severity,
            "last_failure_code": last_failure_code,
            "last_failure_message": last_failure_message,
            "last_failure_at": last_failure_at,
            "recommended_step": recommended_step,
        }

    def _node_id_from_role(self, role: Any) -> int | None:
        if not role:
            return None
        node = self.get_node_by_role(str(role))
        return int(node["id"]) if node is not None else None

    def _node_id_from_name(self, node_name: Any) -> int | None:
        if not node_name:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM node WHERE node_name = ?", (str(node_name),)).fetchone()
        return int(row["id"]) if row is not None else None

    def _node_id_from_path(self, path_label: str) -> int | None:
        label = path_label.lower()
        if "client" in label:
            node = self.get_node_by_role("client")
            return int(node["id"]) if node else None
        if "relay" in label:
            node = self.get_node_by_role("relay")
            return int(node["id"]) if node else None
        if "server" in label:
            node = self.get_node_by_role("server")
            return int(node["id"]) if node else None
        return None

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
        existing = self._table_columns(conn, table)
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _table_columns(self, conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}

    def _channel_is_ok(self, state: Any) -> bool:
        return str(state or "unknown") == "ok"

    def _active_control_action_map(
        self,
        target_kind: str | None = None,
        target_id: int | None = None,
    ) -> dict[tuple[str, int | None], dict[str, Any]]:
        params: list[Any] = []
        clauses = ["status IN ('queued', 'running')"]
        if target_kind is not None:
            clauses.append("target_kind = ?")
            params.append(target_kind)
        if target_kind is not None and target_id is None:
            clauses.append("target_id IS NULL")
        elif target_id is not None:
            clauses.append("target_id = ?")
            params.append(target_id)
        query = (
            "SELECT * FROM control_action "
            f"WHERE {' AND '.join(clauses)} "
            "ORDER BY requested_at ASC, id ASC"
        )
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        results: dict[tuple[str, int | None], dict[str, Any]] = {}
        for row in rows:
            decorated = self._decorate_control_action(dict(row), include_detail=False)
            key = (str(decorated["target_kind"]), decorated.get("target_id"))
            results.setdefault(key, decorated)
        return results

    def _control_action_target_name(self, action: dict[str, Any]) -> str:
        audit_payload = action.get("audit_payload")
        if isinstance(audit_payload, dict) and audit_payload.get("target_name"):
            return str(audit_payload["target_name"])
        if str(action.get("target_kind") or "") == "panel":
            return "panel"
        target_id = action.get("target_id")
        if target_id is None:
            return "unknown"
        with self._connect() as conn:
            row = conn.execute("SELECT node_name FROM node WHERE id = ?", (target_id,)).fetchone()
        if row is not None and row["node_name"]:
            return str(row["node_name"])
        return str(target_id)

    def _derive_node_available_actions(self, node: dict[str, Any], control_bridge_url: str | None) -> tuple[list[str], str | None]:
        if not node.get("paired"):
            return [], "Node must be paired before runtime actions are available"
        if not control_bridge_url:
            return [], "Node control bridge is unavailable for this node"
        runtime_details = node.get("runtime", {}).get("details", {})
        supervisor = node.get("supervisor", {})
        if supervisor.get("checked_at") and supervisor.get("control_available") is False:
            code = str(runtime_details.get("bridge_error_code") or "control_bridge_unreachable")
            if code == "auth_error":
                return [], "Node control bridge rejected authentication; re-pair or refresh node credentials before lifecycle actions."
            if code in {"timeout", "connect_error", "bridge_unavailable", "control_bridge_unreachable"}:
                return [], "Node control bridge is currently unreachable; retry sync runtime after the bridge recovers."
            return [], "Node control bridge is unavailable for lifecycle actions right now."
        return ["sync_runtime", "tail_log", "start", "restart", "stop"], None

    def _control_action_brief(self, action: dict[str, Any] | None) -> str | None:
        if not action:
            return None
        return f"{action.get('action')} ({action.get('status')})"

    def _node_operator_hint(
        self,
        runtime_details: dict[str, Any],
        connectivity: dict[str, Any],
    ) -> tuple[str | None, str, str | None]:
        if runtime_details.get("active_action_summary"):
            return (
                str(runtime_details.get("active_action_summary")),
                "info",
                "Open the action detail to follow progress before issuing another lifecycle action for this node.",
            )
        level = str(connectivity.get("attention_level") or "ok")
        if level != "ok" and connectivity.get("summary"):
            return (
                str(connectivity.get("summary")),
                level,
                str(connectivity.get("recommended_step")) if connectivity.get("recommended_step") else None,
            )
        readonly_reason = runtime_details.get("readonly_reason")
        if readonly_reason:
            severity = "warning" if "unreachable" in str(readonly_reason).lower() else "info"
            return str(readonly_reason), severity, None
        return None, "info", None

    def _node_suggested_action(
        self,
        node_id: int,
        runtime_details: dict[str, Any],
        connectivity: dict[str, Any],
    ) -> dict[str, Any] | None:
        active_action_id = runtime_details.get("active_action_id")
        if active_action_id:
            return _suggested_action(
                kind="open_action",
                target_kind="action",
                action_id=int(active_action_id),
                label="View action",
            )
        available_actions = set(runtime_details.get("available_actions") or [])
        level = str(connectivity.get("attention_level") or "ok")
        if level != "ok":
            if "sync_runtime" in available_actions:
                return _suggested_action(
                    kind="sync_runtime",
                    target_kind="node",
                    target_id=node_id,
                    label="Sync node runtime",
                )
            if "tail_log" in available_actions:
                return _suggested_action(
                    kind="tail_log",
                    target_kind="node",
                    target_id=node_id,
                    label="Tail node log",
                )
        readonly_reason = str(runtime_details.get("readonly_reason") or "")
        if readonly_reason and "tail_log" in available_actions:
            return _suggested_action(
                kind="tail_log",
                target_kind="node",
                target_id=node_id,
                label="Tail node log",
            )
        return None

    def _run_recommended_step(self, code: str | None) -> str | None:
        if not code:
            return None
        mapping = {
            "timeout": "Inspect the node runtime and logs, then verify the agent listener and network reachability.",
            "connect_error": "Check the effective pull URL and confirm the target agent is listening on the expected host and port.",
            "auth_error": "Re-pair the node or verify the stored node token before retrying the run.",
            "protocol_mismatch": "Align panel and agent protocol versions before rerunning the affected phase.",
            "queue_timeout": "Check heartbeat freshness and control bridge logs, then retry once the node resumes queue processing.",
            "queue_not_leased": "The queued job never reached the node. Verify heartbeat freshness and that the node still supports heartbeat_queue dispatch.",
            "queue_lease_timeout": "The queued job was leased but never completed in time. Inspect node runtime, control bridge status, and agent logs before retrying.",
            "queue_lease_expired": "The queued job lease expired before a result returned. Check whether the agent lost connectivity or stalled mid-task.",
            "queue_failed": "Inspect the queued job error and node logs before retrying the phase.",
            "transport_unavailable": "Restore either pull or heartbeat connectivity for the node before retrying the run.",
            "run_failed": "Inspect the latest run events and node diagnostics to identify the failing phase before rerunning.",
        }
        return mapping.get(code)

    def _current_run_blocker_recommended_step(self, code: str | None) -> str | None:
        if not code:
            return None
        mapping = {
            "queue_waiting": "Wait for the next heartbeat lease cycle or inspect the node's push connectivity if the job stays pending.",
            "queue_inflight": "Wait for the leased job to complete, or inspect node runtime and logs if it stops making progress.",
        }
        return mapping.get(code) or self._run_recommended_step(code)

    def _build_current_run_blocker(
        self,
        latest: dict[str, Any],
        latest_probe: dict[str, Any] | None,
        latest_queue_job: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        latest_event_kind = str(latest.get("event_kind") or "")
        latest_event_at = latest.get("created_at")
        if latest_queue_job and latest_queue_job.get("job_id") and latest_queue_job.get("created_at") == latest_event_at:
            status = str(latest_queue_job.get("status") or latest_queue_job.get("event_kind") or "")
            code = str(latest_queue_job.get("error_code") or "")
            if latest_event_kind in {"queue_timeout", "queue_failed", "queue_completion_ignored"} or code:
                blocker_code = code or ("queue_failed" if status == "failed" else status or "queue_failed")
                summary = (
                    f"Queued job {latest_queue_job.get('job_id')} for {latest_queue_job.get('task') or 'queued task'} "
                    f"failed on {latest_queue_job.get('node_name') or 'node'}."
                )
                return {
                    "kind": "queue",
                    "code": blocker_code,
                    "severity": "warning",
                    "summary": summary,
                    "recommended_step": self._current_run_blocker_recommended_step(blocker_code),
                    "suggested_action": (
                        _suggested_action(
                            kind="open_node",
                            target_kind="node",
                            target_id=int(latest_queue_job["node_id"]),
                            label="Open node",
                        )
                        if latest_queue_job.get("node_id") is not None
                        else None
                    ),
                    "node_name": latest_queue_job.get("node_name"),
                    "node_id": latest_queue_job.get("node_id"),
                    "path_label": latest_queue_job.get("path_label"),
                    "task": latest_queue_job.get("task"),
                    "job_id": latest_queue_job.get("job_id"),
                    "lease_expires_at": latest_queue_job.get("lease_expires_at"),
                    "status": status,
                }
            if status in {"pending", "leased"}:
                blocker_code = "queue_waiting" if status == "pending" else "queue_inflight"
                summary = (
                    f"Queued job {latest_queue_job.get('job_id')} for {latest_queue_job.get('task') or 'queued task'} "
                    f"is {status} on {latest_queue_job.get('node_name') or 'node'}."
                )
                return {
                    "kind": "queue",
                    "code": blocker_code,
                    "severity": "info",
                    "summary": summary,
                    "recommended_step": self._current_run_blocker_recommended_step(blocker_code),
                    "suggested_action": (
                        _suggested_action(
                            kind="open_node",
                            target_kind="node",
                            target_id=int(latest_queue_job["node_id"]),
                            label="Open node",
                        )
                        if latest_queue_job.get("node_id") is not None
                        else None
                    ),
                    "node_name": latest_queue_job.get("node_name"),
                    "node_id": latest_queue_job.get("node_id"),
                    "path_label": latest_queue_job.get("path_label"),
                    "task": latest_queue_job.get("task"),
                    "job_id": latest_queue_job.get("job_id"),
                    "lease_expires_at": latest_queue_job.get("lease_expires_at"),
                    "status": status,
                }
            return None
        if latest_event_kind == "probe_dispatched" and latest_probe:
            return {
                "kind": "probe",
                "code": "probe_dispatched",
                "severity": "info",
                "summary": (
                    f"Latest probe {latest_probe.get('task') or 'probe'} was dispatched"
                    + (f" on {latest_probe.get('path_label')}" if latest_probe.get("path_label") else "")
                    + (f" to {latest_probe.get('node_name')}" if latest_probe.get("node_name") else "")
                    + "."
                ),
                "recommended_step": "Wait for the probe result or inspect node diagnostics if the same probe remains the latest event for too long.",
                "suggested_action": (
                    _suggested_action(
                        kind="open_node",
                        target_kind="node",
                        target_id=int(latest_probe["node_id"]),
                        label="Open node",
                    )
                    if latest_probe.get("node_id") is not None
                    else None
                ),
                "node_name": latest_probe.get("node_name"),
                "node_id": latest_probe.get("node_id"),
                "path_label": latest_probe.get("path_label"),
                "task": latest_probe.get("task"),
                "job_id": None,
                "lease_expires_at": None,
                "status": None,
            }
        return None

    def _run_progress_headline(
        self,
        latest: dict[str, Any],
        active_phase: str | None,
        current_blocker: dict[str, Any] | None,
    ) -> tuple[str | None, str]:
        if current_blocker and current_blocker.get("summary"):
            return str(current_blocker["summary"]), str(current_blocker.get("severity") or "info")
        if active_phase:
            return f"phase {active_phase}", "info"
        if latest.get("message"):
            severity = "warning" if str(latest.get("event_kind") or "") in {"run_failed", "probe_transport_error"} else "info"
            return str(latest.get("message")), severity
        if latest.get("event_kind"):
            return str(latest.get("event_kind")), "info"
        return None, "info"

    def _run_progress_recommended_step(
        self,
        latest: dict[str, Any],
        current_blocker: dict[str, Any] | None,
        last_failure_code: str | None,
        last_failure_at: str | None,
    ) -> str | None:
        if current_blocker and current_blocker.get("recommended_step"):
            return str(current_blocker["recommended_step"])
        if last_failure_code and last_failure_at and last_failure_at == latest.get("created_at"):
            return self._run_recommended_step(last_failure_code)
        return None

    def _summarize_run_event(self, event: dict[str, Any]) -> tuple[str | None, str, str | None]:
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        kind = str(event.get("event_kind") or "")
        if kind.startswith("queue_"):
            parts: list[str] = []
            if payload.get("job_id"):
                parts.append(f"job {payload['job_id']}")
            if payload.get("task"):
                parts.append(str(payload["task"]))
            if payload.get("node_name"):
                parts.append(f"node {payload['node_name']}")
            if payload.get("queue_status"):
                parts.append(f"status {payload['queue_status']}")
            if payload.get("error_code"):
                parts.append(f"code {payload['error_code']}")
            if payload.get("error"):
                parts.append(str(payload["error"]))
            severity = "warning" if kind in {"queue_timeout", "queue_failed", "queue_completion_ignored"} else "info"
            return (" | ".join(parts) if parts else None), severity, payload.get("error_code")
        if kind == "probe_dispatched":
            parts = [str(payload.get("task") or "probe")]
            if payload.get("node_name"):
                parts.append(f"node {payload['node_name']}")
            if payload.get("path_label"):
                parts.append(f"path {payload['path_label']}")
            return (" | ".join(parts) if parts else None), "info", None
        if kind == "probe_transport_error":
            parts = [str(payload.get("task") or "probe transport error")]
            if payload.get("transport"):
                parts.append(f"transport {payload['transport']}")
            if payload.get("node_name"):
                parts.append(f"node {payload['node_name']}")
            if payload.get("error_code"):
                parts.append(f"code {payload['error_code']}")
            if payload.get("error"):
                parts.append(str(payload["error"]))
            return (" | ".join(parts) if parts else None), "warning", payload.get("error_code")
        if kind == "probe_completed":
            parts = [str(payload.get("task") or "probe completed")]
            if payload.get("transport"):
                parts.append(f"transport {payload['transport']}")
            if payload.get("node_name"):
                parts.append(f"node {payload['node_name']}")
            if payload.get("error_code"):
                parts.append(f"code {payload['error_code']}")
            severity = "info" if payload.get("success", True) else "warning"
            return (" | ".join(parts) if parts else None), severity, payload.get("error_code")
        if kind in {"phase_started", "phase_completed"}:
            phase = payload.get("phase")
            return (f"phase {phase}" if phase else None), "info", None
        if kind == "run_failed":
            return str(payload.get("error") or event.get("message") or "run failed"), "warning", payload.get("error_code") or "run_failed"
        return None, "info", payload.get("error_code")

    def _job_snapshot(self, job: dict[str, Any]) -> dict[str, Any]:
        payload = _loads(job.get("payload_json") or "{}")
        result = _loads(job.get("result_json") or "{}") if job.get("result_json") else None
        snapshot = {
            "job_id": int(job["id"]),
            "run_id": str(job["run_id"]),
            "node_id": int(job["node_id"]),
            "task": str(job["job_kind"]),
            "status": str(job["status"]),
            "created_at": job.get("created_at"),
            "available_at": job.get("available_at"),
            "leased_at": job.get("leased_at"),
            "lease_expires_at": job.get("lease_expires_at"),
            "completed_at": job.get("completed_at"),
            "timeout_sec": float(job["timeout_sec"]) if job.get("timeout_sec") is not None else None,
            "error": job.get("error"),
            "path_label": payload.get("path_label") if isinstance(payload, dict) else None,
            "result_success": result.get("success") if isinstance(result, dict) else None,
        }
        lease_expires_at = snapshot.get("lease_expires_at")
        if isinstance(lease_expires_at, str) and lease_expires_at:
            try:
                lease_remaining = (_parse_iso_timestamp(lease_expires_at) - datetime.now(timezone.utc)).total_seconds()
                snapshot["lease_remaining_sec"] = round(lease_remaining, 3)
                snapshot["lease_expired"] = lease_remaining <= 0
            except Exception:
                snapshot["lease_remaining_sec"] = None
                snapshot["lease_expired"] = None
        else:
            snapshot["lease_remaining_sec"] = None
            snapshot["lease_expired"] = None
        if snapshot["status"] == "pending":
            snapshot["lease_state"] = "not-leased"
        elif snapshot["status"] == "leased":
            snapshot["lease_state"] = "expired" if snapshot.get("lease_expired") else "active"
        elif snapshot["status"] == "completed":
            snapshot["lease_state"] = "completed"
        elif snapshot["status"] == "failed":
            snapshot["lease_state"] = "failed"
        else:
            snapshot["lease_state"] = snapshot["status"]
        return snapshot


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | bytes | bytearray | None) -> Any:
    if not value:
        return {}
    return json.loads(value)


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sql_in_clause(field: str, values: list[Any], params: list[Any]) -> str:
    placeholders = ", ".join("?" for _ in values)
    params.extend(values)
    return f"{field} IN ({placeholders})"


def _parse_iso_timestamp(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _urls_match(left: str, right: str) -> bool:
    return left.rstrip("/") == right.rstrip("/")


def _derive_control_bridge_url(base_url: str | None, control_port: Any) -> str | None:
    if not base_url or control_port in {None, ""}:
        return None
    try:
        parsed = urlparse(str(base_url))
        if not parsed.scheme or not parsed.hostname:
            return None
        return parsed._replace(netloc=f"{parsed.hostname}:{int(control_port)}").geturl()
    except Exception:
        return None


def _is_dangerous_control_action(action: str) -> bool:
    return action in {"start", "stop", "restart", "pause_scheduler", "resume_scheduler"}


def _empty_run_progress() -> dict[str, Any]:
    return {
        "events_count": 0,
        "last_event_kind": None,
        "last_event_message": None,
        "last_event_at": None,
        "active_phase": None,
        "phase_started_at": None,
        "latest_probe": None,
        "latest_queue_job": None,
        "current_blocker": None,
        "headline": None,
        "headline_severity": "info",
        "last_failure_code": None,
        "last_failure_message": None,
        "last_failure_at": None,
        "recommended_step": None,
    }
