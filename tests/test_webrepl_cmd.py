"""Tests for WebREPL command execution helper: webrepl_exec."""
import socket
import pytest
from unittest.mock import patch, MagicMock


HOST = "192.168.1.42"
PASSWORD = "testpass"
COMMAND = "print(1)"


# ── webrepl_exec tests ───────────────────────────────────────────────────


def test_webrepl_exec_success():
    """webrepl_exec returns {"output": "..."} on successful command execution."""
    mock_sock = MagicMock()
    # Simulate websocket handshake response (HTTP upgrade) then password prompt then command output
    # The implementation reads lines until blank line (handshake), then reads until "Password:" (login),
    # then sends command in raw REPL mode and reads output.
    handshake_resp = b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n\r\n"
    password_prompt = b"Password: "
    # After login, we enter raw REPL: send \x01, get "raw REPL; CTRL-B to exit\n>",
    # send command + \x04, get "OK" + output + "\x04>" (end marker)
    raw_repl_prompt = b"raw REPL; CTRL-B to exit\r\n>"
    command_output = b"OK1\x04>"

    responses = [handshake_resp, password_prompt, raw_repl_prompt, command_output]
    call_idx = [0]

    def mock_recv(bufsize):
        if call_idx[0] < len(responses):
            data = responses[call_idx[0]]
            call_idx[0] += 1
            return data
        return b""

    mock_sock.recv = mock_recv
    mock_sock.sendall = MagicMock()

    with patch("socket.socket", return_value=mock_sock), \
         patch("socket.create_connection", return_value=mock_sock):
        from tools.webrepl_cmd import webrepl_exec
        result = webrepl_exec(HOST, PASSWORD, COMMAND, timeout=5)

    assert "output" in result
    assert "error" not in result


def test_webrepl_exec_timeout():
    """webrepl_exec returns wifi_timeout error on socket.timeout."""
    with patch("socket.create_connection", side_effect=socket.timeout("timed out")):
        from tools.webrepl_cmd import webrepl_exec
        result = webrepl_exec(HOST, PASSWORD, COMMAND, timeout=5)

    assert result["error"] == "wifi_timeout"
    assert HOST in result["detail"]


def test_webrepl_exec_unreachable():
    """webrepl_exec returns wifi_unreachable error on OSError."""
    with patch("socket.create_connection", side_effect=OSError("Connection refused")):
        from tools.webrepl_cmd import webrepl_exec
        result = webrepl_exec(HOST, PASSWORD, COMMAND, timeout=5)

    assert result["error"] == "wifi_unreachable"
    assert HOST in result["detail"]


def test_webrepl_exec_missing_password():
    """webrepl_exec returns invalid_params error when password is empty or None."""
    from tools.webrepl_cmd import webrepl_exec

    result_none = webrepl_exec(HOST, None, COMMAND)
    assert result_none["error"] == "invalid_params"
    assert "password" in result_none["detail"].lower()

    result_empty = webrepl_exec(HOST, "", COMMAND)
    assert result_empty["error"] == "invalid_params"
    assert "password" in result_empty["detail"].lower()
