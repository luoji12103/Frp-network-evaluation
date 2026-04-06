"""Composite run orchestration over long-lived HTTP agents."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from controller.agent_http_client import AgentHttpClient
from controller.orchestrator import (
    build_conclusion,
    build_load_inflation_result,
    evaluate_probe_thresholds,
)
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
            self._run_system(probes, findings, nodes)
        if run_kind in {"baseline", "full"}:
            self._run_baseline(probes, findings, settings.model_dump()["services"], nodes)
        if run_kind in {"capacity", "full"}:
            self._run_capacity(probes, findings, settings.model_dump()["services"], settings.model_dump()["scenarios"], nodes)

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

    def _run_system(self, probes: list[ProbeResult], findings: list[Any], nodes: dict[str, dict[str, Any] | None]) -> None:
        settings = self.store.get_settings()
        for role in ("client", "relay", "server"):
            node = self._require_node(nodes, role)
            result = self._dispatch_probe(
                node=node,
                run_id=f"system-{int(time.time() * 1000)}",
                task="system_snapshot",
                payload={
                    "sample_interval_sec": settings.scenarios.system.sample_interval_sec,
                    "process_names": settings.scenarios.system.process_names,
                },
                path_label=f"{role}_system",
            )
            probes.append(result)
            findings.extend(evaluate_probe_thresholds(result, settings.thresholds))

    def _run_baseline(
        self,
        probes: list[ProbeResult],
        findings: list[Any],
        services: dict[str, Any],
        nodes: dict[str, dict[str, Any] | None],
    ) -> None:
        settings = self.store.get_settings()
        client = self._require_node(nodes, "client")
        relay = self._require_node(nodes, "relay")
        server = self._require_node(nodes, "server")
        relay_host = str(services["relay_probe"]["host"] or self._agent_host(relay))
        server_host = self._agent_host(server)

        if settings.scenarios.ping.enabled:
            for role, host, label in (
                ("client", relay_host, "client_to_relay"),
                ("relay", server_host, "relay_to_server"),
            ):
                node = self._require_node(nodes, role)
                probe = self._dispatch_probe(
                    node=node,
                    run_id=f"ping-{role}-{int(time.time() * 1000)}",
                    task="ping",
                    payload={
                        "host": host,
                        "count": settings.scenarios.ping.count,
                        "timeout_sec": settings.scenarios.ping.timeout_sec,
                    },
                    path_label=label,
                )
                probes.append(probe)
                findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))

        if settings.scenarios.tcp.enabled:
            relay_probe = services["relay_probe"]
            tcp_jobs = (
                (
                    client,
                    "tcp_probe",
                    {
                        "host": relay_probe["host"] or self._agent_host(relay),
                        "port": int(relay_probe["port"]),
                        "attempts": settings.scenarios.tcp.attempts,
                        "interval_ms": settings.scenarios.tcp.interval_ms,
                        "timeout_ms": settings.scenarios.tcp.timeout_ms,
                        "concurrency": settings.scenarios.tcp.concurrency,
                    },
                    "client_to_relay",
                ),
                (
                    relay,
                    "tcp_probe",
                    {
                        "host": server_host,
                        "port": int(services["mc_local"]["port"]),
                        "attempts": settings.scenarios.tcp.attempts,
                        "interval_ms": settings.scenarios.tcp.interval_ms,
                        "timeout_ms": settings.scenarios.tcp.timeout_ms,
                        "concurrency": settings.scenarios.tcp.concurrency,
                    },
                    "relay_to_server",
                ),
                (
                    client,
                    "mc_tcp_probe",
                    {
                        "host": services["mc_public"]["host"],
                        "port": int(services["mc_public"]["port"]),
                        "attempts": settings.scenarios.tcp.attempts,
                        "interval_ms": settings.scenarios.tcp.interval_ms,
                        "timeout_ms": settings.scenarios.tcp.timeout_ms,
                        "concurrency": settings.scenarios.tcp.concurrency,
                    },
                    "client_to_mc_public",
                ),
                (
                    server,
                    "mc_tcp_probe",
                    {
                        "host": services["mc_local"]["host"],
                        "port": int(services["mc_local"]["port"]),
                        "attempts": settings.scenarios.tcp.attempts,
                        "interval_ms": settings.scenarios.tcp.interval_ms,
                        "timeout_ms": settings.scenarios.tcp.timeout_ms,
                        "concurrency": settings.scenarios.tcp.concurrency,
                    },
                    "server_to_local_mc",
                ),
            )
            for node, task, payload, label in tcp_jobs:
                probe = self._dispatch_probe(node=node, run_id=f"{task}-{int(time.time() * 1000)}", task=task, payload=payload, path_label=label)
                probes.append(probe)
                findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))

    def _run_capacity(
        self,
        probes: list[ProbeResult],
        findings: list[Any],
        services: dict[str, Any],
        scenarios: dict[str, Any],
        nodes: dict[str, dict[str, Any] | None],
    ) -> None:
        settings = self.store.get_settings()
        client = self._require_node(nodes, "client")
        relay = self._require_node(nodes, "relay")
        server = self._require_node(nodes, "server")
        server_host = self._agent_host(server)

        if settings.scenarios.throughput.enabled:
            for reverse in (False, True):
                self._start_iperf_server(server, services, probes, findings, "server_iperf_direct", settings)
                probe = self._dispatch_probe(
                    node=relay,
                    run_id=f"relay-throughput-{int(time.time() * 1000)}",
                    task="throughput",
                    payload={
                        "host": server_host,
                        "port": int(services["iperf_local"]["port"]),
                        "duration_sec": settings.scenarios.throughput.duration_sec,
                        "parallel_streams": settings.scenarios.throughput.parallel_streams,
                        "timeout_sec": settings.scenarios.throughput.timeout_sec,
                        "reverse": reverse,
                    },
                    path_label="relay_to_server",
                )
                probes.append(probe)
                findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))

            for reverse in (False, True):
                self._start_iperf_server(server, services, probes, findings, "server_iperf_public", settings)
                probe = self._dispatch_probe(
                    node=client,
                    run_id=f"client-throughput-{int(time.time() * 1000)}",
                    task="throughput",
                    payload={
                        "host": services["iperf_public"]["host"],
                        "port": int(services["iperf_public"]["port"]),
                        "duration_sec": settings.scenarios.throughput.duration_sec,
                        "parallel_streams": settings.scenarios.throughput.parallel_streams,
                        "timeout_sec": settings.scenarios.throughput.timeout_sec,
                        "reverse": reverse,
                    },
                    path_label="client_to_iperf_public",
                )
                probes.append(probe)
                findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))

        if settings.scenarios.load_inflation.enabled:
            idle_probe = self._dispatch_probe(
                node=client,
                run_id=f"idle-{int(time.time() * 1000)}",
                task="mc_tcp_probe",
                payload={
                    "host": services["mc_public"]["host"],
                    "port": int(services["mc_public"]["port"]),
                    "attempts": settings.scenarios.load_inflation.baseline_attempts,
                    "interval_ms": settings.scenarios.load_inflation.probe_interval_ms,
                    "timeout_ms": settings.scenarios.load_inflation.timeout_ms,
                    "concurrency": 1,
                },
                path_label="client_to_mc_public_load_idle",
            )
            idle_probe.name = "mc_tcp_connect_idle"
            probes.append(idle_probe)
            findings.extend(evaluate_probe_thresholds(idle_probe, settings.thresholds))

            self._start_iperf_server(server, services, probes, findings, "server_iperf_public_load", settings)
            throughput_probe = self._dispatch_probe(
                node=client,
                run_id=f"load-throughput-{int(time.time() * 1000)}",
                task="throughput",
                payload={
                    "host": services["iperf_public"]["host"],
                    "port": int(services["iperf_public"]["port"]),
                    "duration_sec": settings.scenarios.load_inflation.duration_sec,
                    "parallel_streams": settings.scenarios.throughput.parallel_streams,
                    "timeout_sec": settings.scenarios.throughput.timeout_sec,
                },
                path_label="client_to_iperf_public_load",
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
                task="mc_tcp_probe",
                payload={
                    "host": services["mc_public"]["host"],
                    "port": int(services["mc_public"]["port"]),
                    "attempts": loaded_attempts,
                    "interval_ms": settings.scenarios.load_inflation.probe_interval_ms,
                    "timeout_ms": settings.scenarios.load_inflation.timeout_ms,
                    "concurrency": 1,
                },
                path_label="client_to_mc_public_load_loaded",
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

    def _start_iperf_server(
        self,
        server: dict[str, Any],
        services: dict[str, Any],
        probes: list[ProbeResult],
        findings: list[Any],
        path_label: str,
        settings: Any,
    ) -> None:
        probe = self._dispatch_probe(
            node=server,
            run_id=f"iperf-server-{int(time.time() * 1000)}",
            task="start_iperf_server",
            payload={
                "port": int(services["iperf_local"]["port"]),
                "bind_host": services["iperf_local"]["host"],
                "one_off": True,
            },
            path_label=path_label,
        )
        probes.append(probe)
        findings.extend(evaluate_probe_thresholds(probe, settings.thresholds))
        time.sleep(0.3)

    def _dispatch_probe(self, node: dict[str, Any], run_id: str, task: str, payload: dict[str, Any], path_label: str) -> ProbeResult:
        timeout_sec = self._timeout_for_task(task, payload)
        payload = dict(payload)
        payload.setdefault("source", node["role"])
        payload.setdefault("platform_name", self._platform_for_runtime(node["runtime_mode"]))

        if node.get("agent_url"):
            try:
                response = self.http.run_job(node=node, job_id=None, run_id=run_id, task=task, payload=payload)
                self.store.update_pull_status(int(node["id"]), ok=True)
                result = ProbeResult.from_dict(response["result"])
            except Exception as exc:
                self.store.update_pull_status(int(node["id"]), ok=False, error=str(exc))
                if not node.get("last_push_ok"):
                    result = make_error_probe(name=task, source=node["role"], target=str(payload.get("host", node["node_name"])), error=str(exc))
                else:
                    result = self._dispatch_via_queue(node=node, run_id=run_id, task=task, payload=payload, timeout_sec=timeout_sec)
        else:
            result = self._dispatch_via_queue(node=node, run_id=run_id, task=task, payload=payload, timeout_sec=timeout_sec)

        result.metadata.setdefault("path_label", path_label)
        result.metadata.setdefault("source_node", node["role"])
        result.metadata.setdefault("node_runtime_mode", node["runtime_mode"])
        return result

    def _dispatch_via_queue(self, node: dict[str, Any], run_id: str, task: str, payload: dict[str, Any], timeout_sec: float) -> ProbeResult:
        if not node.get("last_push_ok"):
            return make_error_probe(
                name=task,
                source=node["role"],
                target=str(payload.get("host", node["node_name"])),
                error=f"{node['node_name']} is not reachable through pull or push mode",
            )
        job_id = self.store.enqueue_job(node_id=int(node["id"]), run_id=run_id, task=task, payload=payload)
        try:
            job = self.store.wait_for_job(job_id=job_id, timeout_sec=timeout_sec)
        except TimeoutError as exc:
            self.store.fail_job(job_id=job_id, error=str(exc))
            return make_error_probe(name=task, source=node["role"], target=str(payload.get("host", node["node_name"])), error=str(exc))
        if job["status"] != "completed":
            return make_error_probe(
                name=task,
                source=node["role"],
                target=str(payload.get("host", node["node_name"])),
                error=job.get("error") or f"Queued job {job_id} failed",
            )
        return ProbeResult.from_dict(json.loads(job["result_json"]))

    def _require_node(self, nodes: dict[str, dict[str, Any] | None], role: str) -> dict[str, Any]:
        node = nodes.get(role)
        if node is None:
            raise ValueError(f"Node for role {role} has not been configured")
        if not node["enabled"]:
            raise ValueError(f"Node {node['node_name']} is disabled")
        if not node["paired"]:
            raise ValueError(f"Node {node['node_name']} is not paired yet")
        return node

    def _agent_host(self, node: dict[str, Any]) -> str:
        if node.get("agent_url"):
            parsed = urlparse(str(node["agent_url"]))
            if parsed.hostname:
                return parsed.hostname
        raise ValueError(f"Node {node['node_name']} does not have a usable agent URL host")

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
