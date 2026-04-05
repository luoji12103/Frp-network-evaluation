"""Agent task dispatch helpers."""

from __future__ import annotations

import argparse
import json
from typing import Any

from probes.mc_probe import run_mc_tcp_probe
from probes.common import detect_platform_name
from probes.ping import run_ping_probe
from probes.system_probe import run_system_snapshot_probe
from probes.tcp_handshake import run_tcp_handshake_probe
from probes.throughput import run_throughput_probe, start_iperf_server_process


async def execute_task(role: str, task: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a single agent task and return a serialized probe result."""
    source = payload.get("source", role)
    platform_name = payload.get("platform_name") or detect_platform_name()

    if task == "ping":
        result = await run_ping_probe(
            host=payload["host"],
            source=source,
            count=int(payload.get("count", 4)),
            timeout_sec=float(payload.get("timeout_sec", 10.0)),
            executor_os=platform_name,
        )
    elif task == "tcp_probe":
        result = await run_tcp_handshake_probe(
            host=payload["host"],
            port=int(payload["port"]),
            source=source,
            attempts=int(payload.get("attempts", payload.get("count", 6))),
            interval_ms=int(payload.get("interval_ms", 250)),
            timeout_ms=int(payload.get("timeout_ms", 3000)),
            concurrency=int(payload.get("concurrency", 1)),
            name="tcp_handshake",
        )
    elif task == "mc_tcp_probe":
        result = await run_mc_tcp_probe(
            host=payload["host"],
            port=int(payload["port"]),
            source=source,
            attempts=int(payload.get("attempts", payload.get("count", 6))),
            interval_ms=int(payload.get("interval_ms", 250)),
            timeout_ms=int(payload.get("timeout_ms", 3000)),
            concurrency=int(payload.get("concurrency", 1)),
        )
    elif task == "throughput":
        result = await run_throughput_probe(
            host=payload["host"],
            port=int(payload["port"]),
            source=source,
            duration_sec=int(payload.get("duration_sec", 10)),
            reverse=bool(payload.get("reverse", False)),
            parallel_streams=int(payload.get("parallel_streams", 1)),
            timeout_sec=float(payload.get("timeout_sec", 20.0)),
        )
    elif task == "system_snapshot":
        result = await run_system_snapshot_probe(
            source=source,
            sample_interval_sec=float(payload.get("sample_interval_sec", 1.0)),
            process_names=list(payload.get("process_names", [])),
            platform_name=platform_name,
        )
    elif task == "start_iperf_server":
        result = await start_iperf_server_process(
            port=int(payload["port"]),
            bind_host=str(payload.get("bind_host", "0.0.0.0")),
            source=source,
            one_off=bool(payload.get("one_off", True)),
        )
    else:
        raise ValueError(f"Unsupported task: {task}")

    return result.to_dict()


def build_parser() -> argparse.ArgumentParser:
    """Build a generic parser shared by all agent roles."""
    parser = argparse.ArgumentParser(description="mc-netprobe agent task runner")
    parser.add_argument("--task", required=True)
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--count", type=int)
    parser.add_argument("--attempts", type=int)
    parser.add_argument("--timeout-sec", dest="timeout_sec", type=float)
    parser.add_argument("--timeout-ms", dest="timeout_ms", type=int)
    parser.add_argument("--interval-ms", dest="interval_ms", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--duration-sec", dest="duration_sec", type=int)
    parser.add_argument("--parallel-streams", dest="parallel_streams", type=int)
    parser.add_argument("--source")
    parser.add_argument("--platform-name", dest="platform_name")
    parser.add_argument("--bind-host", dest="bind_host")
    parser.add_argument("--process-names", nargs="*")
    parser.add_argument("--reverse", action="store_true")
    parser.add_argument("--one-off", action="store_true", default=False)
    parser.add_argument("--json", action="store_true")
    return parser


async def run_agent(role: str) -> int:
    """CLI entrypoint for agent modules."""
    parser = build_parser()
    args = parser.parse_args()
    payload = {key: value for key, value in vars(args).items() if value is not None}
    task = str(payload.pop("task"))
    payload.pop("json", None)
    payload.setdefault("source", role)

    try:
        result = await execute_task(role=role, task=task, payload=payload)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as exc:  # pragma: no cover - defensive path
        error_result = {
            "name": task,
            "source": role,
            "target": payload.get("host") or payload.get("port") or "unknown",
            "success": False,
            "metrics": {},
            "samples": [],
            "error": str(exc),
            "started_at": None,
            "duration_ms": 0.0,
            "metadata": {"role": role},
        }
        print(json.dumps(error_result, indent=2, ensure_ascii=False))
        return 0
