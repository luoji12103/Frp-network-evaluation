"""System resource snapshot probe."""

from __future__ import annotations

import asyncio
import os
from time import perf_counter
from typing import Any

import psutil

from probes.common import ProbeResult, now_iso


async def run_system_snapshot_probe(
    source: str,
    sample_interval_sec: float = 1.0,
    process_names: list[str] | None = None,
    platform_name: str = "linux",
) -> ProbeResult:
    """Capture a lightweight system resource snapshot."""
    started_at = now_iso()
    start = perf_counter()
    process_names = process_names or []
    desired_names = {item.lower() for item in process_names}

    tracked = []
    for process in psutil.process_iter(["name"]):
        name = (process.info.get("name") or "").lower()
        if not desired_names or name in desired_names:
            tracked.append(process)
            try:
                process.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    network_before = psutil.net_io_counters()
    cpu_task = asyncio.create_task(asyncio.to_thread(psutil.cpu_percent, interval=sample_interval_sec))
    await asyncio.sleep(sample_interval_sec)
    network_after = psutil.net_io_counters()
    cpu_usage = await cpu_task

    upload_mbps = ((network_after.bytes_sent - network_before.bytes_sent) * 8) / sample_interval_sec / 1_000_000.0
    download_mbps = ((network_after.bytes_recv - network_before.bytes_recv) * 8) / sample_interval_sec / 1_000_000.0
    memory_usage = psutil.virtual_memory().percent

    load_average, metadata = get_load_average_for_platform(platform_name)
    process_metrics = _collect_process_metrics(tracked)
    metrics: dict[str, Any] = {
        "cpu_usage_pct": cpu_usage,
        "memory_usage_pct": memory_usage,
        "network_up_mbps": upload_mbps,
        "network_down_mbps": download_mbps,
        "load_avg_1m": load_average[0],
        "load_avg_5m": load_average[1],
        "load_avg_15m": load_average[2],
    }

    return ProbeResult(
        name="system_snapshot",
        source=source,
        target=source,
        success=True,
        metrics=metrics,
        samples=[],
        error=None,
        started_at=started_at,
        duration_ms=(perf_counter() - start) * 1000.0,
        metadata={**metadata, "process_metrics": process_metrics},
    )


def get_load_average_for_platform(platform_name: str) -> tuple[tuple[float | None, float | None, float | None], dict[str, Any]]:
    """Return load average or a clear unsupported marker."""
    if platform_name == "windows":
        return (None, None, None), {"load_average": "unsupported_on_windows"}
    try:
        averages = os.getloadavg()
        return (float(averages[0]), float(averages[1]), float(averages[2])), {}
    except OSError:
        return (None, None, None), {"load_average": "unavailable"}


def _collect_process_metrics(processes: list[psutil.Process]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for process in processes:
        try:
            rows.append(
                {
                    "pid": process.pid,
                    "name": process.name(),
                    "cpu_usage_pct": process.cpu_percent(interval=None),
                    "rss_mb": round(process.memory_info().rss / (1024 * 1024), 2),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return rows
