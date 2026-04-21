from controller.quickstart import build_client_topology, build_node_setup_snippet


def test_build_node_setup_snippet() -> None:
    snippet = build_node_setup_snippet(
        role="server",
        host="192.168.1.20",
        os_name="macos",
        ssh_user="myuser",
        ssh_port=22,
        project_root="/Users/me/mc-netprobe",
        python_bin="/usr/bin/python3",
        services={"server_backend_mc": {"host": "127.0.0.1", "port": 25565}},
        notes={"sshd_running": True},
    )
    assert snippet["role"] == "server"
    assert snippet["services"]["server_backend_mc"]["port"] == 25565


def test_build_client_topology() -> None:
    topology = build_client_topology(
        client_host="192.168.1.8",
        client_python_bin="python",
        relay_host="relay.example.com",
        relay_ssh_user="ubuntu",
        relay_ssh_port=22,
        relay_project_root="/opt/mc-netprobe",
        relay_python_bin="python3",
        relay_public_probe_port=22,
        server_host="192.168.1.20",
        server_ssh_user="macuser",
        server_ssh_port=22,
        server_project_root="/Users/macuser/mc-netprobe",
        server_python_bin="/usr/bin/python3",
        mc_public_host="play.example.com",
        mc_public_port=25565,
        iperf_public_host="play.example.com",
        iperf_public_port=5201,
        server_backend_mc_port=25565,
        server_backend_iperf_port=5201,
    )
    assert topology["nodes"]["client"]["os"] == "windows"
    assert topology["nodes"]["relay"]["local"] is False
    assert topology["services"]["mc_public"]["host"] == "play.example.com"
