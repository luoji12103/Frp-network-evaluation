"""TCP connection latency probe."""

from __future__ import annotations

import asyncio
from collections import Counter
from time import perf_counter

from probes.common import ProbeResult, now_iso
from probes.metrics import success_rate, summarize_latency


async def run_tcp_handshake_probe(
    host: str,
    port: int,
    source: str,
    attempts: int = 6,
    interval_ms: int = 250,
    timeout_ms: int = 3000,
    concurrency: int = 1,
    name: str = "tcp_handshake",
) -> ProbeResult:
    """Measure TCP connect latency over repeated attempts."""
    started_at = now_iso()
    start = perf_counter()
    semaphore = asyncio.Semaphore(max(1, concurrency))
    samples: list[dict[str, object] | None] = [None] * attempts

    async def _attempt(index: int) -> None:
        await asyncio.sleep((index * interval_ms) / 1000.0)
        async with semaphore:
            attempt_start = perf_counter()
            try:
                connection = asyncio.open_connection(host=host, port=port)
                _, writer = await asyncio.wait_for(connection, timeout=timeout_ms / 1000.0)
                latency_ms = (perf_counter() - attempt_start) * 1000.0
                writer.close()
                await writer.wait_closed()
                samples[index] = {
                    "attempt": index + 1,
                    "success": True,
                    "latency_ms": latency_ms,
                }
            except Exception as exc:
                error_message = str(exc) or exc.__class__.__name__
                samples[index] = {
                    "attempt": index + 1,
                    "success": False,
                    "latency_ms": None,
                    "error": error_message,
                }

    await asyncio.gather(*(_attempt(index) for index in range(attempts)))
    ordered_samples = [sample for sample in samples if sample is not None]
    latencies = [float(sample["latency_ms"]) for sample in ordered_samples if sample["success"] and sample["latency_ms"] is not None]
    summary = summarize_latency(latencies)
    success_count = sum(1 for sample in ordered_samples if sample["success"])
    error_counts = Counter(str(sample.get("error")) for sample in ordered_samples if not sample["success"])

    metrics = {
        "connect_success_rate_pct": success_rate(success_count, attempts),
        "connect_timeout_or_error_pct": 100.0 - (success_rate(success_count, attempts) or 0.0),
        "connect_avg_ms": summary["avg_ms"],
        "connect_p95_ms": summary["p95_ms"],
        "connect_p99_ms": summary["p99_ms"],
        "connect_max_ms": summary["max_ms"],
    }

    return ProbeResult(
        name=name,
        source=source,
        target=f"{host}:{port}",
        success=success_count > 0,
        metrics=metrics,
        samples=ordered_samples,
        error=None if success_count > 0 else "All TCP connection attempts failed",
        started_at=started_at,
        duration_ms=(perf_counter() - start) * 1000.0,
        metadata={"attempts": attempts, "errors": dict(error_counts), "concurrency": concurrency},
    )
