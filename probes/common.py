"""Common data structures and process execution helpers."""

from __future__ import annotations

import asyncio
import os
import platform
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping, Sequence


@dataclass(slots=True)
class CommandResult:
    """Captured external command execution."""

    command: list[str]
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool
    started_at: str

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


@dataclass(slots=True)
class ProbeResult:
    """Normalized probe result schema."""

    name: str
    source: str
    target: str
    success: bool
    metrics: dict[str, Any] = field(default_factory=dict)
    samples: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    started_at: str | None = None
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "target": self.target,
            "success": self.success,
            "metrics": self.metrics,
            "samples": self.samples,
            "error": self.error,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProbeResult":
        return cls(
            name=str(data["name"]),
            source=str(data["source"]),
            target=str(data["target"]),
            success=bool(data["success"]),
            metrics=dict(data.get("metrics", {})),
            samples=list(data.get("samples", [])),
            error=data.get("error"),
            started_at=data.get("started_at"),
            duration_ms=float(data.get("duration_ms", 0.0) or 0.0),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(slots=True)
class ThresholdFinding:
    """A threshold violation emitted by the orchestrator."""

    path_label: str
    probe_name: str
    metric: str
    threshold: float
    actual: float
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return {
            "path_label": self.path_label,
            "probe_name": self.probe_name,
            "metric": self.metric,
            "threshold": self.threshold,
            "actual": self.actual,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(slots=True)
class RunResult:
    """Top-level run payload exported by main.py."""

    run_id: str
    project: str
    started_at: str
    finished_at: str
    environment: dict[str, Any]
    probes: list[ProbeResult]
    threshold_findings: list[ThresholdFinding]
    conclusion: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "project": self.project,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "environment": self.environment,
            "probes": [probe.to_dict() for probe in self.probes],
            "threshold_findings": [finding.to_dict() for finding in self.threshold_findings],
            "conclusion": self.conclusion,
        }


async def run_cmd(
    command: Sequence[str],
    timeout_sec: float,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    """Run a command with timeout and capture stdout/stderr."""
    started_at = now_iso()
    start = perf_counter()
    process: asyncio.subprocess.Process | None = None

    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd else None,
            env=dict(env) if env else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
        return CommandResult(
            command=list(command),
            exit_code=process.returncode,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_ms=(perf_counter() - start) * 1000.0,
            timed_out=False,
            started_at=started_at,
        )
    except FileNotFoundError as exc:
        return CommandResult(
            command=list(command),
            exit_code=127,
            stdout="",
            stderr=str(exc),
            duration_ms=(perf_counter() - start) * 1000.0,
            timed_out=False,
            started_at=started_at,
        )
    except TimeoutError:
        if process is not None:
            process.kill()
            await process.communicate()
        return CommandResult(
            command=list(command),
            exit_code=None,
            stdout="",
            stderr=f"Command timed out after {timeout_sec} seconds",
            duration_ms=(perf_counter() - start) * 1000.0,
            timed_out=True,
            started_at=started_at,
        )


def make_error_probe(name: str, source: str, target: str, error: str, metadata: dict[str, Any] | None = None) -> ProbeResult:
    """Build a failed probe result with standard fields."""
    return ProbeResult(
        name=name,
        source=source,
        target=target,
        success=False,
        error=error,
        started_at=now_iso(),
        duration_ms=0.0,
        metadata=metadata or {},
    )


def now_iso() -> str:
    """Return a timezone-aware timestamp."""
    return datetime.now(timezone.utc).astimezone().isoformat()


def current_environment() -> dict[str, Any]:
    """Describe the local controller runtime."""
    return {
        "platform": platform.platform(),
        "python_version": sys.version.split()[0],
        "cwd": str(Path.cwd()),
        "hostname": platform.node(),
        "pid": os.getpid(),
    }
