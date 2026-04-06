from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from controller.panel_models import NodeUpsertRequest
from controller.panel_store import PanelStore
from probes.common import ProbeResult, RunResult, ThresholdFinding, now_iso


def test_store_migrates_old_schema_and_backfills_path_label(tmp_path: Path) -> None:
    db_path = tmp_path / "monitor.db"
    secret_path = tmp_path / "panel-secret.txt"
    with sqlite3.connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE run (
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
            CREATE TABLE probe_result (
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
            CREATE TABLE metric_sample (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                node_id INTEGER,
                run_id TEXT,
                probe_result_id INTEGER,
                probe_name TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                captured_at TEXT NOT NULL
            );
            CREATE TABLE alert_event (
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
        conn.execute(
            """
            INSERT INTO run (id, topology_id, run_kind, status, source, started_at, findings_count, conclusion_json)
            VALUES ('run-1', 1, 'baseline', 'completed', 'test', ?, 0, '[]')
            """,
            (now_iso(),),
        )
        conn.execute(
            """
            INSERT INTO probe_result (
                id, run_id, node_id, probe_name, path_label, success, error, metrics_json, metadata_json, started_at, duration_ms
            )
            VALUES (1, 'run-1', NULL, 'ping', 'client_to_relay', 1, NULL, '{"rtt_avg_ms": 10.0}', '{}', ?, 1.0)
            """,
            (now_iso(),),
        )
        conn.execute(
            """
            INSERT INTO metric_sample (
                id, node_id, run_id, probe_result_id, probe_name, metric_name, metric_value, captured_at
            )
            VALUES (1, NULL, 'run-1', 1, 'ping', 'rtt_avg_ms', 10.0, ?)
            """,
            (now_iso(),),
        )
        conn.commit()

    PanelStore(db_path=db_path, secret_path=secret_path)

    with sqlite3.connect(db_path) as conn:
        metric_columns = {row[1] for row in conn.execute("PRAGMA table_info(metric_sample)")}
        alert_columns = {row[1] for row in conn.execute("PRAGMA table_info(alert_event)")}
        assert "path_label" in metric_columns
        assert "fingerprint" in alert_columns
        assert "acknowledged_at" in alert_columns
        path_label = conn.execute("SELECT path_label FROM metric_sample WHERE id = 1").fetchone()[0]
        assert path_label == "client_to_relay"


def test_high_side_anomaly_detection_creates_alert(tmp_path: Path) -> None:
    store = build_store(tmp_path)
    for index in range(12):
        persist_metric_run(
            store=store,
            run_id=f"hist-{index}",
            probe_name="ping",
            metric_name="rtt_avg_ms",
            metric_value=10.0 + (index % 2),
            path_label="client_to_relay",
        )

    persist_metric_run(
        store=store,
        run_id="outlier",
        probe_name="ping",
        metric_name="rtt_avg_ms",
        metric_value=220.0,
        path_label="client_to_relay",
    )

    payload = store.query_alert_events(time_range_hours=24, kinds=["anomaly"], anomaly_only=True)
    assert payload["items"]
    assert payload["items"][0]["metric_name"] == "rtt_avg_ms"
    assert payload["items"][0]["path_label"] == "client_to_relay"


def test_low_side_anomaly_detection_creates_alert(tmp_path: Path) -> None:
    store = build_store(tmp_path)
    for index in range(12):
        persist_metric_run(
            store=store,
            run_id=f"hist-low-{index}",
            probe_name="throughput",
            metric_name="throughput_down_mbps",
            metric_value=50.0 + index,
            path_label="client_to_iperf_public",
            probe_source="client",
        )

    persist_metric_run(
        store=store,
        run_id="outlier-low",
        probe_name="throughput",
        metric_name="throughput_down_mbps",
        metric_value=1.0,
        path_label="client_to_iperf_public",
        probe_source="client",
    )

    payload = store.query_alert_events(time_range_hours=24, kinds=["anomaly"], anomaly_only=True)
    assert any(item["metric_name"] == "throughput_down_mbps" for item in payload["items"])


def test_anomaly_requires_minimum_history(tmp_path: Path) -> None:
    store = build_store(tmp_path)
    for index in range(11):
        persist_metric_run(
            store=store,
            run_id=f"hist-short-{index}",
            probe_name="ping",
            metric_name="rtt_avg_ms",
            metric_value=10.0,
            path_label="client_to_relay",
        )

    persist_metric_run(
        store=store,
        run_id="short-outlier",
        probe_name="ping",
        metric_name="rtt_avg_ms",
        metric_value=220.0,
        path_label="client_to_relay",
    )

    payload = store.query_alert_events(time_range_hours=24, kinds=["anomaly"], anomaly_only=True)
    assert payload["items"] == []


def test_silenced_alert_prevents_repeated_anomaly(tmp_path: Path) -> None:
    store = build_store(tmp_path)
    for index in range(12):
        persist_metric_run(
            store=store,
            run_id=f"silence-hist-{index}",
            probe_name="ping",
            metric_name="rtt_avg_ms",
            metric_value=10.0,
            path_label="client_to_relay",
        )

    persist_metric_run(
        store=store,
        run_id="silence-first",
        probe_name="ping",
        metric_name="rtt_avg_ms",
        metric_value=180.0,
        path_label="client_to_relay",
    )
    alerts = store.query_alert_events(time_range_hours=24, kinds=["anomaly"], anomaly_only=True)["items"]
    assert len(alerts) == 1
    store.silence_alert(alert_id=alerts[0]["id"], silenced_until="2099-01-01T00:00:00+00:00", reason="maintenance")

    stale_but_visible = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
    with store._connect() as conn:
        conn.execute("UPDATE alert_event SET created_at = ? WHERE id = ?", (stale_but_visible, alerts[0]["id"]))
        conn.commit()

    persist_metric_run(
        store=store,
        run_id="silence-second",
        probe_name="ping",
        metric_name="rtt_avg_ms",
        metric_value=200.0,
        path_label="client_to_relay",
    )
    alerts = store.query_alert_events(time_range_hours=24, kinds=["anomaly"], anomaly_only=True)["items"]
    assert len(alerts) == 1


def build_store(tmp_path: Path) -> PanelStore:
    store = PanelStore(db_path=tmp_path / "monitor.db", secret_path=tmp_path / "panel-secret.txt")
    store.upsert_node(
        NodeUpsertRequest(
            node_name="client-1",
            role="client",
            runtime_mode="native-windows",
            agent_url="http://client.example:9870",
            enabled=True,
        )
    )
    return store


def persist_metric_run(
    store: PanelStore,
    run_id: str,
    probe_name: str,
    metric_name: str,
    metric_value: float,
    path_label: str,
    probe_source: str = "client",
) -> None:
    created_run_id = store.create_run("baseline", "test")
    probe = ProbeResult(
        name=probe_name,
        source=probe_source,
        target=path_label,
        success=True,
        metrics={metric_name: metric_value},
        samples=[],
        error=None,
        started_at=now_iso(),
        duration_ms=1.0,
        metadata={"path_label": path_label, "source_node": probe_source},
    )
    finding = []
    if metric_name == "rtt_avg_ms" and metric_value > 120:
        finding.append(
            ThresholdFinding(
                path_label=path_label,
                probe_name=probe_name,
                metric=metric_name,
                threshold=120.0,
                actual=metric_value,
                message="threshold exceeded",
            )
        )
    if metric_name == "throughput_down_mbps" and metric_value < 5:
        finding.append(
            ThresholdFinding(
                path_label=path_label,
                probe_name=probe_name,
                metric=metric_name,
                threshold=5.0,
                actual=metric_value,
                message="threshold exceeded",
            )
        )
    result = RunResult(
        run_id=run_id,
        project="mc-netprobe-monitor",
        started_at=now_iso(),
        finished_at=now_iso(),
        environment={"platform": "test"},
        probes=[probe],
        threshold_findings=finding,
        conclusion=[],
    )
    store.finish_run(created_run_id, status="completed", run_result=result)
