"""WebREPL command execution helper for ESP32 boards over WiFi.

Executes MicroPython commands on boards via the WebREPL websocket protocol.
Uses raw sockets (stdlib only) to implement the minimal websocket handshake
matching MicroPython's WebREPL server.

Requirements covered: STAT-01 (WiFi path), STAT-02 (WiFi path).
"""
import socket
import struct

# ── Constants ────────────────────────────────────────────────────────────
WEBREPL_PORT = 8266


# ── Internal helpers ─────────────────────────────────────────────────────

def _ws_write_text(sock, data: bytes):
    """Send a websocket text frame (opcode 0x81)."""
    length = len(data)
    if length < 126:
        header = struct.pack(">BB", 0x81, length)
    else:
        header = struct.pack(">BBH", 0x81, 126, length)
    sock.sendall(header + data)


def _ws_read(sock, bufsize: int = 4096) -> bytes:
    """Read data from socket, returning raw bytes."""
    return sock.recv(bufsize)


def _read_until(sock, marker: bytes, max_bytes: int = 8192) -> bytes:
    """Read from socket until marker is found or max_bytes exceeded."""
    buf = b""
    while marker not in buf and len(buf) < max_bytes:
        chunk = sock.recv(1024)
        if not chunk:
            break
        buf += chunk
    return buf


def _do_handshake(sock):
    """Perform simplified websocket client handshake (matching webrepl_cli.py)."""
    handshake = (
        b"GET / HTTP/1.1\r\n"
        b"Host: echo.websocket.org\r\n"
        b"Connection: Upgrade\r\n"
        b"Upgrade: websocket\r\n"
        b"Sec-WebSocket-Key: foo\r\n"
        b"\r\n"
    )
    sock.sendall(handshake)
    # Read until blank line signals end of HTTP headers
    _read_until(sock, b"\r\n\r\n")


def _do_login(sock, password: str):
    """Wait for Password: prompt and send password."""
    _read_until(sock, b"Password: ")
    _ws_write_text(sock, password.encode("utf-8") + b"\r")
    # Read login response (success/fail message)
    _read_until(sock, b"\r\n")


def _exec_raw_repl(sock, command: str) -> str:
    """Enter raw REPL, execute command, return output string."""
    # Enter raw REPL mode (Ctrl-A)
    _ws_write_text(sock, b"\x01")
    _read_until(sock, b">")

    # Send command + Ctrl-D to execute
    _ws_write_text(sock, command.encode("utf-8") + b"\x04")

    # Read output: "OK<output>\x04>" pattern
    raw = _read_until(sock, b"\x04>")
    # Parse output between "OK" and "\x04"
    text = raw.decode("utf-8", errors="replace")

    # Extract output after "OK" and before the end marker
    ok_idx = text.find("OK")
    if ok_idx >= 0:
        text = text[ok_idx + 2:]
    end_idx = text.find("\x04")
    if end_idx >= 0:
        text = text[:end_idx]

    return text.strip()


# ── Public API ───────────────────────────────────────────────────────────

def webrepl_exec(host: str, password: str, command: str,
                 timeout: int = 15, port: int = WEBREPL_PORT) -> dict:
    """Execute a MicroPython command on a board via WebREPL websocket.

    Args:
        host:     Board's WiFi IP or hostname.
        password: WebREPL password (required, never stored).
        command:  MicroPython expression/statement to execute.
        timeout:  Connection and read timeout in seconds.
        port:     WebREPL port (default 8266).

    Returns:
        {"output": "..."} on success.
        {"error": "invalid_params", "detail": "..."} if password missing.
        {"error": "wifi_timeout", "detail": "..."} on timeout.
        {"error": "wifi_unreachable", "detail": "..."} on connection failure.
        {"error": "webrepl_exec_failed", "detail": "..."} on other errors.

    Never raises to callers.
    """
    if not password:
        return {
            "error": "invalid_params",
            "detail": "password required for WiFi command execution",
        }

    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.settimeout(timeout)
    except socket.timeout:
        return {
            "error": "wifi_timeout",
            "detail": f"WebREPL connection to {host} timed out after {timeout}s",
        }
    except OSError as e:
        return {
            "error": "wifi_unreachable",
            "detail": f"WebREPL connection to {host} failed: {e}",
        }

    try:
        _do_handshake(sock)
        _do_login(sock, password)
        output = _exec_raw_repl(sock, command)
        return {"output": output}
    except socket.timeout:
        return {
            "error": "wifi_timeout",
            "detail": f"WebREPL connection to {host} timed out after {timeout}s",
        }
    except OSError as e:
        return {
            "error": "wifi_unreachable",
            "detail": f"WebREPL connection to {host} failed: {e}",
        }
    except Exception as e:
        return {
            "error": "webrepl_exec_failed",
            "detail": str(e),
        }
    finally:
        try:
            sock.close()
        except Exception:
            pass
