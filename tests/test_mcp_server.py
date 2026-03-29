"""Tests for MCP server entry point: MCP-01, MCP-02, MCP-03."""
import pytest


def test_mcp_server_imports():
    """MCP-01/MCP-02: mcp_server.py imports without error and exposes FastMCP instance."""
    import mcp_server
    from mcp.server.fastmcp import FastMCP
    assert hasattr(mcp_server, "mcp")
    assert isinstance(mcp_server.mcp, FastMCP)


def test_mcp_server_name():
    """MCP-01: FastMCP instance is named 'esp32-station'."""
    import mcp_server
    assert mcp_server.mcp.name == "esp32-station"


def test_systemd_service_file_content():
    """MCP-03: esp32-station.service contains required systemd directives."""
    import pathlib
    service_path = pathlib.Path("esp32-station.service")
    assert service_path.exists(), "esp32-station.service not found in project root"
    content = service_path.read_text()
    assert "WantedBy=multi-user.target" in content
    assert "Restart=on-failure" in content
    assert "venv/bin/python3" in content
    assert "Type=simple" in content


def test_new_tools_registered():
    """MCP-04/MCP-05: All 5 new Phase 2 tools are registered in the FastMCP instance."""
    import mcp_server
    # FastMCP stores tools in ._tool_manager._tools (dict keyed by tool name)
    # Access via the internal registry — names must match @mcp.tool() function names
    tool_names = [t.name for t in mcp_server.mcp._tool_manager.list_tools()]
    expected = [
        "deploy_file_to_board",
        "deploy_directory_to_board",
        "exec_repl_command",
        "read_board_serial",
        "reset_board",
    ]
    for name in expected:
        assert name in tool_names, f"MCP tool '{name}' not registered"


def test_deploy_file_returns_error_dict_on_failure(monkeypatch):
    """MCP-05: deploy_file_to_board returns error dict (not exception) on board failure."""
    from unittest.mock import patch, MagicMock
    mock_result = MagicMock(returncode=1, stdout="", stderr="board unreachable")
    with patch("subprocess.run", return_value=mock_result):
        import mcp_server
        result = mcp_server.deploy_file_to_board("/dev/ttyUSB0", "/tmp/boot.py")
    assert "error" in result
    assert "detail" in result


def test_exec_repl_returns_error_dict_on_timeout(monkeypatch):
    """MCP-05: exec_repl_command returns error dict on timeout (no exception propagated)."""
    import subprocess
    from unittest.mock import patch
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="mpremote", timeout=10)):
        import mcp_server
        result = mcp_server.exec_repl_command("/dev/ttyUSB0", "print(1)", timeout=10)
    assert "error" in result
    assert result["error"] == "repl_timeout"
    assert "detail" in result


def test_reset_board_invalid_type():
    """MCP-05: reset_board returns error dict for invalid reset_type."""
    import mcp_server
    result = mcp_server.reset_board("/dev/ttyUSB0", reset_type="bogus")
    assert result["error"] == "invalid_reset_type"
    assert "detail" in result
