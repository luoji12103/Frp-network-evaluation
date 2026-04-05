"""Cross-platform ping probe."""

from __future__ import annotations

import re
from time import perf_counter

from probes.common import ProbeResult, make_error_probe, now_iso, run_cmd
from probes.metrics import summarize_latency


WINDOWS_PACKET_RE = re.compile(
    r"Packets:\s+Sent\s*=\s*(?P<sent>\d+),\s*Received\s*=\s*(?P<received>\d+),\s*Lost\s*=\s*(?P<lost>\d+)\s+\((?P<loss>\d+)%\s+loss\)",
    re.IGNORECASE,
)
WINDOWS_TIMES_RE = re.compile(
    r"Minimum\s*=\s*(?P<minimum>\d+)ms,\s*Maximum\s*=\s*(?P<maximum>\d+)ms,\s*Average\s*=\s*(?P<average>\d+)ms",
    re.IGNORECASE,
)
UNIX_PACKET_RE = re.compile(
    r"(?P<sent>\d+)\s+packets transmitted,\s+(?P<received>\d+)\s+(?:packets )?received,\s+(?P<loss>[\d.]+)% packet loss",
    re.IGNORECASE,
)
UNIX_TIMES_RE = re.compile(
    r"(?:round-trip|rtt)\s+min/avg/max/(?:mdev|stddev)\s*=\s*(?P<minimum>[\d.]+)/(?P<average>[\d.]+)/(?P<maximum>[\d.]+)/(?P<deviation>[\d.]+)\s+ms",
    re.IGNORECASE,
)
SAMPLE_TIME_RE = re.compile(r"time(?P<operator>[=<])\s*(?P<value>[\d.]+)\s*ms", re.IGNORECASE)


async def run_ping_probe(
    host: str,
    source: str,
    count: int = 4,
    timeout_sec: float = 10.0,
    executor_os: str = "linux",
) -> ProbeResult:
    """Run ping and parse latency statistics."""
    started_at = now_iso()
    start = perf_counter()
    command = build_ping_command(host=host, count=count, executor_os=executor_os)
    command_result = await run_cmd(command, timeout_sec=timeout_sec)

    if not command_result.stdout and command_result.stderr:
        return make_error_probe(
            name="ping",
            source=source,
            target=host,
            error=command_result.stderr,
            metadata={"command": command, "exit_code": command_result.exit_code, "executor_os": executor_os},
        )

    try:
        parsed = parse_ping_output(command_result.stdout)
    except ValueError as exc:
        return make_error_probe(
            name="ping",
            source=source,
            target=host,
            error=str(exc),
            metadata={"stdout": command_result.stdout, "stderr": command_result.stderr, "command": command},
        )

    samples = [{"latency_ms": value, "success": True} for value in parsed["samples"]]
    metrics = {
        "packet_loss_pct": parsed["packet_loss_pct"],
        "rtt_min_ms": parsed["rtt_min_ms"],
        "rtt_avg_ms": parsed["rtt_avg_ms"],
        "rtt_p95_ms": parsed["rtt_p95_ms"],
        "rtt_p99_ms": parsed["rtt_p99_ms"],
        "rtt_max_ms": parsed["rtt_max_ms"],
        "jitter_ms": parsed["jitter_ms"],
    }
    success = bool(parsed["received"] > 0)
    return ProbeResult(
        name="ping",
        source=source,
        target=host,
        success=success,
        metrics=metrics,
        samples=samples,
        error=None if success else "No ping replies received",
        started_at=started_at,
        duration_ms=(perf_counter() - start) * 1000.0,
        metadata={
            "command": command,
            "sent": parsed["sent"],
            "received": parsed["received"],
            "executor_os": executor_os,
        },
    )


def build_ping_command(host: str, count: int, executor_os: str) -> list[str]:
    """Build a ping command for the local platform."""
    if executor_os == "windows":
        return ["ping", "-n", str(count), host]
    return ["ping", "-c", str(count), host]


def parse_ping_output(output: str) -> dict[str, float | int | list[float]]:
    """Parse Windows/macOS/Linux ping output."""
    samples = _extract_samples(output)
    latency_summary = summarize_latency(samples)

    packet_match = WINDOWS_PACKET_RE.search(output)
    if packet_match:
        sent = int(packet_match.group("sent"))
        received = int(packet_match.group("received"))
        packet_loss_pct = float(packet_match.group("loss"))
        times_match = WINDOWS_TIMES_RE.search(output)
        rtt_min = float(times_match.group("minimum")) if times_match else latency_summary["min_ms"]
        rtt_avg = float(times_match.group("average")) if times_match else latency_summary["avg_ms"]
        rtt_max = float(times_match.group("maximum")) if times_match else latency_summary["max_ms"]
    else:
        packet_match = UNIX_PACKET_RE.search(output)
        if not packet_match:
            raise ValueError("Unable to parse ping packet summary")
        sent = int(packet_match.group("sent"))
        received = int(packet_match.group("received"))
        packet_loss_pct = float(packet_match.group("loss"))
        times_match = UNIX_TIMES_RE.search(output)
        rtt_min = float(times_match.group("minimum")) if times_match else latency_summary["min_ms"]
        rtt_avg = float(times_match.group("average")) if times_match else latency_summary["avg_ms"]
        rtt_max = float(times_match.group("maximum")) if times_match else latency_summary["max_ms"]

    return {
        "sent": sent,
        "received": received,
        "packet_loss_pct": packet_loss_pct,
        "rtt_min_ms": rtt_min,
        "rtt_avg_ms": rtt_avg,
        "rtt_p95_ms": latency_summary["p95_ms"],
        "rtt_p99_ms": latency_summary["p99_ms"],
        "rtt_max_ms": rtt_max,
        "jitter_ms": latency_summary["jitter_ms"],
        "samples": samples,
    }


def _extract_samples(output: str) -> list[float]:
    samples: list[float] = []
    for match in SAMPLE_TIME_RE.finditer(output):
        value = float(match.group("value"))
        if match.group("operator") == "<":
            value = max(value / 2.0, 0.5)
        samples.append(value)
    return samples
