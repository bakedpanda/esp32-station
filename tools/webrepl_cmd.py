"""WebREPL command execution helper for ESP32 boards over WiFi.

Executes MicroPython commands on boards via the WebREPL websocket protocol.
Reads complete WebSocket frames (stripping headers) before scanning for
markers, so multi-frame responses are handled correctly regardless of how
MicroPython splits output across frames.

Requirements covered: STAT-01 (WiFi path), STAT-02 (WiFi path).
"""
import socket
import struct

# ── Constants ────────────────────────────────────────────────────────────
WEBREPL_PORT = 8266
_FRAME_TXT = 0x81
_FRAME_BIN = 0x82


# ── WebSocket frame I/O ──────────────────────────────────────────────────

def _ws_write_frame(sock, data: bytes, frame_type: int = _FRAME_BIN):
    """Send data as a single WebSocket frame."""
    l = len(data)
    if l < 126:
        hdr = struct.pack(">BB", frame_type, l)
    else:
        hdr = struct.pack(">BBH", frame_type, 126, l)
    sock.send(hdr)
    sock.send(data)


def _ws_read_frame(sock) -> bytes:
    """Read one complete WebSocket frame and return its payload bytes only.

    Skips frames with unexpected opcodes (e.g. ping/pong). Returns b"" if
    the socket is closed or no data arrives.
    """
    while True:
        # Read 2-byte frame header
        header = b""
        while len(header) < 2:
            chunk = sock.recv(2 - len(header))
            if not chunk:
                return b""
            header += chunk

        fl, sz = struct.unpack(">BB", header)

        # Extended 16-bit payload length
        if sz == 126:
            ext = b""
            while len(ext) < 2:
                chunk = sock.recv(2 - len(ext))
                if not chunk:
                    return b""
                ext += chunk
            (sz,) = struct.unpack(">H", ext)

        # Read payload
        payload = b""
        while len(payload) < sz:
            chunk = sock.recv(sz - len(payload))
            if not chunk:
                break
            payload += chunk

        # Accept text (0x81) and binary (0x82) frames; skip anything else
        if fl in (_FRAME_TXT, _FRAME_BIN):
            return payload
        # Unknown frame type — discard and read the next one


def _read_until(sock, marker: bytes, max_bytes: int = 8192) -> bytes:
    """Accumulate decoded WebSocket frame payloads until marker is found.

    Reads complete frames so that markers split across frame boundaries
    are still detected correctly.
    """
    buf = b""
    while marker not in buf and len(buf) < max_bytes:
        frame = _ws_read_frame(sock)
        if not frame:
            break
        buf += frame
    return buf


# ── Handshake & login ────────────────────────────────────────────────────

def _client_handshake(sock):
    """HTTP WebSocket upgrade (MicroPython WebREPL variant).

    Uses makefile for line-by-line header reading — matches the approach
    in tools/vendor/webrepl_cli.py which is known to work in production.
    """
    cl = sock.makefile("rwb", 0)
    cl.write(
        b"GET / HTTP/1.1\r\n"
        b"Host: echo.websocket.org\r\n"
        b"Connection: Upgrade\r\n"
        b"Upgrade: websocket\r\n"
        b"Sec-WebSocket-Key: foo\r\n"
        b"\r\n"
    )
    cl.readline()  # HTTP/1.1 101 Switching Protocols
    while True:
        l = cl.readline()
        if l == b"\r\n":
            break


def _login(sock, password: str):
    """Read frames until 'Password: ' prompt appears, then send password."""
    _read_until(sock, b"Password: ")
    _ws_write_frame(sock, password.encode("utf-8") + b"\r", _FRAME_TXT)


# ── Raw REPL execution ───────────────────────────────────────────────────

def _exec_raw_repl(sock, command: str) -> str:
    """Enter raw REPL, execute command, return output string."""
    # Enter raw REPL (Ctrl-A)
    _ws_write_frame(sock, b"\x01", _FRAME_TXT)
    # Consume any post-login banner then wait for raw REPL prompt ">"
    _read_until(sock, b">")

    # Send command in <=64-byte chunks to avoid extended-length WebSocket frames.
    # MicroPython's WebREPL handles large binary frames (OTA uses 1024-byte chunks)
    # but may not handle extended-length text frames (> 125 bytes) correctly.
    data = command.encode("utf-8")
    for i in range(0, len(data), 64):
        _ws_write_frame(sock, data[i:i + 64], _FRAME_TXT)
    # Ctrl-D triggers execution
    _ws_write_frame(sock, b"\x04", _FRAME_TXT)

    # Response format: OK<output>\x04<errors>\x04>
    raw = _read_until(sock, b"\x04>")
    text = raw.decode("utf-8", errors="replace")

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
        s = socket.socket()
        ai = socket.getaddrinfo(host, port)
        addr = ai[0][4]
        s.settimeout(timeout)
        s.connect(addr)
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
        _client_handshake(s)
        _login(s, password)
        output = _exec_raw_repl(s, command)
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
            s.close()
        except Exception:
            pass
