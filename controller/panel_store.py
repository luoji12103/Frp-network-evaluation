"""SQLite-backed persistence for the monitoring panel."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from controller.panel_models import NodeUpsertRequest, PanelSettings
from probes.common import ProbeResult, RunResult, ThresholdFinding, now_iso


DEFAULT_SCHEDULES = (
    ("system", 30),
    ("baseline", 60),
    ("capacity", 300),
)


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
        return [self._decorate_node(dict(row)) for row in rows]

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
        return self._decorate_node(dict(row)) if row is not None else None

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
        return self._decorate_node(dict(row)) if row is not None else None

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
        return self._decorate_node(dict(row)) if row is not None else None

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
                        topology_id, node_name, role, runtime_mode, agent_url, enabled,
                        paired, created_at, updated_at, last_status, last_push_ok, last_pull_ok
                    )
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 'unpaired', 0, 0)
                    """,
                    (
                        topology_id,
                        payload.node_name,
                        payload.role,
                        payload.runtime_mode,
                        payload.agent_url,
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
                    SET node_name = ?, role = ?, runtime_mode = ?, agent_url = ?, enabled = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        payload.node_name,
                        payload.role,
                        payload.runtime_mode,
                        payload.agent_url,
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
        node_name: str,
        role: str,
        runtime_mode: str,
        pair_code: str,
        agent_url: str | None,
        advertise_url: str | None,
    ) -> tuple[dict[str, Any], str]:
        node = self.get_node_by_name(node_name)
        if node is None:
            raise ValueError(f"Unknown node: {node_name}")
        if node["role"] != role:
            raise ValueError("Role does not match the paired node")
        if node["runtime_mode"] != runtime_mode:
            raise ValueError("Runtime mode does not match the paired node")

        with self._connect() as conn:
            secret_row = conn.execute("SELECT * FROM node_secret WHERE node_id = ?", (node["id"],)).fetchone()
        if secret_row is None or not secret_row["pair_code_hash"]:
            raise ValueError("Pair code has not been generated for this node")
        if secret_row["pair_code_expires_at"] and str(secret_row["pair_code_expires_at"]) < now_iso():
            raise ValueError("Pair code has expired")
        if not hmac.compare_digest(str(secret_row["pair_code_hash"]), _hash_token(pair_code)):
            raise ValueError("Pair code is invalid")

        token_salt = secrets.token_hex(12)
        node_token = self._derive_node_token(node["id"], token_salt)
        presented_url = advertise_url or agent_url or node.get("agent_url")
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
                (_hash_token(node_token), token_salt, now_iso(), node["id"]),
            )
            conn.execute(
                """
                UPDATE node
                SET paired = 1,
                    agent_url = COALESCE(?, agent_url),
                    last_seen_at = ?,
                    last_push_ok = 1,
                    last_status = 'push-online',
                    updated_at = ?
                WHERE id = ?
                """,
                (presented_url, now_iso(), now_iso(), node["id"]),
            )
            conn.commit()
        paired = self.get_node(node["id"])
        if paired is None:
            raise KeyError(node["id"])
        return paired, node_token

    def resolve_node_from_token(self, node_name: str, token: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT n.*, ns.token_hash, ns.token_salt
                FROM node n
                JOIN node_secret ns ON ns.node_id = n.id
                WHERE n.node_name = ?
                """,
                (node_name,),
            ).fetchone()
        if row is None or not row["token_hash"]:
            raise ValueError("Node is not paired")
        if not hmac.compare_digest(str(row["token_hash"]), _hash_token(token)):
            raise ValueError("Invalid node token")
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
        agent_url: str | None,
        status: dict[str, Any],
    ) -> dict[str, Any]:
        current = now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE node
                SET agent_url = COALESCE(?, agent_url),
                    last_seen_at = ?,
                    last_heartbeat_at = ?,
                    last_push_ok = 1,
                    last_push_error = NULL,
                    status_payload_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (agent_url, current, current, _dumps(status), current, node_id),
            )
            conn.commit()
        return self.refresh_node_status(node_id)

    def mark_push_error(self, node_id: int, error: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE node SET last_push_ok = 0, last_push_error = ?, updated_at = ? WHERE id = ?",
                (error, now_iso(), node_id),
            )
            conn.commit()
        self.refresh_node_status(node_id)

    def update_pull_status(self, node_id: int, ok: bool, error: str | None = None) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE node
                SET last_pull_ok = ?, last_pull_error = ?, last_pull_checked_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (1 if ok else 0, error, now_iso(), now_iso(), node_id),
            )
            conn.commit()
        return self.refresh_node_status(node_id)

    def mark_stale_nodes(self, stale_after_sec: int = 45) -> None:
        cutoff = time.time() - stale_after_sec
        cutoff_iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(cutoff)) + "+00:00"
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT id, last_seen_at FROM node WHERE paired = 1").fetchall()
            for row in rows:
                if row["last_seen_at"] and str(row["last_seen_at"]) < cutoff_iso:
                    conn.execute(
                        "UPDATE node SET last_push_ok = 0, last_push_error = ?, updated_at = ? WHERE id = ?",
                        ("Heartbeat timeout", now_iso(), row["id"]),
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

    def enqueue_job(self, node_id: int, run_id: str, task: str, payload: dict[str, Any]) -> int:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO job (topology_id, node_id, run_id, job_kind, payload_json, status, created_at, available_at)
                VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (self.get_topology_id(), node_id, run_id, task, _dumps(payload), now_iso(), now_iso()),
            )
            job_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            conn.commit()
        return job_id

    def lease_jobs(self, node_id: int, limit: int = 5) -> list[dict[str, Any]]:
        stale_cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 45)) + "+00:00"
        leased_at = now_iso()
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM job
                WHERE node_id = ?
                  AND (
                    status = 'pending'
                    OR (status = 'leased' AND COALESCE(leased_at, '') < ?)
                  )
                ORDER BY id
                LIMIT ?
                """,
                (node_id, stale_cutoff, limit),
            ).fetchall()
            job_ids = [int(row["id"]) for row in rows]
            if job_ids:
                conn.executemany(
                    "UPDATE job SET status = 'leased', leased_at = ? WHERE id = ?",
                    [(leased_at, job_id) for job_id in job_ids],
                )
                conn.commit()
        return [dict(row) for row in rows]

    def complete_job(self, job_id: int, result: dict[str, Any]) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE job
                SET status = 'completed',
                    result_json = ?,
                    completed_at = ?,
                    error = NULL
                WHERE id = ?
                """,
                (_dumps(result), now_iso(), job_id),
            )
            conn.commit()

    def fail_job(self, job_id: int, error: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                UPDATE job
                SET status = 'failed',
                    completed_at = ?,
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
        return run_id

    def has_active_run(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM run WHERE status = 'running' LIMIT 1").fetchone()
        return row is not None

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
                    error = ?, findings_count = ?, conclusion_json = ?
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
                    run_id,
                ),
            )
            if run_result is not None:
                conn.execute("DELETE FROM probe_result WHERE run_id = ?", (run_id,))
                for probe in run_result.probes:
                    row = conn.execute(
                        """
                        INSERT INTO probe_result (
                            run_id, node_id, probe_name, path_label, success, error,
                            metrics_json, metadata_json, started_at, duration_ms
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            run_id,
                            self._node_id_from_role(probe.metadata.get("source_node")),
                            probe.name,
                            probe.metadata.get("path_label"),
                            1 if probe.success else 0,
                            probe.error,
                            _dumps(probe.metrics),
                            _dumps(probe.metadata),
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
                                    node_id, run_id, probe_result_id, probe_name, metric_name, metric_value, captured_at
                                )
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    self._node_id_from_role(probe.metadata.get("source_node")),
                                    run_id,
                                    probe_result_id,
                                    probe.name,
                                    metric_name,
                                    float(metric_value),
                                    finished_at,
                                ),
                            )
                for finding in run_result.threshold_findings:
                    conn.execute(
                        """
                        INSERT INTO alert_event (
                            topology_id, node_id, run_id, kind, severity, status, message, created_at
                        )
                        VALUES (?, ?, ?, 'threshold', ?, 'open', ?, ?)
                        """,
                        (
                            self.get_topology_id(),
                            self._node_id_from_path(finding.path_label),
                            run_id,
                            finding.severity,
                            f"{finding.path_label} {finding.metric} actual={finding.actual} threshold={finding.threshold}",
                            finished_at,
                        ),
                    )
            conn.commit()

    def list_recent_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM run ORDER BY started_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decorate_run(dict(row)) for row in rows]

    def list_recent_alerts(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM alert_event ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]

    def insert_alert(
        self,
        kind: str,
        severity: str,
        status: str,
        message: str,
        node_id: int | None = None,
        run_id: str | None = None,
    ) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO alert_event (topology_id, node_id, run_id, kind, severity, status, message, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.get_topology_id(), node_id, run_id, kind, severity, status, message, now_iso()),
            )
            conn.commit()

    def query_history(
        self,
        node: str | None = None,
        probe_name: str | None = None,
        metric_name: str | None = None,
        time_range_hours: int = 24,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        clauses = ["ms.captured_at >= ?"]
        cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - (time_range_hours * 3600))) + "+00:00"
        params.append(cutoff)
        if node:
            clauses.append("(n.node_name = ? OR CAST(ms.node_id AS TEXT) = ?)")
            params.extend([node, node])
        if probe_name:
            clauses.append("ms.probe_name = ?")
            params.append(probe_name)
        if metric_name:
            clauses.append("ms.metric_name = ?")
            params.append(metric_name)
        params.append(limit)
        sql = f"""
            SELECT ms.*, n.node_name
            FROM metric_sample ms
            LEFT JOIN node n ON n.id = ms.node_id
            WHERE {' AND '.join(clauses)}
            ORDER BY ms.captured_at DESC
            LIMIT ?
        """
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(row) for row in reversed(rows)]

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

    def build_public_dashboard_snapshot(self) -> dict[str, Any]:
        settings = self.get_settings().model_dump()
        nodes = [self._public_node(node) for node in self.list_nodes()]
        runs = [self._public_run(run) for run in self.list_recent_runs(limit=12)]
        alerts = [self._public_alert(alert) for alert in self.list_recent_alerts(limit=12)]
        degraded_statuses = {"push-only", "heartbeat-degraded"}
        offline_statuses = {"offline", "unpaired", "disabled"}
        return {
            "topology_id": self.get_topology_id(),
            "topology_name": settings["topology_name"],
            "summary": {
                "total_nodes": len(nodes),
                "online_nodes": sum(1 for node in nodes if node["status"] == "online"),
                "degraded_nodes": sum(1 for node in nodes if node["status"] in degraded_statuses),
                "offline_nodes": sum(1 for node in nodes if node["status"] in offline_statuses),
                "active_alerts": sum(1 for alert in alerts if alert["status"] == "open"),
            },
            "nodes": nodes,
            "latest_runs": runs,
            "alerts": alerts,
            "history": {
                "samples": self.query_history(metric_name="cpu_usage_pct", time_range_hours=24, limit=180),
            },
        }

    def _public_node(self, node: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": int(node["id"]),
            "role": str(node["role"]),
            "node_name": str(node["node_name"]),
            "status": str(node["status"]),
            "enabled": bool(node["enabled"]),
            "paired": bool(node["paired"]),
            "last_seen_at": node.get("last_seen_at"),
            "last_push_ok": bool(node.get("last_push_ok")),
            "last_pull_ok": bool(node.get("last_pull_ok")),
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
            "kind": str(alert["kind"]),
            "severity": str(alert["severity"]),
            "status": str(alert["status"]),
            "message": str(alert["message"]),
            "created_at": alert.get("created_at"),
        }

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
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
                    status_payload_json TEXT DEFAULT '{}'
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
                    conclusion_json TEXT DEFAULT '[]'
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
                    leased_at TEXT,
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
                    created_at TEXT NOT NULL
                );
                """
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
        push_ok = bool(node.get("last_push_ok"))
        pull_ok = bool(node.get("last_pull_ok"))
        if push_ok and pull_ok:
            return "online"
        if push_ok:
            return "push-only"
        if pull_ok:
            return "heartbeat-degraded"
        return "offline"

    def _decorate_node(self, node: dict[str, Any]) -> dict[str, Any]:
        node["enabled"] = bool(node.get("enabled"))
        node["paired"] = bool(node.get("paired"))
        node["last_push_ok"] = bool(node.get("last_push_ok"))
        node["last_pull_ok"] = bool(node.get("last_pull_ok"))
        node["status_payload"] = _loads(node.get("status_payload_json") or "{}")
        node["status"] = self._classify_node(node)
        return node

    def _decorate_run(self, run: dict[str, Any]) -> dict[str, Any]:
        run["conclusion"] = _loads(run.get("conclusion_json") or "[]")
        return run

    def _node_id_from_role(self, role: Any) -> int | None:
        if not role:
            return None
        node = self.get_node_by_role(str(role))
        return int(node["id"]) if node is not None else None

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


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _loads(value: str | bytes | bytearray | None) -> Any:
    if not value:
        return {}
    return json.loads(value)


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
