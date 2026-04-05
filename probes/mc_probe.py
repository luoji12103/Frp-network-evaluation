"""Minecraft probe helpers for MVP."""

from __future__ import annotations

from probes.tcp_handshake import run_tcp_handshake_probe


async def run_mc_tcp_probe(
    host: str,
    port: int,
    source: str,
    attempts: int = 6,
    interval_ms: int = 250,
    timeout_ms: int = 3000,
    concurrency: int = 1,
):
    """Use TCP connect latency as the MVP MC probe."""
    return await run_tcp_handshake_probe(
        host=host,
        port=port,
        source=source,
        attempts=attempts,
        interval_ms=interval_ms,
        timeout_ms=timeout_ms,
        concurrency=concurrency,
        name="mc_tcp_connect",
    )
