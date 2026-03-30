"""Tests for WebREPL command execution helper: webrepl_exec."""
import socket
import struct
import pytest
from unittest.mock import patch, MagicMock

from tools.webrepl_cmd import webrepl_exec, WEBREPL_PORT


HOST = "192.168.1.42"
PASSWORD = "testpass"
COMMAND = "print(1)"

# Raw paste mode window size used in test mocks (256 bytes as little-endian uint16)
_WINDOW = struct.pack("<H", 256)


def _frame(data: bytes, ftype: int = 0x81) -> bytes:
    """Build a minimal (unmasked) WebSocket frame."""
    l = len(data)
    hdr = struct.pack(">BB", ftype, l) if l < 126 else struct.pack(">BBH", ftype, 126, l)
    return hdr + data


def _make_mock_sock(ws_payload: bytes):
    """Return a mock socket whose recv feeds ws_payload, and makefile returns HTTP 101."""
    buf = bytearray(ws_payload)
    mock_sock = MagicMock()

    def recv(sz):
        chunk = bytes(buf[:sz])
        del buf[:sz]
        return chunk

    mock_sock.recv = recv

    # makefile is used only for the HTTP handshake (readline loop)
    mock_file = MagicMock()
    mock_file.readline.side_effect = [
        b"HTTP/1.1 101 Switching Protocols\r\n",
        b"Upgrade: websocket\r\n",
        b"\r\n",
    ]
    mock_sock.makefile.return_value = mock_file
    return mock_sock


# ── webrepl_exec tests ───────────────────────────────────────────────────


def test_webrepl_exec_success():
    """webrepl_exec returns {"output": "1"} on successful command execution.

    Frame sequence (each a complete WebSocket frame):
      1. Text frame: "Password: "              — login prompt
      2. Text frame: raw REPL banner + ">"     — raw REPL entry
      3. Text frame: "R\\x00" + window (2 bytes) — raw paste mode accepted
      4. Text frame: "OK1\\n\\x04\\x04>"           — command output + end markers
    """
    ws_payload = (
        _frame(b"Password: ")
        + _frame(b"raw REPL; CTRL-B to exit\r\n>")
        + _frame(b"R\x00" + _WINDOW)
        + _frame(b"OK1\n\x04\x04>")
    )
    mock_sock = _make_mock_sock(ws_payload)

    with patch("socket.socket", return_value=mock_sock), \
         patch("socket.getaddrinfo", return_value=[(None, None, None, None, (HOST, WEBREPL_PORT))]):
        result = webrepl_exec(HOST, PASSWORD, COMMAND, timeout=5)

    assert "error" not in result
    assert result.get("output") == "1"


def test_webrepl_exec_multiframe_output():
    """webrepl_exec correctly assembles output split across multiple WebSocket frames.

    Simulates long output where MicroPython splits the response:
      - Frame for "OK" prefix
      - Frame for JSON payload + first \\x04
      - Frame for second \\x04
      - Frame for final ">" prompt
    All four payloads must be assembled before \\x04> is detected.
    """
    json_output = b'{"firmware": "1.21.0", "wifi_connected": true}'
    ws_payload = (
        _frame(b"Password: ")
        + _frame(b"raw REPL; CTRL-B to exit\r\n>")
        + _frame(b"R\x00" + _WINDOW)
        + _frame(b"OK")
        + _frame(json_output + b"\x04")
        + _frame(b"\x04")
        + _frame(b">")
    )
    mock_sock = _make_mock_sock(ws_payload)

    with patch("socket.socket", return_value=mock_sock), \
         patch("socket.getaddrinfo", return_value=[(None, None, None, None, (HOST, WEBREPL_PORT))]):
        result = webrepl_exec(HOST, PASSWORD, "import json; print(json.dumps({}))", timeout=5)

    assert "error" not in result
    assert "firmware" in result.get("output", "")


def test_webrepl_exec_legacy_fallback():
    """webrepl_exec falls back to legacy chunked mode when raw paste is not supported.

    Simulates older firmware that does not respond with R\\x00 to \\x05A.
    Legacy mode sends the command in 64-byte chunks followed by Ctrl-D.
    """
    ws_payload = (
        _frame(b"Password: ")
        + _frame(b"raw REPL; CTRL-B to exit\r\n>")
        + _frame(b"\x01\x00")   # not R\x00 — raw paste not supported
        + _frame(b"OK1\n\x04\x04>")
    )
    mock_sock = _make_mock_sock(ws_payload)

    with patch("socket.socket", return_value=mock_sock), \
         patch("socket.getaddrinfo", return_value=[(None, None, None, None, (HOST, WEBREPL_PORT))]):
        result = webrepl_exec(HOST, PASSWORD, COMMAND, timeout=5)

    assert "error" not in result
    assert result.get("output") == "1"


def test_webrepl_exec_timeout_on_connect():
    """webrepl_exec returns wifi_timeout when socket.connect times out."""
    mock_sock = MagicMock()
    mock_sock.connect.side_effect = socket.timeout("timed out")

    with patch("socket.socket", return_value=mock_sock), \
         patch("socket.getaddrinfo", return_value=[(None, None, None, None, (HOST, WEBREPL_PORT))]):
        result = webrepl_exec(HOST, PASSWORD, COMMAND, timeout=5)

    assert result["error"] == "wifi_timeout"
    assert HOST in result["detail"]


def test_webrepl_exec_unreachable():
    """webrepl_exec returns wifi_unreachable when socket.connect raises OSError."""
    mock_sock = MagicMock()
    mock_sock.connect.side_effect = OSError("Connection refused")

    with patch("socket.socket", return_value=mock_sock), \
         patch("socket.getaddrinfo", return_value=[(None, None, None, None, (HOST, WEBREPL_PORT))]):
        result = webrepl_exec(HOST, PASSWORD, COMMAND, timeout=5)

    assert result["error"] == "wifi_unreachable"
    assert HOST in result["detail"]


def test_webrepl_exec_missing_password():
    """webrepl_exec returns invalid_params error when password is empty or None."""
    result_none = webrepl_exec(HOST, None, COMMAND)
    assert result_none["error"] == "invalid_params"
    assert "password" in result_none["detail"].lower()

    result_empty = webrepl_exec(HOST, "", COMMAND)
    assert result_empty["error"] == "invalid_params"
    assert "password" in result_empty["detail"].lower()
