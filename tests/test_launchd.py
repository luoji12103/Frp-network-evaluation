from __future__ import annotations

import plistlib
from pathlib import Path

from agents.launchd import DEFAULT_LABEL, build_launchd_paths, build_launchd_plist, write_launchd_plist


def test_build_launchd_paths_resolves_default_repo_relative_locations() -> None:
    paths = build_launchd_paths(
        repo_root="/Users/me/mc-netprobe",
        config_path="config/agent/server.yaml",
        home_dir="/Users/me",
    )

    assert paths.config_path == Path("/Users/me/mc-netprobe/config/agent/server.yaml")
    assert paths.log_path == Path("/Users/me/mc-netprobe/logs/server-agent.launchd.log")
    assert paths.plist_path == Path(f"/Users/me/Library/LaunchAgents/{DEFAULT_LABEL}.plist")


def test_build_launchd_paths_preserves_absolute_config_path() -> None:
    paths = build_launchd_paths(
        repo_root="/Users/me/mc-netprobe",
        config_path="/tmp/server-agent.yaml",
        home_dir="/Users/me",
    )

    assert paths.config_path == Path("/tmp/server-agent.yaml")


def test_write_launchd_plist_contains_expected_program_arguments(tmp_path: Path) -> None:
    paths = build_launchd_paths(
        repo_root=tmp_path / "repo",
        config_path="config/agent/server.yaml",
        home_dir=tmp_path / "home",
    )
    payload = build_launchd_plist(
        paths=paths,
        python_bin="/usr/bin/python3",
        panel_url="http://panel-host:8765",
        pair_code="pair-123",
        node_name="server-1",
        role="server",
        runtime_mode="native-macos",
        listen_host="0.0.0.0",
        listen_port=9870,
        label=DEFAULT_LABEL,
    )

    written_path = write_launchd_plist(paths.plist_path, payload)
    parsed = plistlib.loads(written_path.read_bytes())

    assert parsed["Label"] == DEFAULT_LABEL
    assert parsed["WorkingDirectory"] == str(paths.repo_root)
    assert parsed["StandardOutPath"] == str(paths.log_path)
    assert parsed["StandardErrorPath"] == str(paths.log_path)
    assert parsed["ProgramArguments"] == [
        "/usr/bin/python3",
        "-m",
        "agents.service",
        "--config",
        str(paths.config_path),
        "--panel-url",
        "http://panel-host:8765",
        "--pair-code",
        "pair-123",
        "--node-name",
        "server-1",
        "--role",
        "server",
        "--runtime-mode",
        "native-macos",
        "--listen-host",
        "0.0.0.0",
        "--listen-port",
        "9870",
        "--control-port",
        "9871",
    ]
