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
