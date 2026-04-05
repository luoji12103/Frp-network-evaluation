"""Main orchestration flow for mc-netprobe."""

from __future__ import annotations

import asyncio
import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

from agents import execute_task
from controller.scenario import ScenariosConfig, ThresholdsConfig, TopologyConfig
from controller.ssh_exec import SSHExecutor
from probes.common import ProbeResult, RunResult, ThresholdFinding, current_environment, make_error_probe, now_iso
from probes.metrics import calculate_load_inflation


@dataclass(slots=True)
class Orchestrator:
    """Coordinate local and remote probes into one run result."""

    topology: TopologyConfig
    thresholds: ThresholdsConfig
    scenarios: ScenariosConfig
    run_id: str
    ssh: SSHExecutor | None = None

    def __post_init__(self) -> None:
        if self.ssh is None:
            self.ssh = SSHExecutor()

    async def run(self) -> RunResult:
        """Execute the configured probe flow."""
        started_at = now_iso()
        probes: list[ProbeResult] = []
        findings: list[ThresholdFinding] = []

        await self._run_baseline(probes, findings)
        await self._run_throughput(probes, findings)
        await self._run_load_inflation(probes, findings)
        await self._run_system_snapshots(probes, findings)

        finished_at = now_iso()
        conclusion = build_conclusion(probes, findings)
        return RunResult(
            run_id=self.run_id,
            project=self.topology.project_name,
            started_at=started_at,
            finished_at=finished_at,
            environment=current_environment(),
            probes=probes,
            threshold_findings=findings,
            conclusion=conclusion,
        )

    async def _run_baseline(self, probes: list[ProbeResult], findings: list[ThresholdFinding]) -> None:
        if self.scenarios.ping.enabled:
            await self._record(
                probes,
                findings,
                await self._execute_on_node(
                    "client",
                    "ping",
                    {"host": self.topology.nodes.relay.host, "count": self.scenarios.ping.count, "timeout_sec": self.scenarios.ping.timeout_sec},
                    path_label="client_to_relay",
                ),
            )
            await self._record(
                probes,
                findings,
                await self._execute_on_node(
                    "relay",
                    "ping",
                    {"host": self.topology.nodes.server.host, "count": self.scenarios.ping.count, "timeout_sec": self.scenarios.ping.timeout_sec},
                    path_label="relay_to_server",
                ),
            )

        if self.scenarios.tcp.enabled:
            relay_probe = self.topology.services.relay_probe
            if relay_probe is not None:
                await self._record(
                    probes,
                    findings,
                    await self._execute_on_node(
                        "client",
                        "tcp_probe",
                        {
                            "host": relay_probe.host,
                            "port": relay_probe.port,
                            "attempts": self.scenarios.tcp.attempts,
                            "interval_ms": self.scenarios.tcp.interval_ms,
                            "timeout_ms": self.scenarios.tcp.timeout_ms,
                            "concurrency": self.scenarios.tcp.concurrency,
                        },
                        path_label="client_to_relay",
                    ),
                )

            await self._record(
                probes,
                findings,
                await self._execute_on_node(
                    "relay",
                    "tcp_probe",
                    {
                        "host": self.topology.nodes.server.host,
                        "port": self.topology.services.mc_local.port,
                        "attempts": self.scenarios.tcp.attempts,
                        "interval_ms": self.scenarios.tcp.interval_ms,
                        "timeout_ms": self.scenarios.tcp.timeout_ms,
                        "concurrency": self.scenarios.tcp.concurrency,
                    },
                    path_label="relay_to_server",
                ),
            )

            mc_public_probe = await self._execute_on_node(
                "client",
                "mc_tcp_probe",
                {
                    "host": self.topology.services.mc_public.host,
                    "port": self.topology.services.mc_public.port,
                    "attempts": self.scenarios.tcp.attempts,
                    "interval_ms": self.scenarios.tcp.interval_ms,
                    "timeout_ms": self.scenarios.tcp.timeout_ms,
                    "concurrency": self.scenarios.tcp.concurrency,
                },
                path_label="client_to_mc_public",
            )
            await self._record(probes, findings, mc_public_probe)

            server_local_probe = await self._execute_on_node(
                "server",
                "mc_tcp_probe",
                {
                    "host": self.topology.services.mc_local.host,
                    "port": self.topology.services.mc_local.port,
                    "attempts": self.scenarios.tcp.attempts,
                    "interval_ms": self.scenarios.tcp.interval_ms,
                    "timeout_ms": self.scenarios.tcp.timeout_ms,
                    "concurrency": self.scenarios.tcp.concurrency,
                },
                path_label="server_to_local_mc",
            )
            await self._record(probes, findings, server_local_probe)

    async def _run_throughput(self, probes: list[ProbeResult], findings: list[ThresholdFinding]) -> None:
        if not self.scenarios.throughput.enabled:
            return

        await self._start_server_iperf(probes, findings, path_label="server_iperf_direct")
        relay_forward = await self._execute_on_node(
            "relay",
            "throughput",
            {
                "host": self.topology.nodes.server.host,
                "port": self.topology.services.iperf_local.port,
                "duration_sec": self.scenarios.throughput.duration_sec,
                "parallel_streams": self.scenarios.throughput.parallel_streams,
                "timeout_sec": self.scenarios.throughput.timeout_sec,
            },
            path_label="relay_to_server",
        )
        await self._record(probes, findings, relay_forward)

        await self._start_server_iperf(probes, findings, path_label="server_iperf_direct")
        relay_reverse = await self._execute_on_node(
            "relay",
            "throughput",
            {
                "host": self.topology.nodes.server.host,
                "port": self.topology.services.iperf_local.port,
                "duration_sec": self.scenarios.throughput.duration_sec,
                "parallel_streams": self.scenarios.throughput.parallel_streams,
                "timeout_sec": self.scenarios.throughput.timeout_sec,
                "reverse": True,
            },
            path_label="relay_to_server",
        )
        await self._record(probes, findings, relay_reverse)

        await self._start_server_iperf(probes, findings, path_label="server_iperf_public")
        client_forward = await self._execute_on_node(
            "client",
            "throughput",
            {
                "host": self.topology.services.iperf_public.host,
                "port": self.topology.services.iperf_public.port,
                "duration_sec": self.scenarios.throughput.duration_sec,
                "parallel_streams": self.scenarios.throughput.parallel_streams,
                "timeout_sec": self.scenarios.throughput.timeout_sec,
            },
            path_label="client_to_iperf_public",
        )
        await self._record(probes, findings, client_forward)

        await self._start_server_iperf(probes, findings, path_label="server_iperf_public")
        client_reverse = await self._execute_on_node(
            "client",
            "throughput",
            {
                "host": self.topology.services.iperf_public.host,
                "port": self.topology.services.iperf_public.port,
                "duration_sec": self.scenarios.throughput.duration_sec,
                "parallel_streams": self.scenarios.throughput.parallel_streams,
                "timeout_sec": self.scenarios.throughput.timeout_sec,
                "reverse": True,
            },
            path_label="client_to_iperf_public",
        )
        await self._record(probes, findings, client_reverse)

    async def _run_load_inflation(self, probes: list[ProbeResult], findings: list[ThresholdFinding]) -> None:
        if not self.scenarios.load_inflation.enabled:
            return

        idle_probe = await self._execute_on_node(
            "client",
            "mc_tcp_probe",
            {
                "host": self.topology.services.mc_public.host,
                "port": self.topology.services.mc_public.port,
                "attempts": self.scenarios.load_inflation.baseline_attempts,
                "interval_ms": self.scenarios.load_inflation.probe_interval_ms,
                "timeout_ms": self.scenarios.load_inflation.timeout_ms,
                "concurrency": 1,
            },
            path_label="client_to_mc_public_load_idle",
        )
        idle_probe.name = "mc_tcp_connect_idle"
        await self._record(probes, findings, idle_probe)

        await self._start_server_iperf(probes, findings, path_label="server_iperf_public_load")
        loaded_attempts = max(1, math.ceil((self.scenarios.load_inflation.duration_sec * 1000) / self.scenarios.load_inflation.probe_interval_ms))

        throughput_task = asyncio.create_task(
            self._execute_on_node(
                "client",
                "throughput",
                {
                    "host": self.topology.services.iperf_public.host,
                    "port": self.topology.services.iperf_public.port,
                    "duration_sec": self.scenarios.load_inflation.duration_sec,
                    "parallel_streams": self.scenarios.throughput.parallel_streams,
                    "timeout_sec": self.scenarios.throughput.timeout_sec,
                },
                path_label="client_to_iperf_public_load",
            )
        )
        loaded_probe_task = asyncio.create_task(
            self._execute_on_node(
                "client",
                "mc_tcp_probe",
                {
                    "host": self.topology.services.mc_public.host,
                    "port": self.topology.services.mc_public.port,
                    "attempts": loaded_attempts,
                    "interval_ms": self.scenarios.load_inflation.probe_interval_ms,
                    "timeout_ms": self.scenarios.load_inflation.timeout_ms,
                    "concurrency": 1,
                },
                path_label="client_to_mc_public_load_loaded",
            )
        )
        throughput_result, loaded_probe = await asyncio.gather(throughput_task, loaded_probe_task)
        loaded_probe.name = "mc_tcp_connect_loaded"
        await self._record(probes, findings, throughput_result)
        await self._record(probes, findings, loaded_probe)

        load_result = build_load_inflation_result(idle_probe=idle_probe, loaded_probe=loaded_probe, throughput_result=throughput_result)
        load_result.metadata["path_label"] = "client_to_mc_public_load"
        await self._record(probes, findings, load_result)

    async def _run_system_snapshots(self, probes: list[ProbeResult], findings: list[ThresholdFinding]) -> None:
        if not self.scenarios.system.enabled:
            return

        relay_probe = await self._execute_on_node(
            "relay",
            "system_snapshot",
            {
                "sample_interval_sec": self.scenarios.system.sample_interval_sec,
                "process_names": self.scenarios.system.process_names,
            },
            path_label="relay_system",
        )
        await self._record(probes, findings, relay_probe)

        server_probe = await self._execute_on_node(
            "server",
            "system_snapshot",
            {
                "sample_interval_sec": self.scenarios.system.sample_interval_sec,
                "process_names": self.scenarios.system.process_names,
            },
            path_label="server_system",
        )
        await self._record(probes, findings, server_probe)

    async def _record(self, probes: list[ProbeResult], findings: list[ThresholdFinding], probe: ProbeResult) -> None:
        probes.append(probe)
        findings.extend(evaluate_probe_thresholds(probe, self.thresholds))

    async def _start_server_iperf(self, probes: list[ProbeResult], findings: list[ThresholdFinding], path_label: str) -> None:
        server_result = await self._execute_on_node(
            "server",
            "start_iperf_server",
            {
                "port": self.topology.services.iperf_local.port,
                "bind_host": self.topology.services.iperf_local.host,
                "one_off": True,
            },
            path_label=path_label,
        )
        await self._record(probes, findings, server_result)
        await asyncio.sleep(0.3)

    async def _execute_on_node(self, node_name: str, task: str, payload: dict[str, Any], path_label: str) -> ProbeResult:
        node = getattr(self.topology.nodes, node_name)
        merged_payload = dict(payload)
        merged_payload.setdefault("source", node_name)
        merged_payload.setdefault("platform_name", node.os)

        if node.local:
            result = ProbeResult.from_dict(await execute_task(role=node.role, task=task, payload=merged_payload))
        else:
            assert self.ssh is not None
            result = await self.ssh.run_remote_agent(node=node, task=task, payload=merged_payload)

        result.metadata.setdefault("path_label", path_label)
        result.metadata.setdefault("source_node", node_name)
        result.metadata.setdefault("node_os", node.os)
        return result


def evaluate_probe_thresholds(probe: ProbeResult, thresholds: ThresholdsConfig) -> list[ThresholdFinding]:
    """Evaluate numeric threshold violations for a single probe."""
    findings: list[ThresholdFinding] = []
    path_label = str(probe.metadata.get("path_label", "unknown"))

    if probe.name == "ping":
        findings.extend(_check_upper(path_label, probe, "packet_loss_pct", thresholds.ping.packet_loss_pct_max))
        findings.extend(_check_upper(path_label, probe, "rtt_avg_ms", thresholds.ping.rtt_avg_ms_max))
        findings.extend(_check_upper(path_label, probe, "rtt_p95_ms", thresholds.ping.rtt_p95_ms_max))
        findings.extend(_check_upper(path_label, probe, "jitter_ms", thresholds.ping.jitter_ms_max))
    elif probe.name.startswith("tcp_handshake") or probe.name.startswith("mc_tcp_connect"):
        findings.extend(_check_upper(path_label, probe, "connect_avg_ms", thresholds.tcp.connect_avg_ms_max))
        findings.extend(_check_upper(path_label, probe, "connect_p95_ms", thresholds.tcp.connect_p95_ms_max))
        findings.extend(_check_upper(path_label, probe, "connect_timeout_or_error_pct", thresholds.tcp.timeout_or_error_pct_max))
    elif probe.name == "throughput":
        findings.extend(_check_lower(path_label, probe, "throughput_up_mbps", thresholds.throughput.throughput_up_mbps_min))
        findings.extend(_check_lower(path_label, probe, "throughput_down_mbps", thresholds.throughput.throughput_down_mbps_min))
    elif probe.name == "load_inflation":
        findings.extend(_check_upper(path_label, probe, "load_rtt_inflation_ms", thresholds.load_inflation.load_rtt_inflation_ms_max))
        findings.extend(_check_upper(path_label, probe, "loaded_timeout_pct", thresholds.load_inflation.loaded_timeout_pct_max))
    elif probe.name == "system_snapshot":
        findings.extend(_check_upper(path_label, probe, "cpu_usage_pct", thresholds.system.cpu_usage_pct_max))
        findings.extend(_check_upper(path_label, probe, "memory_usage_pct", thresholds.system.memory_usage_pct_max))

    return findings


def build_load_inflation_result(idle_probe: ProbeResult, loaded_probe: ProbeResult, throughput_result: ProbeResult) -> ProbeResult:
    """Create a synthetic load-inflation result from idle and loaded probes."""
    idle_avg = idle_probe.metrics.get("connect_avg_ms")
    loaded_avg = loaded_probe.metrics.get("connect_avg_ms")
    metrics = {
        "idle_connect_avg_ms": idle_avg,
        "loaded_connect_avg_ms": loaded_avg,
        "load_rtt_inflation_ms": calculate_load_inflation(idle_avg, loaded_avg),
        "loaded_connect_p95_ms": loaded_probe.metrics.get("connect_p95_ms"),
        "loaded_timeout_pct": loaded_probe.metrics.get("connect_timeout_or_error_pct"),
    }
    success = throughput_result.success and idle_avg is not None and loaded_avg is not None
    error_parts: list[str] = []
    if not throughput_result.success:
        error_parts.append(f"Throughput load failed: {throughput_result.error}")
    if idle_avg is None or loaded_avg is None:
        error_parts.append("Missing idle or loaded TCP average")

    return ProbeResult(
        name="load_inflation",
        source="client",
        target=f"{idle_probe.target} under load",
        success=success,
        metrics=metrics,
        samples=[],
        error="; ".join(error_parts) if error_parts else None,
        started_at=now_iso(),
        duration_ms=0.0,
        metadata={
            "idle_probe": idle_probe.name,
            "loaded_probe": loaded_probe.name,
            "throughput_probe": throughput_result.name,
        },
    )


def build_conclusion(probes: list[ProbeResult], findings: list[ThresholdFinding]) -> list[str]:
    """Build a compact human-readable conclusion block."""
    lines: list[str] = []
    failure_count = sum(1 for probe in probes if not probe.success)
    baseline_mc_probe = next(
        (
            probe
            for probe in probes
            if probe.name == "mc_tcp_connect" and probe.metadata.get("path_label") == "client_to_mc_public"
        ),
        None,
    )
    if baseline_mc_probe and baseline_mc_probe.metrics.get("connect_avg_ms") is not None:
        lines.append(
            "Client to mc_public TCP average "
            f"{baseline_mc_probe.metrics.get('connect_avg_ms'):.2f} ms, "
            f"P95 {baseline_mc_probe.metrics.get('connect_p95_ms'):.2f} ms."
        )

    load_probe = next((probe for probe in probes if probe.name == "load_inflation"), None)
    if load_probe and load_probe.metrics.get("load_rtt_inflation_ms") is not None:
        lines.append(
            "Load inflation delta "
            f"{load_probe.metrics.get('load_rtt_inflation_ms'):.2f} ms, "
            f"loaded timeout {load_probe.metrics.get('loaded_timeout_pct') or 0.0:.2f}%."
        )

    if findings:
        dominant = Counter(finding.path_label for finding in findings).most_common(1)[0][0]
        lines.append(f"Most threshold violations are concentrated on {dominant}.")
    elif failure_count == 0:
        lines.append("No threshold violations detected in the completed probe set.")

    if failure_count > 0:
        lines.append(f"{failure_count} probe(s) reported errors; review raw.json for details.")

    if not lines:
        lines.append("Run completed without enough data to derive a bottleneck conclusion.")
    return lines


def _check_upper(path_label: str, probe: ProbeResult, metric: str, threshold: float) -> list[ThresholdFinding]:
    value = probe.metrics.get(metric)
    if value is None or float(value) <= threshold:
        return []
    return [
        ThresholdFinding(
            path_label=path_label,
            probe_name=probe.name,
            metric=metric,
            threshold=threshold,
            actual=float(value),
            message=f"{metric} exceeded the configured maximum",
        )
    ]


def _check_lower(path_label: str, probe: ProbeResult, metric: str, threshold: float) -> list[ThresholdFinding]:
    value = probe.metrics.get(metric)
    if value is None or float(value) >= threshold:
        return []
    return [
        ThresholdFinding(
            path_label=path_label,
            probe_name=probe.name,
            metric=metric,
            threshold=threshold,
            actual=float(value),
            message=f"{metric} fell below the configured minimum",
        )
    ]
