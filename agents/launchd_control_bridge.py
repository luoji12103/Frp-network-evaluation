"""Helpers for generating macOS launchd plist files for the control bridge."""

from __future__ import annotations

import argparse
import plistlib
from pathlib import Path

from controller.control_bridge import DEFAULT_MACOS_CONTROL_BRIDGE_LABEL, DEFAULT_NODE_CONTROL_PORT_OFFSET


DEFAULT_AGENT_LABEL = "com.mc-netprobe.server.agent"
DEFAULT_AGENT_CONFIG_PATH = Path("config/agent/server.yaml")
DEFAULT_BRIDGE_LOG_PATH = Path("logs/server-control-bridge.launchd.log")


def resolve_repo_path(repo_root: str | Path, requested_path: str | Path) -> Path:
    root = Path(repo_root).expanduser().resolve()
    path = Path(requested_path).expanduser()
    return path if path.is_absolute() else (root / path)


def build_control_bridge_plist(
    *,
    repo_root: str | Path,
    home_dir: str | Path,
    python_bin: str,
    bridge_host: str,
    bridge_port: int,
    agent_config: str | Path = DEFAULT_AGENT_CONFIG_PATH,
    agent_label: str = DEFAULT_AGENT_LABEL,
    bridge_label: str = DEFAULT_MACOS_CONTROL_BRIDGE_LABEL,
    bridge_log_path: str | Path = DEFAULT_BRIDGE_LOG_PATH,
) -> dict[str, object]:
    root = Path(repo_root).expanduser().resolve()
    agent_config_path = resolve_repo_path(root, agent_config)
    log_path = resolve_repo_path(root, bridge_log_path)
    plist_path = Path(home_dir).expanduser().resolve() / "Library" / "LaunchAgents" / f"{agent_label}.plist"
    return {
        "Label": bridge_label,
        "ProgramArguments": [
            python_bin,
            "-m",
            "controller.control_bridge",
            "--mode",
            "node",
            "--adapter",
            "launchd",
            "--host",
            bridge_host,
            "--port",
            str(bridge_port),
            "--agent-config",
            str(agent_config_path),
            "--label",
            agent_label,
            "--plist-path",
            str(plist_path),
            "--log-path",
            str(log_path),
            "--bridge-url",
            f"http://{bridge_host}:{bridge_port}",
        ],
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(log_path),
        "StandardErrorPath": str(log_path),
    }


def write_plist(output_path: str | Path, payload: dict[str, object]) -> Path:
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=False)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write a macOS launchd plist for the control bridge.")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--home-dir", default=str(Path.home()))
    parser.add_argument("--python-bin", required=True)
    parser.add_argument("--bridge-host", default="0.0.0.0")
    parser.add_argument("--bridge-port", type=int, default=9870 + DEFAULT_NODE_CONTROL_PORT_OFFSET)
    parser.add_argument("--agent-config", default=str(DEFAULT_AGENT_CONFIG_PATH))
    parser.add_argument("--agent-label", default=DEFAULT_AGENT_LABEL)
    parser.add_argument("--bridge-label", default=DEFAULT_MACOS_CONTROL_BRIDGE_LABEL)
    parser.add_argument("--bridge-log-path", default=str(DEFAULT_BRIDGE_LOG_PATH))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    payload = build_control_bridge_plist(
        repo_root=args.repo_root,
        home_dir=args.home_dir,
        python_bin=args.python_bin,
        bridge_host=args.bridge_host,
        bridge_port=args.bridge_port,
        agent_config=args.agent_config,
        agent_label=args.agent_label,
        bridge_label=args.bridge_label,
        bridge_log_path=args.bridge_log_path,
    )
    output_path = Path(args.home_dir).expanduser().resolve() / "Library" / "LaunchAgents" / f"{args.bridge_label}.plist"
    write_plist(output_path, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
