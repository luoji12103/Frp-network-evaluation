"""Interactive quickstart helpers for beginner-friendly role setup."""

from __future__ import annotations

import argparse
import getpass
import os
import platform
import shlex
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import yaml


SERVER_SNIPPET_PATH = Path("config/generated/server-mac.generated.yaml")
RELAY_SNIPPET_PATH = Path("config/generated/relay-linux.generated.yaml")
CLIENT_TOPOLOGY_PATH = Path("config/topology.quickstart.yaml")
QUICKSTART_LOG_DIR = Path("logs/quickstart")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for quickstart flows."""
    parser = argparse.ArgumentParser(description="mc-netprobe quickstart setup")
    parser.add_argument(
        "--mode",
        required=True,
        choices=["server-mac", "relay-linux", "client-windows"],
        help="Role-specific setup flow to execute.",
    )
    return parser


def main() -> int:
    """Entry point for quickstart CLI."""
    args = build_parser().parse_args()
    if args.mode == "server-mac":
        return run_server_mac_quickstart()
    if args.mode == "relay-linux":
        return run_relay_linux_quickstart()
    return run_client_windows_quickstart()


def run_server_mac_quickstart() -> int:
    """Prepare a macOS server node for beginner-friendly testing."""
    print("== mc-netprobe quickstart: macOS server ==")
    warn_if_platform_mismatch(expected="Darwin")
    ensure_parent_dir(SERVER_SNIPPET_PATH)

    defaults = {
        "host": detect_local_ip(),
        "ssh_user": getpass.getuser(),
        "ssh_port": 22,
        "project_root": str(Path.cwd()),
        "python_bin": sys.executable,
        "server_backend_mc_port": 25565,
        "server_backend_iperf_host": "0.0.0.0",
        "server_backend_iperf_port": 5201,
    }

    host = prompt_text("Mac 这台机器给 Windows 客户端/relay 用的地址或主机名", defaults["host"])
    ssh_user = prompt_text("SSH 登录用户名", defaults["ssh_user"])
    ssh_port = prompt_int("SSH 端口", defaults["ssh_port"])
    project_root = prompt_text("项目在 Mac 上的绝对路径", defaults["project_root"])
    python_bin = prompt_text("Mac 上运行项目用的 Python", defaults["python_bin"])
    server_backend_mc_port = prompt_int("Minecraft backend 监听端口", defaults["server_backend_mc_port"])
    server_backend_iperf_host = prompt_text("iperf3 backend 绑定地址", defaults["server_backend_iperf_host"])
    server_backend_iperf_port = prompt_int("iperf3 backend 监听端口", defaults["server_backend_iperf_port"])

    print()
    print("预检查:")
    print(f"- Python: {sys.version.split()[0]}")
    print(f"- iperf3: {'已找到' if command_exists('iperf3') else '未找到'}")
    print(f"- ssh: {'已找到' if command_exists('ssh') else '未找到'}")
    sshd_running = process_running("sshd")
    print(f"- sshd: {'运行中' if sshd_running else '未检测到'}")
    if not sshd_running:
        print("  建议先开启 macOS Remote Login: sudo systemsetup -setremotelogin on")

    mc_listening = is_local_port_open(server_backend_mc_port)
    print(f"- Minecraft backend 端口 {server_backend_mc_port}: {'已监听' if mc_listening else '未监听'}")
    if not mc_listening:
        maybe_start_background_service(
            prompt="如果你的 MC 服务还没启动，可输入启动命令后台运行；直接回车则跳过",
            log_name="mac-mc-server.log",
            success_port=server_backend_mc_port,
        )

    snippet = build_node_setup_snippet(
        role="server",
        host=host,
        os_name="macos",
        ssh_user=ssh_user,
        ssh_port=ssh_port,
        project_root=project_root,
        python_bin=python_bin,
        services={
            "server_backend_mc": {"host": host, "port": server_backend_mc_port},
            "server_backend_iperf": {"host": host, "port": server_backend_iperf_port},
        },
        notes={
            "sshd_running": sshd_running,
            "iperf3_installed": command_exists("iperf3"),
        },
    )
    write_yaml(SERVER_SNIPPET_PATH, snippet)

    print()
    print(f"已写入: {SERVER_SNIPPET_PATH}")
    print("把下面这些值留给 Windows 客户端脚本使用:")
    print(f"- server host: {host}")
    print(f"- server ssh_user: {ssh_user}")
    print(f"- server ssh_port: {ssh_port}")
    print(f"- server project_root: {project_root}")
    print(f"- server python_bin: {python_bin}")
    print(f"- server_backend_mc port: {server_backend_mc_port}")
    print(f"- server_backend_iperf port: {server_backend_iperf_port}")
    return 0


def run_relay_linux_quickstart() -> int:
    """Prepare a Linux relay node for beginner-friendly testing."""
    print("== mc-netprobe quickstart: relay Linux / FRPS ==")
    warn_if_platform_mismatch(expected="Linux")
    ensure_parent_dir(RELAY_SNIPPET_PATH)

    defaults = {
        "host": detect_local_ip(),
        "ssh_user": getpass.getuser(),
        "ssh_port": 22,
        "project_root": str(Path.cwd()),
        "python_bin": sys.executable,
        "relay_public_probe_port": 22,
        "mc_public_port": 25565,
        "iperf_public_port": 5201,
    }

    host = prompt_text("relay 对外给客户端访问的公网 IP 或域名", defaults["host"])
    ssh_user = prompt_text("relay 的 SSH 用户名", defaults["ssh_user"])
    ssh_port = prompt_int("relay 的 SSH 端口", defaults["ssh_port"])
    project_root = prompt_text("项目在 relay 上的绝对路径", defaults["project_root"])
    python_bin = prompt_text("relay 上运行项目用的 Python", defaults["python_bin"])
    relay_public_probe_port = prompt_int("客户端探测 relay 用的 TCP 端口", defaults["relay_public_probe_port"])
    mc_public_port = prompt_int("FRP 暴露给玩家的 Minecraft 端口", defaults["mc_public_port"])
    iperf_public_port = prompt_int("FRP 暴露给测速的 iperf3 端口", defaults["iperf_public_port"])

    print()
    print("预检查:")
    print(f"- Python: {sys.version.split()[0]}")
    print(f"- iperf3: {'已找到' if command_exists('iperf3') else '未找到'}")
    print(f"- ssh: {'已找到' if command_exists('ssh') else '未找到'}")
    sshd_running = process_running("sshd")
    frps_running = process_running("frps")
    print(f"- sshd: {'运行中' if sshd_running else '未检测到'}")
    print(f"- frps: {'运行中' if frps_running else '未检测到'}")
    if not sshd_running:
        print("  建议先开启 SSH 服务: sudo systemctl enable --now ssh")
    if not frps_running:
        maybe_start_background_service(
            prompt="如果 frps 还没启动，可输入启动命令；systemctl 命令会前台执行，普通命令会后台运行。直接回车跳过",
            log_name="linux-frps.log",
            success_port=None,
        )

    mc_public_open = is_local_port_open(mc_public_port)
    iperf_public_open = is_local_port_open(iperf_public_port)
    print(f"- mc_public 端口 {mc_public_port}: {'本机已监听' if mc_public_open else '本机未检测到监听'}")
    print(f"- iperf_public 端口 {iperf_public_port}: {'本机已监听' if iperf_public_open else '本机未检测到监听'}")

    snippet = build_node_setup_snippet(
        role="relay",
        host=host,
        os_name="linux",
        ssh_user=ssh_user,
        ssh_port=ssh_port,
        project_root=project_root,
        python_bin=python_bin,
        services={
            "relay_public_probe": {"host": host, "port": relay_public_probe_port},
            "mc_public": {"host": host, "port": mc_public_port},
            "iperf_public": {"host": host, "port": iperf_public_port},
        },
        notes={
            "sshd_running": sshd_running,
            "frps_running": process_running("frps"),
            "iperf3_installed": command_exists("iperf3"),
        },
    )
    write_yaml(RELAY_SNIPPET_PATH, snippet)

    print()
    print(f"已写入: {RELAY_SNIPPET_PATH}")
    print("把下面这些值留给 Windows 客户端脚本使用:")
    print(f"- relay host: {host}")
    print(f"- relay ssh_user: {ssh_user}")
    print(f"- relay ssh_port: {ssh_port}")
    print(f"- relay project_root: {project_root}")
    print(f"- relay python_bin: {python_bin}")
    print(f"- relay_public_probe port: {relay_public_probe_port}")
    print(f"- mc_public: {host}:{mc_public_port}")
    print(f"- iperf_public: {host}:{iperf_public_port}")
    return 0


def run_client_windows_quickstart() -> int:
    """Prepare a Windows client and optionally run a test immediately."""
    print("== mc-netprobe quickstart: Windows client ==")
    warn_if_platform_mismatch(expected="Windows")
    ensure_parent_dir(CLIENT_TOPOLOGY_PATH)

    relay_defaults = load_snippet_defaults(RELAY_SNIPPET_PATH)
    server_defaults = load_snippet_defaults(SERVER_SNIPPET_PATH)

    client_python_bin = prompt_text("Windows 客户端本机运行 Python", sys.executable)
    client_host = prompt_text("Windows 客户端本机地址，仅用于记录", detect_local_ip())

    print()
    print("[relay / FRPS 配置]")
    relay_host = prompt_text("relay 公网 IP 或域名", relay_defaults.get("host", ""))
    relay_ssh_user = prompt_text("relay SSH 用户名", relay_defaults.get("ssh_user", ""))
    relay_ssh_port = prompt_int("relay SSH 端口", int(relay_defaults.get("ssh_port", 22)))
    relay_project_root = prompt_text("relay 上的项目绝对路径", relay_defaults.get("project_root", ""))
    relay_python_bin = prompt_text("relay 上的 Python", relay_defaults.get("python_bin", "python3"))
    relay_public_probe_port = prompt_int("relay_public_probe TCP 端口", int(relay_defaults.get("services", {}).get("relay_public_probe", {}).get("port", 22)))

    print()
    print("[mac server 配置]")
    server_host = prompt_text("mac server 地址", server_defaults.get("host", ""))
    server_ssh_user = prompt_text("mac server SSH 用户名", server_defaults.get("ssh_user", ""))
    server_ssh_port = prompt_int("mac server SSH 端口", int(server_defaults.get("ssh_port", 22)))
    server_project_root = prompt_text("mac server 上的项目绝对路径", server_defaults.get("project_root", ""))
    server_python_bin = prompt_text("mac server 上的 Python", server_defaults.get("python_bin", "python3"))
    server_backend_mc_port = prompt_int("mac server backend Minecraft 端口", int(server_defaults.get("services", {}).get("server_backend_mc", {}).get("port", 25565)))
    server_backend_iperf_port = prompt_int("mac server backend iperf3 端口", int(server_defaults.get("services", {}).get("server_backend_iperf", {}).get("port", 5201)))

    print()
    print("[公网映射配置]")
    mc_public_host = prompt_text("玩家连接用的 mc_public 域名或 IP", relay_defaults.get("services", {}).get("mc_public", {}).get("host", relay_host))
    mc_public_port = prompt_int("mc_public 端口", int(relay_defaults.get("services", {}).get("mc_public", {}).get("port", 25565)))
    iperf_public_host = prompt_text("测速用的 iperf_public 域名或 IP", relay_defaults.get("services", {}).get("iperf_public", {}).get("host", relay_host))
    iperf_public_port = prompt_int("iperf_public 端口", int(relay_defaults.get("services", {}).get("iperf_public", {}).get("port", 5201)))

    topology = build_client_topology(
        client_host=client_host,
        client_python_bin=client_python_bin,
        relay_host=relay_host,
        relay_ssh_user=relay_ssh_user,
        relay_ssh_port=relay_ssh_port,
        relay_project_root=relay_project_root,
        relay_python_bin=relay_python_bin,
        relay_public_probe_port=relay_public_probe_port,
        server_host=server_host,
        server_ssh_user=server_ssh_user,
        server_ssh_port=server_ssh_port,
        server_project_root=server_project_root,
        server_python_bin=server_python_bin,
        mc_public_host=mc_public_host,
        mc_public_port=mc_public_port,
        iperf_public_host=iperf_public_host,
        iperf_public_port=iperf_public_port,
        server_backend_mc_port=server_backend_mc_port,
        server_backend_iperf_port=server_backend_iperf_port,
    )
    write_yaml(CLIENT_TOPOLOGY_PATH, topology)

    print()
    print(f"已写入: {CLIENT_TOPOLOGY_PATH}")
    print("默认会继续使用:")
    print("- config/thresholds.example.yaml")
    print("- config/scenarios.example.yaml")
    print(f"- Windows 客户端 iperf3: {'已找到' if command_exists('iperf3') else '未找到，吞吐测试会记为失败'}")

    if prompt_yes_no("现在立刻从 Windows 客户端发起一次测试吗", default=True):
        command = [
            client_python_bin,
            "main.py",
            "--topology",
            str(CLIENT_TOPOLOGY_PATH),
            "--thresholds",
            "config/thresholds.example.yaml",
            "--scenarios",
            "config/scenarios.example.yaml",
        ]
        print(f"执行: {shlex.join(command)}")
        result = subprocess.run(command, check=False)
        return int(result.returncode)
    return 0


def build_node_setup_snippet(
    role: str,
    host: str,
    os_name: str,
    ssh_user: str,
    ssh_port: int,
    project_root: str,
    python_bin: str,
    services: dict[str, dict[str, Any]],
    notes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a shareable snippet for a single node."""
    return {
        "role": role,
        "host": host,
        "os": os_name,
        "ssh_user": ssh_user,
        "ssh_port": ssh_port,
        "project_root": project_root,
        "python_bin": python_bin,
        "services": services,
        "notes": notes or {},
    }


def build_client_topology(
    *,
    client_host: str,
    client_python_bin: str,
    relay_host: str,
    relay_ssh_user: str,
    relay_ssh_port: int,
    relay_project_root: str,
    relay_python_bin: str,
    relay_public_probe_port: int,
    server_host: str,
    server_ssh_user: str,
    server_ssh_port: int,
    server_project_root: str,
    server_python_bin: str,
    mc_public_host: str,
    mc_public_port: int,
    iperf_public_host: str,
    iperf_public_port: int,
    server_backend_mc_port: int,
    server_backend_iperf_port: int,
) -> dict[str, Any]:
    """Build the Windows client topology file."""
    return {
        "project_name": "mc-frp-netprobe",
        "nodes": {
            "client": {
                "role": "client",
                "host": client_host,
                "os": "windows",
                "local": True,
                "python_bin": client_python_bin,
            },
            "relay": {
                "role": "relay",
                "host": relay_host,
                "os": "linux",
                "local": False,
                "ssh_user": relay_ssh_user,
                "ssh_port": relay_ssh_port,
                "project_root": relay_project_root,
                "python_bin": relay_python_bin,
            },
            "server": {
                "role": "server",
                "host": server_host,
                "os": "macos",
                "local": False,
                "ssh_user": server_ssh_user,
                "ssh_port": server_ssh_port,
                "project_root": server_project_root,
                "python_bin": server_python_bin,
            },
        },
        "services": {
            "relay_public_probe": {"host": relay_host, "port": relay_public_probe_port},
            "mc_public": {"host": mc_public_host, "port": mc_public_port},
            "iperf_public": {"host": iperf_public_host, "port": iperf_public_port},
            "server_backend_mc": {"host": server_host, "port": server_backend_mc_port},
            "server_backend_iperf": {"host": server_host, "port": server_backend_iperf_port},
        },
    }


def prompt_text(prompt: str, default: str, allow_empty: bool = False) -> str:
    """Prompt for a text value with a default."""
    suffix = f" [{default}]" if default else ""
    while True:
        value = input(f"{prompt}{suffix}: ").strip()
        if value:
            return value
        if default:
            return default
        if allow_empty:
            return ""
        print("这个值不能为空。")


def prompt_int(prompt: str, default: int) -> int:
    """Prompt for an integer with validation."""
    while True:
        value = input(f"{prompt} [{default}]: ").strip()
        if not value:
            return default
        try:
            return int(value)
        except ValueError:
            print("请输入整数。")


def prompt_yes_no(prompt: str, default: bool) -> bool:
    """Prompt for a yes/no answer."""
    suffix = "Y/n" if default else "y/N"
    answer = input(f"{prompt} [{suffix}]: ").strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes", "1", "true"}


def detect_local_ip() -> str:
    """Best-effort discovery of the machine's likely LAN IP."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        sock.close()


def command_exists(name: str) -> bool:
    """Return whether a command is available on PATH."""
    return shutil_which(name) is not None


def shutil_which(name: str) -> str | None:
    """Local wrapper to avoid importing shutil at module top for small scripts."""
    from shutil import which

    return which(name)


def process_running(process_name: str) -> bool:
    """Best-effort process existence check on POSIX systems."""
    try:
        result = subprocess.run(
            ["pgrep", "-x", process_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except OSError:
        return False


def is_local_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Return whether a local TCP port is currently accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return True
    except OSError:
        return False


def maybe_start_background_service(prompt: str, log_name: str, success_port: int | None) -> None:
    """Optionally start a user-provided service command."""
    command = input(f"{prompt}: ").strip()
    if not command:
        return

    ensure_parent_dir(QUICKSTART_LOG_DIR / log_name)
    if "systemctl" in command or command.startswith("service "):
        result = subprocess.run(command, shell=True, check=False)
        if result.returncode != 0:
            print(f"启动命令退出码: {result.returncode}")
        return

    log_path = QUICKSTART_LOG_DIR / log_name
    with log_path.open("a", encoding="utf-8") as handle:
        process = subprocess.Popen(  # noqa: S602
            command,
            shell=True,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    print(f"已后台启动，PID={process.pid}，日志: {log_path}")
    if success_port is not None:
        time.sleep(2.0)
        print(f"端口 {success_port}: {'已监听' if is_local_port_open(success_port) else '仍未检测到监听'}")


def ensure_parent_dir(path: Path) -> None:
    """Create parent directories for a file path."""
    path.parent.mkdir(parents=True, exist_ok=True)


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    """Write a YAML file preserving field order."""
    ensure_parent_dir(path)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_snippet_defaults(path: Path) -> dict[str, Any]:
    """Load generated defaults when present."""
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return {}
    return raw


def warn_if_platform_mismatch(expected: str) -> None:
    """Print a soft warning when the script is being executed on the wrong OS."""
    actual = platform.system()
    if actual != expected:
        print(f"警告: 当前系统是 {actual}，这个脚本原本是给 {expected} 用的。继续执行通常也没问题，但自动检查可能不准确。")


if __name__ == "__main__":
    raise SystemExit(main())
