from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "bin" / "install_client_agent.ps1"


def _script_lines() -> list[str]:
    return SCRIPT_PATH.read_text(encoding="utf-8").splitlines()


def test_install_client_agent_param_block_is_first_statement() -> None:
    lines = _script_lines()
    statements = [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]
    assert statements[0] == "param("


def test_install_client_agent_bridge_uses_bridge_log() -> None:
    bridge_line = next(line.strip() for line in _script_lines() if line.strip().startswith("$bridgeArgument = "))
    assert "$bridgeLog" in bridge_line
    assert "$agentLog" not in bridge_line
