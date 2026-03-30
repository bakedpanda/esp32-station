"""WebREPL command execution helper for ESP32 boards over WiFi.

Executes MicroPython commands on boards via the WebREPL websocket protocol.
Uses the same websocket framing as tools/vendor/webrepl_cli.py to ensure
compatibility with MicroPython's WebREPL server.

Requirements covered: STAT-01 (WiFi path), STAT-02 (WiFi path).
"""
import socket
import struct

# ── Constants ────────────────────────────────────────────────────────────
WEBREPL_PORT = 8266
_FRAME_TXT = 0x81
_FRAME_BIN = 0x82


# ── WebSocket class (matches MicroPython's WebREPL server expectations) ──
# Adapted from tools/vendor/webrepl_cli.py to ensure frame compatibility.

class _WebSocket:
    def __init__(self, s):
        self.s = s
        self.buf = b""

    def write(self, data, frame=_FRAME_BIN):
        l = len(data)
        if l < 126:
            hdr = struct.pack(">BB", frame, l)
        else:
            hdr = struct.pack(">BBH", frame, 126, l)
        self.s.send(hdr)
        self.s.send(data)

    def _recvexactly(self, sz):
        res = b""
        while sz:
            data = self.s.recv(sz)
            if not data:
                break
            res += data
            sz -= len(data)
        return res

    def read(self, size, text_ok=False):
        if not self.buf:
            while True:
                hdr = self._recvexactly(2)
                assert len(hdr) == 2
                fl, sz = struct.unpack(">BB", hdr)
                if sz == 126:
                    hdr = self._recvexactly(2)
                    assert len(hdr) == 2
                    (sz,) = struct.unpack(">H", hdr)
                if fl == _FRAME_BIN:
                    break
                if text_ok and fl == _FRAME_TXT:
                    break
                # skip unexpected frame type
                while sz:
                    skip = self.s.recv(sz)
                    sz -= len(skip)
            data = self._recvexactly(sz)
            self.buf = data

        d = self.buf[:size]
        self.buf = self.buf[size:]
        return d

    def ioctl(self, req, val):
        assert req == 9 and val == 2


# ── Internal helpers ─────────────────────────────────────────────────────

def _client_handshake(sock):
    """HTTP WebSocket upgrade (MicroPython WebREPL variant).
    Uses makefile line-by-line reading to reliably consume HTTP headers."""
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


def _login(ws, password):
    """Wait for Password: prompt (byte-by-byte via ws.read) and send password."""
    while True:
        c = ws.read(1, text_ok=True)
        if c == b":":
            ws.read(1, text_ok=True)  # consume the space after ":"
            break
    ws.write(password.encode("utf-8") + b"\r")


def _read_until(ws, marker, max_bytes=8192):
    """Read bytes from websocket (proper frame decoding) until marker found."""
    buf = b""
    while marker not in buf and len(buf) < max_bytes:
        buf += ws.read(1, text_ok=True)
    return buf


def _exec_raw_repl(ws, command):
    """Enter raw REPL, execute command, return output string."""
    # Enter raw REPL mode (Ctrl-A) — use text frame
    ws.write(b"\x01", _FRAME_TXT)
    _read_until(ws, b">")

    # Send command + Ctrl-D to execute — use text frame
    ws.write(command.encode("utf-8") + b"\x04", _FRAME_TXT)

    # Response format: OK<output>\x04<error>\x04>
    raw = _read_until(ws, b"\x04>")
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
        ws = _WebSocket(s)
        _login(ws, password)
        ws.ioctl(9, 2)
        output = _exec_raw_repl(ws, command)
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
