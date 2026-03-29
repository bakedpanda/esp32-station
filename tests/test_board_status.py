"""Tests for board status collection and health check: get_status, check_health."""
import json
import pytest
from unittest.mock import patch, MagicMock


PORT = "/dev/ttyUSB0"
HOST = "192.168.1.42"
PASSWORD = "testpass"

STATUS_JSON = json.dumps({
    "firmware": "1.27.0",
    "wifi_connected": True,
    "ip_address": "192.168.1.42",
    "free_memory": 102400,
    "free_storage": 2097152,
    "board": "esp32",
})


# ── get_status tests ─────────────────────────────────────────────────────


def test_get_status_usb_success():
    """get_status(port=...) returns parsed status dict with transport='usb'."""
    with patch("tools.board_status.exec_repl", return_value={"port": PORT, "output": STATUS_JSON}):
        from tools.board_status import get_status
        result = get_status(port=PORT)

    assert result["firmware"] == "1.27.0"
    assert result["wifi_connected"] is True
    assert result["ip_address"] == "192.168.1.42"
    assert result["free_memory"] == 102400
    assert result["free_storage"] == 2097152
    assert result["board"] == "esp32"
    assert result["transport"] == "usb"
    assert "error" not in result


def test_get_status_wifi_success():
    """get_status(host=..., password=...) returns parsed status dict with transport='wifi'."""
    with patch("tools.board_status.webrepl_exec", return_value={"output": STATUS_JSON}):
        from tools.board_status import get_status
        result = get_status(host=HOST, password=PASSWORD)

    assert result["firmware"] == "1.27.0"
    assert result["transport"] == "wifi"
    assert "error" not in result


def test_get_status_parse_error():
    """get_status returns status_parse_failed when output is not valid JSON."""
    with patch("tools.board_status.exec_repl", return_value={"port": PORT, "output": "not json at all"}):
        from tools.board_status import get_status
        result = get_status(port=PORT)

    assert result["error"] == "status_parse_failed"
    assert "not json at all" in result["detail"]


def test_get_status_invalid_params_both():
    """get_status returns invalid_params when both port and host are provided."""
    from tools.board_status import get_status
    result = get_status(port=PORT, host=HOST)
    assert result["error"] == "invalid_params"


def test_get_status_invalid_params_neither():
    """get_status returns invalid_params when neither port nor host is provided."""
    from tools.board_status import get_status
    result = get_status()
    assert result["error"] == "invalid_params"


# ── check_health tests ──────────────────────────────────────────────────


def test_health_check_healthy_usb():
    """check_health(port=...) returns healthy when exec_repl succeeds."""
    mock_ports = [MagicMock(device=PORT)]
    with patch("tools.board_status.exec_repl", return_value={"port": PORT, "output": "1"}), \
         patch("tools.board_status.comports", return_value=mock_ports):
        from tools.board_status import check_health
        result = check_health(port=PORT)

    assert result["status"] == "healthy"


def test_health_check_unresponsive():
    """check_health returns unresponsive on repl_timeout error."""
    mock_ports = [MagicMock(device=PORT)]
    with patch("tools.board_status.exec_repl", return_value={"error": "repl_timeout", "detail": "command timed out after 5s"}), \
         patch("tools.board_status.comports", return_value=mock_ports):
        from tools.board_status import check_health
        result = check_health(port=PORT)

    assert result["status"] == "unresponsive"
    assert "detail" in result


def test_health_check_not_found():
    """check_health returns not_found when port is not in comports list."""
    with patch("tools.board_status.comports", return_value=[]):
        from tools.board_status import check_health
        result = check_health(port=PORT)

    assert result["status"] == "not_found"
    assert PORT in result["detail"]


def test_health_check_wifi_healthy():
    """check_health(host=..., password=...) returns healthy on success."""
    with patch("tools.board_status.webrepl_exec", return_value={"output": "1"}):
        from tools.board_status import check_health
        result = check_health(host=HOST, password=PASSWORD)

    assert result["status"] == "healthy"


def test_health_check_wifi_unreachable():
    """check_health returns not_found when wifi_unreachable error occurs."""
    with patch("tools.board_status.webrepl_exec", return_value={"error": "wifi_unreachable", "detail": "connection refused"}):
        from tools.board_status import check_health
        result = check_health(host=HOST, password=PASSWORD)

    assert result["status"] == "not_found"
    assert "detail" in result
