"""SSH helpers for remote agent execution."""

from __future__ import annotations

import json
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from controller.scenario import NodeConfig
from probes.common import ProbeResult, make_error_probe, run_cmd


@dataclass(slots=True)
class SSHExecutor:
    """Wrapper around system ssh/scp binaries."""

    connect_timeout_sec: float = 15.0

    async def run_remote_agent(self, node: NodeConfig, task: str, payload: dict[str, Any]) -> ProbeResult:
        """Run an agent task over SSH and parse its JSON output."""
        if node.local:
            raise ValueError("Local nodes must not be executed through SSH")
        if not node.ssh_user:
            raise ValueError(f"ssh_user is required for remote node {node.role}")

        remote_args = [
            node.python_bin,
            "-m",
            f"agents.agent_{node.role}",
            "--task",
            task,
            "--json",
        ]
        remote_args.extend(_serialize_cli_args(payload))

        remote_command = f"cd {shlex.quote(node.project_root)} && {shlex.join(remote_args)}"
        command = [
            "ssh",
            "-o",
            f"ConnectTimeout={int(self.connect_timeout_sec)}",
            "-p",
            str(node.ssh_port),
            f"{node.ssh_user}@{node.host}",
            remote_command,
        ]

        result = await run_cmd(command, timeout_sec=max(self.connect_timeout_sec, float(payload.get("timeout_sec", 20.0)) + 5.0))
        stdout = result.stdout.strip()
        if stdout:
            try:
                return ProbeResult.from_dict(json.loads(_extract_json(stdout)))
            except (json.JSONDecodeError, ValueError) as exc:
                return make_error_probe(
                    name=task,
                    source=node.role,
                    target=str(payload.get("host") or node.host),
                    error=f"Failed to parse remote agent output: {exc}",
                    metadata={"stdout": stdout, "stderr": result.stderr, "command": command},
                )

        return make_error_probe(
            name=task,
            source=node.role,
            target=str(payload.get("host") or node.host),
            error=result.stderr or "Remote execution produced no output",
            metadata={"command": command, "exit_code": result.exit_code},
        )

    async def copy_file_to_remote(self, node: NodeConfig, local_path: str | Path, remote_path: str) -> bool:
        """Copy a file to a remote node using scp."""
        if not node.ssh_user:
            raise ValueError(f"ssh_user is required for remote node {node.role}")

        command = [
            "scp",
            "-P",
            str(node.ssh_port),
            str(local_path),
            f"{node.ssh_user}@{node.host}:{remote_path}",
        ]
        result = await run_cmd(command, timeout_sec=self.connect_timeout_sec + 30.0)
        return result.succeeded


def _serialize_cli_args(payload: dict[str, Any]) -> list[str]:
    arguments: list[str] = []
    for key, value in payload.items():
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                arguments.append(flag)
            continue
        if isinstance(value, list):
            if value:
                arguments.append(flag)
                arguments.extend(str(item) for item in value)
            continue
        arguments.extend([flag, str(value)])
    return arguments


def _extract_json(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty output")
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in output")
    return stripped[start : end + 1]
