"""iperf3 throughput probe and helpers."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from time import perf_counter
from typing import Any

from probes.common import ProbeResult, make_error_probe, now_iso, run_cmd
from probes.metrics import stability_score


async def run_throughput_probe(
    host: str,
    port: int,
    source: str,
    duration_sec: int = 10,
    reverse: bool = False,
    parallel_streams: int = 1,
    timeout_sec: float = 20.0,
) -> ProbeResult:
    """Run an iperf3 client session and parse its JSON output."""
    started_at = now_iso()
    start = perf_counter()
    command = [
        "iperf3",
        "--json",
        "--client",
        host,
        "--port",
        str(port),
        "--time",
        str(duration_sec),
    ]
    if reverse:
        command.append("--reverse")
    if parallel_streams > 1:
        command.extend(["--parallel", str(parallel_streams)])

    command_result = await run_cmd(command, timeout_sec=timeout_sec)
    if not command_result.succeeded:
        return make_error_probe(
            name="throughput",
            source=source,
            target=f"{host}:{port}",
            error=command_result.stderr or "iperf3 command failed",
            metadata={"command": command, "exit_code": command_result.exit_code, "reverse": reverse},
        )

    try:
        metrics, samples = parse_iperf3_output(command_result.stdout, reverse=reverse)
    except (ValueError, json.JSONDecodeError) as exc:
        return make_error_probe(
            name="throughput",
            source=source,
            target=f"{host}:{port}",
            error=f"Failed to parse iperf3 output: {exc}",
            metadata={"stdout": command_result.stdout, "stderr": command_result.stderr},
        )

    return ProbeResult(
        name="throughput",
        source=source,
        target=f"{host}:{port}",
        success=True,
        metrics=metrics,
        samples=samples,
        started_at=started_at,
        duration_ms=(perf_counter() - start) * 1000.0,
        metadata={"reverse": reverse, "parallel_streams": parallel_streams, "command": command},
    )


def parse_iperf3_output(raw_output: str, reverse: bool) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Parse iperf3 JSON into normalized metrics."""
    payload = json.loads(raw_output)
    end = payload["end"]
    intervals = payload.get("intervals", [])
    interval_rates = [interval["sum"]["bits_per_second"] / 1_000_000.0 for interval in intervals if "sum" in interval]
    samples = [{"throughput_mbps": value} for value in interval_rates]

    sent = end.get("sum_sent", {})
    received = end.get("sum_received", {})
    transfer_up = float(sent.get("bits_per_second", 0.0)) / 1_000_000.0 if sent else None
    transfer_down = float(received.get("bits_per_second", 0.0)) / 1_000_000.0 if received else None

    metrics = {
        "throughput_up_mbps": transfer_up if not reverse else None,
        "throughput_down_mbps": transfer_down if reverse else None,
        "throughput_stability_score": stability_score(interval_rates),
        "retransmits": sent.get("retransmits"),
        "test_duration_sec": sent.get("seconds") or received.get("seconds"),
    }
    return metrics, samples


async def start_iperf_server_process(
    port: int,
    bind_host: str,
    source: str,
    one_off: bool = True,
) -> ProbeResult:
    """Start an iperf3 server in the background."""
    iperf_binary = shutil.which("iperf3")
    if not iperf_binary:
        return make_error_probe(
            name="iperf3_server",
            source=source,
            target=f"{bind_host}:{port}",
            error="iperf3 executable not found",
        )

    command = [iperf_binary, "--server", "--port", str(port), "--bind", bind_host]
    if one_off:
        command.append("--one-off")

    try:
        process = subprocess.Popen(  # noqa: S603
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        await asyncio.sleep(0.2)
        if process.poll() is not None:
            return make_error_probe(
                name="iperf3_server",
                source=source,
                target=f"{bind_host}:{port}",
                error="iperf3 server exited immediately",
                metadata={"command": command, "exit_code": process.returncode},
            )
        return ProbeResult(
            name="iperf3_server",
            source=source,
            target=f"{bind_host}:{port}",
            success=True,
            metrics={"port": port},
            samples=[],
            error=None,
            started_at=now_iso(),
            duration_ms=0.0,
            metadata={"command": command, "pid": process.pid, "one_off": one_off},
        )
    except OSError as exc:
        return make_error_probe(
            name="iperf3_server",
            source=source,
            target=f"{bind_host}:{port}",
            error=str(exc),
            metadata={"command": command},
        )
