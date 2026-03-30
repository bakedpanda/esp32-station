"""Tests for README.md content — covers SETUP-03."""
import pathlib
import pytest

README = pathlib.Path("README.md")


def read_readme():
    return README.read_text()


def test_readme_exists():
    assert README.exists(), "README.md not found in project root"


@pytest.mark.parametrize("tool_name", [
    "list_connected_boards",
    "identify_chip",
    "flash_micropython",
    "get_board_state",
    "deploy_file_to_board",
    "deploy_directory_to_board",
    "exec_repl_command",
    "read_board_serial",
    "reset_board",
    "deploy_ota_wifi",
    "pull_and_deploy_github",
    "get_board_status",
    "check_board_health",
    "discover_boards",
    "deploy_boot_config",
])
def test_tool_in_readme(tool_name):
    assert tool_name in read_readme(), f"Tool '{tool_name}' missing from README"


@pytest.mark.parametrize("module_name", [
    "board_detection.py",
    "firmware_flash.py",
    "file_deploy.py",
    "repl.py",
    "serial_lock.py",
    "ota_wifi.py",
    "github_deploy.py",
    "board_status.py",
    "webrepl_cmd.py",
    "mdns_discovery.py",
    "credentials.py",
    "boot_deploy.py",
])
def test_module_in_readme_architecture(module_name):
    assert module_name in read_readme(), f"Module '{module_name}' missing from README architecture"


def test_mcp_registration_command():
    assert "claude mcp add --transport http esp32-station" in read_readme(), (
        "README missing canonical MCP registration command: "
        "'claude mcp add --transport http esp32-station'"
    )


def test_mcp_registration_hostname_note():
    content = read_readme()
    assert "hostname" in content, "README missing hostname substitution note"
    assert "IP" in content or "ip" in content, (
        "README missing IP address substitution note alongside hostname"
    )


def test_setup_sh_referenced_in_readme():
    assert "setup.sh" in read_readme(), (
        "README must reference setup.sh as the primary setup path (per D-11)"
    )


def test_phases_4_to_6_in_status_table():
    content = read_readme()
    assert "Phase 4" in content or "Hardening" in content, (
        "README status table missing Phase 4 / Hardening row"
    )
    assert "Phase 5" in content or "Board Status" in content, (
        "README status table missing Phase 5 / Board Status row"
    )
    assert "Phase 6" in content or "Provisioning" in content, (
        "README status table missing Phase 6 / Provisioning row"
    )
