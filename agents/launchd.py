"""Helpers for generating macOS launchd plist files for the agent service."""

from __future__ import annotations

import argparse
import plistlib
import shlex
from dataclasses import dataclass
from pathlib import Path


DEFAULT_LABEL = "com.mc-netprobe.server.agent"
DEFAULT_CONFIG_PATH = Path("config/agent/server.yaml")
DEFAULT_LOG_NAME = "server-agent.launchd.log"
DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 9870
DEFAULT_CONTROL_PORT = DEFAULT_LISTEN_PORT + 1
DEFAULT_NODE_NAME = "server"
DEFAULT_ROLE = "server"
DEFAULT_RUNTIME_MODE = "native-macos"


@dataclass(frozen=True)
class LaunchdInstallPaths:
    """Resolved paths used by the launchd installer."""

    repo_root: Path
    home_dir: Path
    config_path: Path
    log_path: Path
    plist_path: Path


def resolve_repo_path(repo_root: str | Path, requested_path: str | Path) -> Path:
    """Resolve a repo-relative or absolute path to an absolute location."""
    root = Path(repo_root).expanduser().resolve()
    path = Path(requested_path).expanduser()
    if path.is_absolute():
        return path
    return root / path


def build_launchd_paths(
    repo_root: str | Path,
    config_path: str | Path = DEFAULT_CONFIG_PATH,
    *,
    home_dir: str | Path | None = None,
    label: str = DEFAULT_LABEL,
) -> LaunchdInstallPaths:
    """Build the resolved filesystem paths used by the installer."""
    root = Path(repo_root).expanduser().resolve()
    user_home = Path(home_dir).expanduser().resolve() if home_dir is not None else Path.home().resolve()
    log_path = (user_home / "Library" / "Logs" / "mc-netprobe" / DEFAULT_LOG_NAME).resolve()
    return LaunchdInstallPaths(
        repo_root=root,
        home_dir=user_home,
        config_path=resolve_repo_path(root, config_path),
        log_path=log_path,
        plist_path=(user_home / "Library" / "LaunchAgents" / f"{label}.plist").resolve(),
    )


def build_launchd_plist(
    *,
    paths: LaunchdInstallPaths,
    python_bin: str,
    panel_url: str,
    pair_code: str,
    node_name: str = DEFAULT_NODE_NAME,
    role: str = DEFAULT_ROLE,
    runtime_mode: str = DEFAULT_RUNTIME_MODE,
    listen_host: str = DEFAULT_LISTEN_HOST,
    listen_port: int = DEFAULT_LISTEN_PORT,
    control_port: int | None = DEFAULT_CONTROL_PORT,
    label: str = DEFAULT_LABEL,
) -> dict[str, object]:
    """Construct the plist payload for the launch agent."""
    command = " ".join(
        [
            f"cd {shlex.quote(str(paths.repo_root))}",
            "&&",
            "exec",
            shlex.quote(python_bin),
            "-m",
            "agents.service",
            "--config",
            shlex.quote(str(paths.config_path)),
            "--panel-url",
            shlex.quote(panel_url),
            "--pair-code",
            shlex.quote(pair_code),
            "--node-name",
            shlex.quote(node_name),
            "--role",
            shlex.quote(role),
            "--runtime-mode",
            shlex.quote(runtime_mode),
            "--listen-host",
            shlex.quote(listen_host),
            "--listen-port",
            shlex.quote(str(listen_port)),
            "--control-port",
            shlex.quote(str(control_port if control_port is not None else listen_port + 1)),
        ]
    )
    return {
        "Label": label,
        "ProgramArguments": [
            "/bin/zsh",
            "-c",
            command,
        ],
        "WorkingDirectory": str(paths.home_dir),
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(paths.log_path),
        "StandardErrorPath": str(paths.log_path),
    }


def write_launchd_plist(plist_path: str | Path, payload: dict[str, object]) -> Path:
    """Write a launchd plist to disk in XML format."""
    output_path = Path(plist_path).expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=False)
    return output_path


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser used by the shell installer."""
    parser = argparse.ArgumentParser(description="Write a macOS launchd plist for the agent service.")
    parser.add_argument("--repo-root", required=True)
    parser.add_argument("--home-dir", default=str(Path.home()))
    parser.add_argument("--python-bin", required=True)
    parser.add_argument("--panel-url", required=True)
    parser.add_argument("--pair-code", required=True)
    parser.add_argument("--node-name", default=DEFAULT_NODE_NAME)
    parser.add_argument("--role", default=DEFAULT_ROLE)
    parser.add_argument("--runtime-mode", default=DEFAULT_RUNTIME_MODE)
    parser.add_argument("--listen-host", default=DEFAULT_LISTEN_HOST)
    parser.add_argument("--listen-port", type=int, default=DEFAULT_LISTEN_PORT)
    parser.add_argument("--control-port", type=int, default=DEFAULT_CONTROL_PORT)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    parser.add_argument("--label", default=DEFAULT_LABEL)
    return parser


def main() -> int:
    """Generate and write the launchd plist."""
    args = build_parser().parse_args()
    paths = build_launchd_paths(
        repo_root=args.repo_root,
        config_path=args.config,
        home_dir=args.home_dir,
        label=args.label,
    )
    payload = build_launchd_plist(
        paths=paths,
        python_bin=args.python_bin,
        panel_url=args.panel_url,
        pair_code=args.pair_code,
        node_name=args.node_name,
        role=args.role,
        runtime_mode=args.runtime_mode,
        listen_host=args.listen_host,
        listen_port=args.listen_port,
        control_port=args.control_port,
        label=args.label,
    )
    write_launchd_plist(paths.plist_path, payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
