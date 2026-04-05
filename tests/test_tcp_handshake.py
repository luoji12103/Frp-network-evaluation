import asyncio

from probes.tcp_handshake import run_tcp_handshake_probe


def test_tcp_handshake_probe_aggregation() -> None:
    async def _runner() -> None:
        server = await asyncio.start_server(lambda reader, writer: writer.close(), host="127.0.0.1", port=0)
        port = server.sockets[0].getsockname()[1]
        try:
            result = await run_tcp_handshake_probe(
                host="127.0.0.1",
                port=port,
                source="test",
                attempts=3,
                interval_ms=10,
                timeout_ms=1000,
            )
            assert result.success is True
            assert result.metrics["connect_success_rate_pct"] == 100.0
            assert result.metrics["connect_avg_ms"] is not None
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(_runner())
