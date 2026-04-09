"""Helpers for generating macOS launchd plist files for the control bridge."""

from __future__ import annotations

import argparse
import plistlib
import shlex
from pathlib import Path

from controller.control_bridge import DEFAULT_MACOS_CONTROL_BRIDGE_LABEL, DEFAULT_NODE_CONTROL_PORT_OFFSET


DEFAULT_AGENT_LABEL = "com.mc-netprobe.server.agent"
DEFAULT_AGENT_CONFIG_PATH = Path("config/agent/server.yaml")
DEFAULT_BRIDGE_LOG_NAME = "server-control-bridge.launchd.log"


def resolve_repo_path(repo_root: str | Path, requested_path: str | Path) -> Path:
    root = Path(repo_root).expanduser().resolve()
    path = Path(requested_path).expanduser()
    return path if path.is_absolute() else (root / path)


def resolve_launchd_log_path(home_dir: str | Path, requested_path: str | Path = DEFAULT_BRIDGE_LOG_NAME) -> Path:
    home = Path(home_dir).expanduser().resolve()
    path = Path(requested_path).expanduser()
    if path.is_absolute():
        return path
    return (home / "Library" / "Logs" / "mc-netprobe" / path.name).resolve()


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
    bridge_log_path: str | Path = DEFAULT_BRIDGE_LOG_NAME,
) -> dict[str, object]:
    root = Path(repo_root).expanduser().resolve()
    user_home = Path(home_dir).expanduser().resolve()
    agent_config_path = resolve_repo_path(root, agent_config)
    log_path = resolve_launchd_log_path(user_home, bridge_log_path)
    plist_path = user_home / "Library" / "LaunchAgents" / f"{agent_label}.plist"
    command = " ".join(
        [
            f"cd {shlex.quote(str(root))}",
            "&&",
            "exec",
            shlex.quote(python_bin),
            "-m",
            "controller.control_bridge",
            "--mode",
            "node",
            "--adapter",
            "launchd",
            "--host",
            shlex.quote(bridge_host),
            "--port",
            shlex.quote(str(bridge_port)),
            "--agent-config",
            shlex.quote(str(agent_config_path)),
            "--label",
            shlex.quote(agent_label),
            "--plist-path",
            shlex.quote(str(plist_path)),
            "--log-path",
            shlex.quote(str(log_path)),
            "--bridge-url",
            shlex.quote(f"http://{bridge_host}:{bridge_port}"),
        ]
    )
    return {
        "Label": bridge_label,
        "ProgramArguments": [
            "/bin/zsh",
            "-c",
            command,
        ],
        "WorkingDirectory": str(user_home),
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
    parser.add_argument("--bridge-log-path", default=DEFAULT_BRIDGE_LOG_NAME)
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
