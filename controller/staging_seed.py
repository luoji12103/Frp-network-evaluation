"""Helpers for isolated staging panel fixtures and simulated-agent pairing data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from controller.panel_models import AgentCapabilities, AgentEndpointReport, AgentIdentity, AgentRuntimeStatus, NodeUpsertRequest
from controller.panel_store import PanelStore
from probes.common import RunResult, now_iso


SIM_NODE_SPECS = [
    {
        "env_prefix": "CLIENT_SIM",
        "node_name": "client-sim",
        "role": "client",
        "runtime_mode": "native-windows",
        "platform_name": "windows",
        "configured_pull_url": "http://client-sim:9870",
        "advertise_url": "http://client-sim:9870",
        "control_url": "http://client-sim-control-bridge:9871",
    },
    {
        "env_prefix": "RELAY_SIM",
        "node_name": "relay-sim",
        "role": "relay",
        "runtime_mode": "docker-linux",
        "platform_name": "linux",
        "configured_pull_url": "http://relay-sim:9870",
        "advertise_url": "http://relay-sim-advertised:9870",
        "control_url": "http://relay-sim-control-bridge:9871",
    },
    {
        "env_prefix": "SERVER_SIM",
        "node_name": "server-sim",
        "role": "server",
        "runtime_mode": "native-macos",
        "platform_name": "macos",
        "configured_pull_url": "http://server-sim:9870",
        "advertise_url": "http://server-sim:9870",
        "control_url": "http://server-sim-control-bridge:9871",
    },
]

FIXTURE_NODE_SPECS = [
    {
        "node_name": "client-push-only-fixture",
        "role": "client",
        "runtime_mode": "native-windows",
        "platform_name": "windows",
        "configured_pull_url": "http://push-only-fixture:9870",
        "advertise_url": "http://push-only-fixture:9870",
        "control_url": None,
        "pull_ok": False,
        "pull_error": "request to http://push-only-fixture:9870/api/v1/status timed out",
        "pull_error_code": "timeout",
    },
    {
        "node_name": "relay-legacy-fixture",
        "role": "relay",
        "runtime_mode": "docker-linux",
        "platform_name": "linux",
        "configured_pull_url": "http://legacy-status-fixture:9880",
        "advertise_url": "http://legacy-status-fixture:9880",
        "control_url": None,
        "pull_ok": False,
        "pull_error": "legacy /api/v1/status payload",
        "pull_error_code": "legacy_status_shape",
    },
    {
        "node_name": "server-protocol-fixture",
        "role": "server",
        "runtime_mode": "native-macos",
        "platform_name": "macos",
        "configured_pull_url": "http://protocol-status-fixture:9881",
        "advertise_url": "http://protocol-status-fixture:9881",
        "control_url": None,
        "pull_ok": False,
        "pull_error": "Unsupported agent protocol_version '999'; expected 1",
        "pull_error_code": "protocol_mismatch",
    },
]


def seed_staging_snapshot(
    *,
    db_path: str | Path,
    env_path: str | Path | None = None,
    include_active_blocker: bool = False,
) -> dict[str, Any]:
    store = PanelStore(db_path=db_path)
    created_at = now_iso()

    sim_payload = _prepare_sim_nodes(store=store)
    fixture_nodes = _prepare_fixture_nodes(store=store)
    alerts_payload = _seed_alerts(store=store, created_at=created_at)
    actions_payload = _seed_actions(store=store)
    runs_payload = _seed_runs(store=store, include_active_blocker=include_active_blocker)

    payload = {
        "generated_at": created_at,
        "sim_nodes": sim_payload,
        "fixtures": {
            "nodes": [item["node_name"] for item in fixture_nodes],
            "alerts": alerts_payload,
            "actions": actions_payload,
            "runs": runs_payload,
        },
    }
    if env_path is not None:
        _write_env_file(path=Path(env_path), payload=payload)
    return payload


def _prepare_sim_nodes(store: PanelStore) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for spec in SIM_NODE_SPECS:
        node = store.upsert_node(
            NodeUpsertRequest(
                node_name=spec["node_name"],
                role=spec["role"],  # type: ignore[arg-type]
                runtime_mode=spec["runtime_mode"],  # type: ignore[arg-type]
                configured_pull_url=spec["configured_pull_url"],
                enabled=True,
            )
        )
        pair_code, expires_at = store.create_pair_code(int(node["id"]))
        payload.append(
            {
                "node_id": int(node["id"]),
                "node_name": spec["node_name"],
                "role": spec["role"],
                "runtime_mode": spec["runtime_mode"],
                "platform_name": spec["platform_name"],
                "pair_code": pair_code,
                "pair_code_expires_at": expires_at,
                "configured_pull_url": spec["configured_pull_url"],
                "advertise_url": spec["advertise_url"],
                "control_url": spec["control_url"],
                "env_prefix": spec["env_prefix"],
            }
        )
    return payload


def _prepare_fixture_nodes(store: PanelStore) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for spec in FIXTURE_NODE_SPECS:
        node = store.upsert_node(
            NodeUpsertRequest(
                node_name=spec["node_name"],
                role=spec["role"],  # type: ignore[arg-type]
                runtime_mode=spec["runtime_mode"],  # type: ignore[arg-type]
                configured_pull_url=spec["configured_pull_url"],
                enabled=True,
            )
        )
        pair_code, _ = store.create_pair_code(int(node["id"]))
        store.pair_agent(
            identity=AgentIdentity(
                node_name=spec["node_name"],
                role=spec["role"],  # type: ignore[arg-type]
                runtime_mode=spec["runtime_mode"],  # type: ignore[arg-type]
                protocol_version="1",
                platform_name=spec["platform_name"],
                hostname=f"{spec['node_name']}-fixture",
                agent_version="fixture",
            ),
            pair_code=pair_code,
            endpoint=AgentEndpointReport(
                listen_host="0.0.0.0",
                listen_port=9870,
                advertise_url=spec["advertise_url"],
                control_url=spec["control_url"],
            ),
            capabilities=AgentCapabilities(pull_http=True, heartbeat_queue=False, result_lookup=False),
        )
        store.record_heartbeat(
            node_id=int(node["id"]),
            endpoint=AgentEndpointReport(
                listen_host="0.0.0.0",
                listen_port=9870,
                advertise_url=spec["advertise_url"],
                control_url=spec["control_url"],
            ),
            runtime_status=AgentRuntimeStatus(
                paired=True,
                started_at=now_iso(),
                last_heartbeat_at=now_iso(),
                last_error=None,
                environment={"platform_name": spec["platform_name"], "fixture": True},
            ),
        )
        store.update_pull_status(
            int(node["id"]),
            ok=bool(spec["pull_ok"]),
            error=spec["pull_error"],
            error_code=spec["pull_error_code"],
        )
        payload.append(store.get_node(int(node["id"])) or {"node_name": spec["node_name"]})

    disabled = store.upsert_node(
        NodeUpsertRequest(
            node_name="server-disabled-fixture",
            role="server",
            runtime_mode="native-macos",
            configured_pull_url="http://server-disabled-fixture:9870",
            enabled=False,
        )
    )
    payload.append(disabled)
    return payload


def _seed_alerts(store: PanelStore, created_at: str) -> dict[str, int]:
    fingerprint = "staging-alert-fingerprint"
    store.insert_alert(
        kind="threshold",
        severity="warning",
        status="open",
        message="client_to_mc_public connect_avg_ms actual=240 threshold=150",
        path_label="client_to_mc_public",
        probe_name="tcp_handshake",
        metric_name="connect_avg_ms",
        actual_value=240.0,
        threshold_value=150.0,
        fingerprint=fingerprint,
    )
    store.insert_alert(
        kind="anomaly",
        severity="warning",
        status="acknowledged",
        message="relay_to_server_backend_mc packet_loss_pct anomaly acknowledged",
        path_label="relay_to_server_backend_mc",
        probe_name="ping",
        metric_name="packet_loss_pct",
        actual_value=12.0,
        threshold_value=2.0,
        fingerprint="staging-ack-fingerprint",
        acknowledged_at=created_at,
        acknowledged_by="staging-seed",
    )
    store.insert_alert(
        kind="threshold",
        severity="error",
        status="acknowledged",
        message="client_to_relay_public rtt_avg_ms silenced for staging",
        path_label="client_to_relay_public",
        probe_name="ping",
        metric_name="rtt_avg_ms",
        actual_value=210.0,
        threshold_value=120.0,
        fingerprint=fingerprint,
        acknowledged_at=created_at,
        acknowledged_by="staging-seed",
        silenced_until="2099-01-01T00:00:00+00:00",
        silence_reason="staging validation fixture",
    )
    summary = store.query_alert_events(time_range_hours=24 * 365, limit=50)["summary"]
    return {key: int(value) for key, value in summary.items()}


def _seed_actions(store: PanelStore) -> dict[str, int]:
    node = store.get_node_by_name("relay-legacy-fixture")
    if node is None:
        return {"total": 0, "active": 0}
    completed = store.create_control_action(
        target_kind="node",
        target_id=int(node["id"]),
        action="sync_runtime",
        requested_by="staging-seed",
        confirmation_required=False,
        audit_payload={"request": {"action": "sync_runtime"}, "target_name": node["node_name"]},
    )
    store.start_control_action(int(completed["id"]), transport="fixture")
    store.finish_control_action(
        int(completed["id"]),
        status="completed",
        result_summary="Fixture runtime sync completed",
        transport="fixture",
        audit_payload={"response": {"runtime": {"state": "running"}, "supervisor": {"control_available": False}}},
    )
    failed = store.create_control_action(
        target_kind="node",
        target_id=int(node["id"]),
        action="tail_log",
        requested_by="staging-seed",
        confirmation_required=False,
        audit_payload={"request": {"action": "tail_log"}, "target_name": node["node_name"]},
    )
    store.start_control_action(int(failed["id"]), transport="fixture")
    store.finish_control_action(
        int(failed["id"]),
        status="failed",
        error_code="bridge_unavailable",
        error_detail="Fixture bridge unavailable",
        transport="fixture",
    )
    store.create_control_action(
        target_kind="node",
        target_id=int(node["id"]),
        action="restart",
        requested_by="staging-seed",
        confirmation_required=True,
        audit_payload={"request": {"action": "restart"}, "target_name": node["node_name"]},
    )
    items = store.list_control_actions(limit=20)
    return {"total": len(items), "active": sum(1 for item in items if item.get("active"))}


def _seed_runs(store: PanelStore, include_active_blocker: bool) -> dict[str, Any]:
    completed_run_id = store.create_run("baseline", "staging-seed")
    store.record_run_event(completed_run_id, "phase_started", "baseline phase started", {"phase": "baseline"})
    store.record_run_event(
        completed_run_id,
        "queue_timeout",
        "ping queued job timed out on relay-legacy-fixture",
        {
            "job_id": 42,
            "task": "ping",
            "node_name": "relay-legacy-fixture",
            "queue_status": "pending",
            "error": "Timed out waiting for job 42",
            "error_code": "queue_not_leased",
            "job": {"job_id": 42, "task": "ping", "status": "pending", "lease_state": "not-leased"},
        },
    )
    store.record_run_event(
        completed_run_id,
        "probe_completed",
        "ping completed on relay-legacy-fixture via pull",
        {
            "task": "ping",
            "node_name": "relay-legacy-fixture",
            "path_label": "client_to_relay_public",
            "transport": "pull",
            "success": True,
            "error": None,
        },
    )
    store.finish_run(completed_run_id, status="completed", run_result=_empty_run_result(completed_run_id))

    active_run_id: str | None = None
    if include_active_blocker:
        active_run_id = store.create_run("full", "staging-seed")
        store.record_run_event(active_run_id, "phase_started", "full phase started", {"phase": "full"})
        store.record_run_event(
            active_run_id,
            "queue_timeout",
            "throughput queued job timed out on client-push-only-fixture",
            {
                "job_id": 77,
                "task": "throughput",
                "node_name": "client-push-only-fixture",
                "queue_status": "pending",
                "error": "Timed out waiting for job 77",
                "error_code": "queue_not_leased",
                "job": {"job_id": 77, "task": "throughput", "status": "pending", "lease_state": "not-leased"},
            },
        )

    return {
        "completed_run_id": completed_run_id,
        "active_run_id": active_run_id,
    }


def _empty_run_result(run_id: str) -> RunResult:
    current = now_iso()
    return RunResult(
        run_id=run_id,
        project="mc-netprobe-monitor",
        started_at=current,
        finished_at=current,
        environment={"fixture": "staging-seed"},
        probes=[],
        threshold_findings=[],
        conclusion=["staging seed completed"],
    )


def _write_env_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            existing[key.strip()] = value.strip()

    updates = dict(existing)
    for item in payload.get("sim_nodes") or []:
        prefix = str(item["env_prefix"])
        updates[f"{prefix}_PAIR_CODE"] = str(item["pair_code"])
        updates[f"{prefix}_NODE_NAME"] = str(item["node_name"])
        updates[f"{prefix}_ROLE"] = str(item["role"])
        updates[f"{prefix}_RUNTIME_MODE"] = str(item["runtime_mode"])
        updates[f"{prefix}_PLATFORM_NAME"] = str(item["platform_name"])
        updates[f"{prefix}_CONFIGURED_PULL_URL"] = str(item["configured_pull_url"])
        updates[f"{prefix}_ADVERTISE_URL"] = str(item["advertise_url"])
        updates[f"{prefix}_CONTROL_URL"] = str(item["control_url"] or "")
    updates["STAGING_SEED_SUMMARY_JSON"] = json.dumps(payload["fixtures"], separators=(",", ":"), ensure_ascii=False)
    path.write_text("\n".join(f"{key}={value}" for key, value in sorted(updates.items())) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed isolated staging fixtures for the panel")
    parser.add_argument("--db-path", default="data/monitor.db")
    parser.add_argument("--env-path")
    parser.add_argument("--include-active-blocker", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = seed_staging_snapshot(
        db_path=args.db_path,
        env_path=args.env_path,
        include_active_blocker=args.include_active_blocker,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
