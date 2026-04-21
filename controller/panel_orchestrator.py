"""Composite run orchestration over long-lived HTTP agents."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from controller.agent_http_client import AgentHttpClient, AgentHttpError
from controller.orchestrator import (
    build_conclusion,
    build_load_inflation_result,
    evaluate_probe_thresholds,
)
from controller.path_registry import path_family
from controller.panel_store import PanelStore
from exporters.csv_exporter import export_csv
from exporters.html_report import export_html
from exporters.json_exporter import export_json
from probes.common import ProbeResult, RunResult, current_environment, make_error_probe, now_iso


class PanelOrchestrator:
    """Run panel-initiated monitoring flows across paired agents."""

    def __init__(self, store: PanelStore, output_root: str | Path = "results") -> None:
        self.store = store
        self.output_root = Path(output_root)
        self.http = AgentHttpClient(store=store)

    def start_run_in_background(self, run_kind: str, source: str) -> str:
        run_id = self.store.create_run(run_kind=run_kind, source=source)
        worker = threading.Thread(target=self._run_and_persist, args=(run_id, run_kind, source), daemon=True)
        worker.start()
        return run_id

    def run_scheduled_due(self, run_kind: str) -> str | None:
        if self.store.has_active_run():
            return None
        return self.start_run_in_background(run_kind=run_kind, source="schedule")

    def _run_and_persist(self, run_id: str, run_kind: str, source: str) -> None:
        try:
            self.store.record_run_event(run_id, "run_started", f"{run_kind} run started", {"source": source})
            run_result = self.execute_run(run_id=run_id, run_kind=run_kind, source=source)
            output_dir = self.output_root / run_id
            output_dir.mkdir(parents=True, exist_ok=True)
            raw_path = export_json(run_result, output_dir)
            csv_path = export_csv(run_result, output_dir)
            html_path = export_html(run_result, output_dir)
            self.store.finish_run(
                run_id=run_id,
                status="completed",
                run_result=run_result,
                raw_path=str(raw_path),
                csv_path=str(csv_path),
                html_path=str(html_path),
            )
        except Exception as exc:  # pragma: no cover - defensive failure path
            self.store.finish_run(run_id=run_id, status="failed", error=str(exc))
            self.store.insert_alert(kind="run_failed", severity="error", status="open", message=f"{run_kind} failed: {exc}", run_id=run_id)

    def execute_run(self, run_id: str, run_kind: str, source: str) -> RunResult:
        settings = self.store.get_settings()
        nodes = {role: self.store.get_node_by_role(role) for role in ("client", "relay", "server")}
        probes: list[ProbeResult] = []
        findings = []
        started_at = now_iso()

        if run_kind in {"system", "full"}:
            self._run_system(run_id, probes, findings, nodes)
        if run_kind in {"baseline", "full"}:
            self._run_baseline(run_id, probes, findings, settings.model_dump()["services"], nodes)
        if run_kind in {"capacity", "full"}:
            self._run_capacity(run_id, probes, findings, settings.model_dump()["services"], settings.model_dump()["scenarios"], nodes)

        finished_at = now_iso()
        return RunResult(
            run_id=run_id,
            project=settings.topology_name,
            started_at=started_at,
            finished_at=finished_at,
            environment=current_environment() | {"source": source, "run_kind": run_kind},
            probes=probes,
            threshold_findings=findings,
            conclusion=build_conclusion(probes, findings),
        )

    def _run_system(self, run_id: str, probes: list[ProbeResult], findings: list[Any], nodes: dict[str, dict[str, Any] | None]) -> None:
        settings = self.store.get_settings()
        self.store.record_run_event(run_id, "phase_started", "system phase started", {"phase": "system"})
        for role in ("client", "relay", "server"):
            node = self._require_node(nodes, role)
            result = self._dispatch_probe(
                node=node,
                run_id=f"system-{int(time.time() * 1000)}",
                event_run_id=run_id,
                task="system_snapshot",
                payload={
                    "sample_interval_sec": settings.scenarios.system.sample_interval_sec,
                    "process_names": settings.scenarios.system.process_names,
                },
                path_label=f"{role}_system",
            )
            probes.append(result)
            findings.extend(evaluate_probe_thresholds(result, settings.thresholds))
        self.store.record_run_event(run_id, "phase_completed", "system phase completed", {"phase": "system"})

    def _run_baseline(
        self,
        run_id: str,
        probes: list[ProbeResult],
        findings: list[Any],
        services: dict[str, Any],
        nodes: dict[str, dict[str, Any] | None],
    ) -> None:
        settings = self.store.get_settings()
        self.store.record_run_event(run_id, "phase_started", "baseline phase started", {"phase": "baseline"})
        client = self._require_node(nodes, "client")
        relay = self._require_node(nodes, "relay")
        server = self._require_node(nodes, "server")
        relay_target = self._resolve_probe_target(services, "relay_public_probe")
        server_backend_mc = self._resolve_probe_target(services, "server_backend_mc")
        mc_public = self._resolve_probe_target(services, "mc_public")

        if settings.scenarios.ping.enabled:
            for role, host, label in (
                ("client", relay_target["host"], "client_to_relay_public"),
                ("server", relay_target["host"], "server_to_relay_public"),
            ):
                node = self._require_node(nodes, role)
                probe = self._dispatch_probe(
                    node=node,
                    run_id=f"ping-{role}-{int(time.time() * 1000)}",
                    event_run_id=run_id,
                    task="ping",
                    payload={
                        "host": host,
                        "count": settings.scenarios.ping.count,
                        "timeout_sec": settings.scenarios.ping.timeout_sec,
                    },
                    path_label=label,
                    target_ref="relay_public_probe",
                )
                probes.append(probe)
                findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))

        if settings.scenarios.tcp.enabled:
            tcp_jobs = (
                (
                    client,
                    "tcp_probe",
                    {
                        "host": relay_target["host"],
                        "port": relay_target["port"],
                        "attempts": settings.scenarios.tcp.attempts,
                        "interval_ms": settings.scenarios.tcp.interval_ms,
                        "timeout_ms": settings.scenarios.tcp.timeout_ms,
                        "concurrency": settings.scenarios.tcp.concurrency,
                    },
                    "client_to_relay_public",
                    "relay_public_probe",
                ),
                (
                    relay,
                    "tcp_probe",
                    {
                        "host": server_backend_mc["host"],
                        "port": server_backend_mc["port"],
                        "attempts": settings.scenarios.tcp.attempts,
                        "interval_ms": settings.scenarios.tcp.interval_ms,
                        "timeout_ms": settings.scenarios.tcp.timeout_ms,
                        "concurrency": settings.scenarios.tcp.concurrency,
                    },
                    "relay_to_server_backend_mc",
                    "server_backend_mc",
                ),
                (
                    client,
                    "mc_tcp_probe",
                    {
                        "host": mc_public["host"],
                        "port": mc_public["port"],
                        "attempts": settings.scenarios.tcp.attempts,
                        "interval_ms": settings.scenarios.tcp.interval_ms,
                        "timeout_ms": settings.scenarios.tcp.timeout_ms,
                        "concurrency": settings.scenarios.tcp.concurrency,
                    },
                    "client_to_mc_public",
                    "mc_public",
                ),
                (
                    server,
                    "tcp_probe",
                    {
                        "host": relay_target["host"],
                        "port": relay_target["port"],
                        "attempts": settings.scenarios.tcp.attempts,
                        "interval_ms": settings.scenarios.tcp.interval_ms,
                        "timeout_ms": settings.scenarios.tcp.timeout_ms,
                        "concurrency": settings.scenarios.tcp.concurrency,
                    },
                    "server_to_relay_public",
                    "relay_public_probe",
                ),
            )
            for node, task, payload, label, target_ref in tcp_jobs:
                probe = self._dispatch_probe(
                    node=node,
                    run_id=f"{task}-{int(time.time() * 1000)}",
                    event_run_id=run_id,
                    task=task,
                    payload=payload,
                    path_label=label,
                    target_ref=target_ref,
                )
                probes.append(probe)
                findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))
        self.store.record_run_event(run_id, "phase_completed", "baseline phase completed", {"phase": "baseline"})

    def _run_capacity(
        self,
        run_id: str,
        probes: list[ProbeResult],
        findings: list[Any],
        services: dict[str, Any],
        scenarios: dict[str, Any],
        nodes: dict[str, dict[str, Any] | None],
    ) -> None:
        settings = self.store.get_settings()
        self.store.record_run_event(run_id, "phase_started", "capacity phase started", {"phase": "capacity"})
        client = self._require_node(nodes, "client")
        relay = self._require_node(nodes, "relay")
        server = self._require_node(nodes, "server")
        server_backend_iperf = self._resolve_probe_target(services, "server_backend_iperf")
        iperf_public = self._resolve_probe_target(services, "iperf_public")
        mc_public = self._resolve_probe_target(services, "mc_public")

        if settings.scenarios.throughput.enabled:
            for reverse in (False, True):
                self._start_iperf_server(
                    run_id,
                    server,
                    services,
                    probes,
                    findings,
                    "relay_to_server_backend_iperf",
                    settings,
                    target_ref="server_backend_iperf",
                )
                probe = self._dispatch_probe(
                    node=relay,
                    run_id=f"relay-throughput-{int(time.time() * 1000)}",
                    event_run_id=run_id,
                    task="throughput",
                    payload={
                        "host": server_backend_iperf["host"],
                        "port": server_backend_iperf["port"],
                        "duration_sec": settings.scenarios.throughput.duration_sec,
                        "parallel_streams": settings.scenarios.throughput.parallel_streams,
                        "timeout_sec": settings.scenarios.throughput.timeout_sec,
                        "reverse": reverse,
                    },
                    path_label="relay_to_server_backend_iperf",
                    target_ref="server_backend_iperf",
                )
                probes.append(probe)
                findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))

            for reverse in (False, True):
                self._start_iperf_server(
                    run_id,
                    server,
                    services,
                    probes,
                    findings,
                    "client_to_iperf_public",
                    settings,
                    target_ref="iperf_public",
                )
                probe = self._dispatch_probe(
                    node=client,
                    run_id=f"client-throughput-{int(time.time() * 1000)}",
                    event_run_id=run_id,
                    task="throughput",
                    payload={
                        "host": iperf_public["host"],
                        "port": iperf_public["port"],
                        "duration_sec": settings.scenarios.throughput.duration_sec,
                        "parallel_streams": settings.scenarios.throughput.parallel_streams,
                        "timeout_sec": settings.scenarios.throughput.timeout_sec,
                        "reverse": reverse,
                    },
                    path_label="client_to_iperf_public",
                    target_ref="iperf_public",
                )
                probes.append(probe)
                findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))

        if settings.scenarios.load_inflation.enabled:
            idle_probe = self._dispatch_probe(
                node=client,
                run_id=f"idle-{int(time.time() * 1000)}",
                event_run_id=run_id,
                task="mc_tcp_probe",
                payload={
                    "host": mc_public["host"],
                    "port": mc_public["port"],
                    "attempts": settings.scenarios.load_inflation.baseline_attempts,
                    "interval_ms": settings.scenarios.load_inflation.probe_interval_ms,
                    "timeout_ms": settings.scenarios.load_inflation.timeout_ms,
                    "concurrency": 1,
                },
                path_label="client_to_mc_public_load_idle",
                target_ref="mc_public",
            )
            idle_probe.name = "mc_tcp_connect_idle"
            probes.append(idle_probe)
            findings.extend(evaluate_probe_thresholds(idle_probe, settings.thresholds))

            self._start_iperf_server(
                run_id,
                server,
                services,
                probes,
                findings,
                "client_to_iperf_public_load",
                settings,
                target_ref="iperf_public",
            )
            throughput_probe = self._dispatch_probe(
                node=client,
                run_id=f"load-throughput-{int(time.time() * 1000)}",
                event_run_id=run_id,
                task="throughput",
                payload={
                    "host": iperf_public["host"],
                    "port": iperf_public["port"],
                    "duration_sec": settings.scenarios.load_inflation.duration_sec,
                    "parallel_streams": settings.scenarios.throughput.parallel_streams,
                    "timeout_sec": settings.scenarios.throughput.timeout_sec,
                },
                path_label="client_to_iperf_public_load",
                target_ref="iperf_public",
            )
            loaded_attempts = max(
                1,
                int(
                    (settings.scenarios.load_inflation.duration_sec * 1000)
                    / max(1, settings.scenarios.load_inflation.probe_interval_ms)
                ),
            )
            loaded_probe = self._dispatch_probe(
                node=client,
                run_id=f"loaded-{int(time.time() * 1000)}",
                event_run_id=run_id,
                task="mc_tcp_probe",
                payload={
                    "host": mc_public["host"],
                    "port": mc_public["port"],
                    "attempts": loaded_attempts,
                    "interval_ms": settings.scenarios.load_inflation.probe_interval_ms,
                    "timeout_ms": settings.scenarios.load_inflation.timeout_ms,
                    "concurrency": 1,
                },
                path_label="client_to_mc_public_load_loaded",
                target_ref="mc_public",
            )
            loaded_probe.name = "mc_tcp_connect_loaded"
            probes.append(throughput_probe)
            findings.extend(evaluate_probe_thresholds(throughput_probe, settings.thresholds))
            probes.append(loaded_probe)
            findings.extend(evaluate_probe_thresholds(loaded_probe, settings.thresholds))

            load_result = build_load_inflation_result(idle_probe=idle_probe, loaded_probe=loaded_probe, throughput_result=throughput_probe)
            load_result.metadata["path_label"] = "client_to_mc_public_load"
            probes.append(load_result)
            findings.extend(evaluate_probe_thresholds(load_result, settings.thresholds))
        self.store.record_run_event(run_id, "phase_completed", "capacity phase completed", {"phase": "capacity"})

    def _start_iperf_server(
        self,
        run_id: str,
        server: dict[str, Any],
        services: dict[str, Any],
        probes: list[ProbeResult],
        findings: list[Any],
        path_label: str,
        settings: Any,
        target_ref: str,
    ) -> None:
        target = self._resolve_probe_target(services, target_ref)
        probe = self._dispatch_probe(
            node=server,
            run_id=f"iperf-server-{int(time.time() * 1000)}",
            event_run_id=run_id,
            task="start_iperf_server",
            payload={
                "port": target["port"],
                "bind_host": target["host"],
                "one_off": True,
            },
            path_label=path_label,
            target_ref=target_ref,
        )
        probes.append(probe)
        findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))
        time.sleep(0.3)

    def _dispatch_probe(
        self,
        node: dict[str, Any],
        run_id: str,
        task: str,
        payload: dict[str, Any],
        path_label: str,
        event_run_id: str | None = None,
        target_ref: str | None = None,
    ) -> ProbeResult:
        action_run_id = event_run_id or run_id
        timeout_sec = self._timeout_for_task(task, payload)
        payload = dict(payload)
        payload.setdefault("source", node["role"])
        payload.setdefault("platform_name", self._platform_for_runtime(node["runtime_mode"]))
        can_pull = self._node_can_pull(node)
        can_queue = self._node_can_queue(node)
        self.store.record_run_event(
            action_run_id,
            "probe_dispatched",
            f"{task} dispatched to {node['node_name']}",
            {"task": task, "node_name": node["node_name"], "path_label": path_label, "can_pull": can_pull, "can_queue": can_queue},
        )

        if can_pull:
            try:
                response = self.http.run_job(node=node, job_id=None, run_id=run_id, task=task, payload=payload)
                self.store.update_pull_status(int(node["id"]), ok=True)
                result = ProbeResult.from_dict(response["result"])
                transport = "pull"
            except Exception as exc:
                error_code = self._error_code_from_exception(exc)
                self.store.update_pull_status(int(node["id"]), ok=False, error=str(exc), error_code=error_code)
                self.store.record_run_event(
                    action_run_id,
                    "probe_transport_error",
                    f"{task} pull dispatch failed on {node['node_name']}",
                    {
                        "task": task,
                        "node_name": node["node_name"],
                        "path_label": path_label,
                        "transport": "pull",
                        "error": str(exc),
                        "error_code": error_code,
                        "fallback_available": can_queue,
                    },
                )
                if can_queue:
                    result = self._dispatch_via_queue(
                        node=node,
                        run_id=run_id,
                        task=task,
                        payload=payload,
                        timeout_sec=timeout_sec,
                        event_run_id=action_run_id,
                        path_label=path_label,
                        target_ref=target_ref,
                    )
                    result.metadata.setdefault("fallback_from_transport", "pull")
                    result.metadata.setdefault("fallback_from_code", error_code)
                    transport = "queue-fallback"
                else:
                    result = make_error_probe(
                        name=task,
                        source=node["role"],
                        target=str(payload.get("host", node["node_name"])),
                        error=str(exc),
                        metadata={"error_code": error_code, "transport": "pull-error"},
                    )
                    transport = "pull-error"
        elif can_queue:
            self.store.reset_pull_status(int(node["id"]))
            result = self._dispatch_via_queue(
                node=node,
                run_id=run_id,
                task=task,
                payload=payload,
                timeout_sec=timeout_sec,
                event_run_id=action_run_id,
                path_label=path_label,
                target_ref=target_ref,
            )
            transport = "queue"
        else:
            self.store.reset_pull_status(int(node["id"]))
            result = make_error_probe(
                name=task,
                source=node["role"],
                target=str(payload.get("host", node["node_name"])),
                error=f"{node['node_name']} is not reachable through pull or push mode",
                metadata={"error_code": "transport_unavailable", "transport": "unavailable"},
            )
            transport = "unavailable"

        result.metadata.setdefault("path_label", path_label)
        result.metadata.setdefault("path_id", path_label)
        result.metadata.setdefault("path_family", path_family(path_label))
        if target_ref:
            result.metadata.setdefault("target_ref", target_ref)
            result.metadata.setdefault("target_scope", "public" if path_family(path_label) == "public" else "backend")
        result.metadata.setdefault("source_node", node["role"])
        result.metadata.setdefault("node_runtime_mode", node["runtime_mode"])
        result.metadata.setdefault("transport", transport)
        self.store.record_run_event(
            action_run_id,
            "probe_completed",
            f"{task} completed on {node['node_name']} via {transport}",
            {
                "task": task,
                "node_name": node["node_name"],
                "path_label": path_label,
                "path_family": result.metadata.get("path_family"),
                "transport": transport,
                "success": result.success,
                "error": result.error,
                "error_code": result.metadata.get("error_code"),
                "fallback_from_code": result.metadata.get("fallback_from_code"),
            },
        )
        return result

    def _dispatch_via_queue(
        self,
        node: dict[str, Any],
        run_id: str,
        task: str,
        payload: dict[str, Any],
        timeout_sec: float,
        event_run_id: str | None = None,
        path_label: str | None = None,
        target_ref: str | None = None,
    ) -> ProbeResult:
        action_run_id = event_run_id or run_id
        if not self._node_can_queue(node):
            return make_error_probe(
                name=task,
                source=node["role"],
                target=str(payload.get("host", node["node_name"])),
                error=f"{node['node_name']} is not reachable through pull or push mode",
                metadata={"error_code": "transport_unavailable", "transport": "queue"},
            )
        job_id = self.store.enqueue_job(node_id=int(node["id"]), run_id=run_id, task=task, payload=payload, timeout_sec=timeout_sec)
        job_snapshot = self.store.get_job_snapshot(job_id)
        self.store.record_run_event(
            action_run_id,
            "queue_enqueued",
            f"{task} queued for {node['node_name']}",
            {
                "job_id": job_id,
                "task": task,
                "node_name": node["node_name"],
                "path_label": path_label,
                "timeout_sec": timeout_sec,
                "queue_status": "pending",
                "job": job_snapshot or {"job_id": job_id, "task": task, "status": "pending", "timeout_sec": timeout_sec},
            },
        )
        try:
            job = self.store.wait_for_job(job_id=job_id, timeout_sec=timeout_sec)
        except TimeoutError as exc:
            job_snapshot = self.store.get_job_snapshot(job_id)
            error_code = self._queue_timeout_code(job_snapshot)
            self.store.record_run_event(
                action_run_id,
                "queue_timeout",
                f"{task} queued job timed out on {node['node_name']}",
                {
                    "job_id": job_id,
                    "task": task,
                    "node_name": node["node_name"],
                    "path_label": path_label,
                    "timeout_sec": timeout_sec,
                    "queue_status": job_snapshot.get("status") if isinstance(job_snapshot, dict) else "timeout",
                    "job": job_snapshot,
                    "error": str(exc),
                    "error_code": error_code,
                },
            )
            self.store.fail_job(job_id=job_id, error=str(exc))
            return make_error_probe(
                name=task,
                source=node["role"],
                target=str(payload.get("host", node["node_name"])),
                error=str(exc),
                metadata={"error_code": error_code, "transport": "queue", "job": job_snapshot},
            )
        if job["status"] != "completed":
            job_snapshot = self.store.get_job_snapshot(job_id)
            self.store.record_run_event(
                action_run_id,
                "queue_failed",
                f"{task} queued job failed on {node['node_name']}",
                {
                    "job_id": job_id,
                    "task": task,
                    "node_name": node["node_name"],
                    "path_label": path_label,
                    "timeout_sec": timeout_sec,
                    "queue_status": job.get("status"),
                    "job": job_snapshot,
                    "error": job.get("error") or f"Queued job {job_id} failed",
                    "error_code": "queue_failed",
                },
            )
            return make_error_probe(
                name=task,
                source=node["role"],
                target=str(payload.get("host", node["node_name"])),
                error=job.get("error") or f"Queued job {job_id} failed",
                metadata={"error_code": "queue_failed", "transport": "queue", "job": job_snapshot},
            )
        result = ProbeResult.from_dict(json.loads(job["result_json"]))
        result.metadata.setdefault("transport", "queue")
        result.metadata.setdefault("job_id", job_id)
        if path_label:
            result.metadata.setdefault("path_label", path_label)
            result.metadata.setdefault("path_id", path_label)
            result.metadata.setdefault("path_family", path_family(path_label))
        if target_ref:
            result.metadata.setdefault("target_ref", target_ref)
            result.metadata.setdefault("target_scope", "public" if path_family(path_label) == "public" else "backend")
        return result

    def _require_node(self, nodes: dict[str, dict[str, Any] | None], role: str) -> dict[str, Any]:
        node = nodes.get(role)
        if node is None:
            raise ValueError(f"Node for role {role} has not been configured")
        if not node["enabled"]:
            raise ValueError(f"Node {node['node_name']} is disabled")
        if not node["paired"]:
            raise ValueError(f"Node {node['node_name']} is not paired yet")
        return node

    def _resolve_probe_target(self, services: dict[str, Any], target_ref: str) -> dict[str, Any]:
        target = services.get(target_ref) or {}
        host = str(target.get("host") or "").strip()
        if not host:
            raise ValueError(f"Service target '{target_ref}' is not configured")
        return {"host": host, "port": int(target["port"])}

    def _agent_host(self, node: dict[str, Any]) -> str:
        effective_pull_url = node.get("endpoints", {}).get("effective_pull_url")
        if effective_pull_url:
            parsed = urlparse(str(effective_pull_url))
            if parsed.hostname:
                return parsed.hostname
        raise ValueError(f"Node {node['node_name']} does not have a usable agent URL host")

    def _node_can_pull(self, node: dict[str, Any]) -> bool:
        return bool(node.get("endpoints", {}).get("effective_pull_url")) and bool(node.get("capabilities", {}).get("pull_http", True))

    def _node_can_queue(self, node: dict[str, Any]) -> bool:
        return bool(node.get("capabilities", {}).get("heartbeat_queue", True)) and node.get("connectivity", {}).get("push", {}).get("state") == "ok"

    def _platform_for_runtime(self, runtime_mode: str) -> str:
        if runtime_mode == "native-windows":
            return "windows"
        if runtime_mode == "native-macos":
            return "macos"
        return "linux"

    def _timeout_for_task(self, task: str, payload: dict[str, Any]) -> float:
        if task == "ping":
            return float(payload.get("timeout_sec", 10.0)) + 5.0
        if task in {"tcp_probe", "mc_tcp_probe"}:
            attempts = int(payload.get("attempts", 3))
            timeout_ms = int(payload.get("timeout_ms", 3000))
            interval_ms = int(payload.get("interval_ms", 250))
            return max(5.0, ((attempts * (timeout_ms + interval_ms)) / 1000.0) + 5.0)
        if task == "throughput":
            return float(payload.get("duration_sec", 10)) + float(payload.get("timeout_sec", 20.0)) + 5.0
        if task == "system_snapshot":
            return float(payload.get("sample_interval_sec", 1.0)) + 5.0
        return 10.0

    def _error_code_from_exception(self, exc: Exception) -> str:
        if isinstance(exc, AgentHttpError):
            return exc.code
        if isinstance(exc, TimeoutError):
            return "timeout"
        return "pull_request_failed"

    def _queue_timeout_code(self, job_snapshot: dict[str, Any] | None) -> str:
        if not isinstance(job_snapshot, dict):
            return "queue_timeout"
        status = str(job_snapshot.get("status") or "")
        if status == "pending":
            return "queue_not_leased"
        if status == "leased":
            if job_snapshot.get("lease_expired"):
                return "queue_lease_expired"
            return "queue_lease_timeout"
        return "queue_timeout"
