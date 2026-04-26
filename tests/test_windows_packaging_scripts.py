from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_SCRIPT = ROOT / "clients" / "windows" / "scripts" / "package-windows-client.ps1"
VALIDATE_SCRIPT = ROOT / "clients" / "windows" / "scripts" / "validate-windows-client.ps1"
README = ROOT / "clients" / "windows" / "README-WINDOWS.md"


def test_package_script_names_expected_zip_entries() -> None:
    text = PACKAGE_SCRIPT.read_text(encoding="utf-8")
    for entry in [
        "mc-netprobe-tray.exe",
        "mc-netprobe-service.exe",
        "mc-netprobe-elevate.exe",
        "python",
        "repo",
        "templates",
    ]:
        assert entry in text


def test_validate_script_checks_service_firewall_and_no_console_window_claim() -> None:
    text = VALIDATE_SCRIPT.read_text(encoding="utf-8")
    assert "Get-Service -Name mc-netprobe-client" in text
    assert "Get-NetFirewallRule" in text
    assert "Get-Process" in text


def test_windows_readme_documents_program_data_runtime() -> None:
    text = README.read_text(encoding="utf-8")
    assert "C:\\ProgramData\\mc-netprobe\\client" in text
    assert "Open Config File" in text
    assert "Open Logs Folder" in text
