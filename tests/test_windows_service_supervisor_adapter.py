from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from controller.control_bridge import BridgeActionError, WindowsServiceSupervisorAdapter


class FakeCompleted:
    def __init__(self, stdout: str, stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def test_windows_service_supervisor_adapter_reads_status(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], capture_output: bool, text: bool, check: bool) -> FakeCompleted:
        calls.append(command)
        return FakeCompleted(
            json.dumps(
                {
                    "ok": True,
                    "status": {
                        "state": "running",
                        "agent_state": "running",
                        "control_bridge_state": "running",
                        "last_error": None,
                    },
                }
            )
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = WindowsServiceSupervisorAdapter(
        control_exe=tmp_path / "mc-netprobe-service.exe",
        log_path=tmp_path / "control-bridge.log",
    )

    response = adapter.runtime()

    assert response.state == "running"
    assert response.supervisor.process_state == "running"
    assert calls[0][1:] == ["control", "status"]


def test_windows_service_supervisor_adapter_surfaces_control_errors(monkeypatch, tmp_path: Path) -> None:
    def fake_run(command: list[str], capture_output: bool, text: bool, check: bool) -> FakeCompleted:
        return FakeCompleted("", "pipe unavailable", 1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = WindowsServiceSupervisorAdapter(
        control_exe=tmp_path / "mc-netprobe-service.exe",
        log_path=tmp_path / "control-bridge.log",
    )

    with pytest.raises(BridgeActionError) as error:
        adapter.runtime()

    assert error.value.code == "windows_supervisor_control_failed"
    assert "pipe unavailable" in error.value.message
