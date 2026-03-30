"""WebREPL command execution helper for ESP32 boards over WiFi.

Executes MicroPython commands on boards via the WebREPL websocket protocol.
Uses raw paste mode (MicroPython v1.14+) which provides device-side flow
control and supports commands of any length. Falls back to legacy 64-byte
chunked mode for older firmware (commands must be ≤255 bytes in that case).

Raw paste mode protocol:
  1. Ctrl-B  — ensure interactive REPL (exit stuck raw REPL from prior failed session)
  2. Ctrl-A  — enter raw REPL; board replies with text banner ending ">"
  3. Client sends \x05A\x01 — request raw paste mode
  4. Board replies R\x01 + 2-byte little-endian window size + \x01 flow-control token
  5. Client sends up to window bytes; waits for \x01 before each subsequent window
  6. Client sends \x04 to trigger execution
  7. Board replies \x04<output>\x04<errors>\x04>

Reference: https://github.com/micropython/micropython/issues/16997
           MicroPython stdin ring buffer is 260 bytes (ports/esp32/mphalport.c);
           commands >255 bytes in legacy mode overflow it silently.

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
        header = b""
        while len(header) < 2:
            chunk = sock.recv(2 - len(header))
            if not chunk:
                return b""
            header += chunk

        fl, sz = struct.unpack(">BB", header)

        if sz == 126:
            ext = b""
            while len(ext) < 2:
                chunk = sock.recv(2 - len(ext))
                if not chunk:
                    return b""
                ext += chunk
            (sz,) = struct.unpack(">H", ext)

        payload = b""
        while len(payload) < sz:
            chunk = sock.recv(sz - len(payload))
            if not chunk:
                break
            payload += chunk

        if fl in (_FRAME_TXT, _FRAME_BIN):
            return payload


# ── Buffered reader ──────────────────────────────────────────────────────

class _Reader:
    """Buffered byte reader over WebSocket frames.

    Accumulates frame payloads into an internal buffer so callers can read
    exact byte counts or scan for markers without losing bytes that arrived
    in the same frame as other data. Required for raw paste mode where
    flow-control bytes (\x01) and response bytes arrive in the same stream
    as command output.
    """

    def __init__(self, sock):
        self._sock = sock
        self._buf = b""

    def read(self, n: int) -> bytes:
        """Read exactly n bytes, accumulating frames as needed."""
        while len(self._buf) < n:
            frame = _ws_read_frame(self._sock)
            if not frame:
                break
            self._buf += frame
        result = self._buf[:n]
        self._buf = self._buf[n:]
        return result

    def read_until(self, marker: bytes, max_bytes: int = 8192) -> bytes:
        """Accumulate frames until marker is found or max_bytes exceeded.

        Returns bytes up to and including the marker; any bytes after the
        marker are retained in the buffer for subsequent reads.
        """
        while marker not in self._buf and len(self._buf) < max_bytes:
            frame = _ws_read_frame(self._sock)
            if not frame:
                break
            self._buf += frame
        idx = self._buf.find(marker)
        if idx >= 0:
            end = idx + len(marker)
            result, self._buf = self._buf[:end], self._buf[end:]
            return result
        result, self._buf = self._buf, b""
        return result

    def unread(self, data: bytes) -> None:
        """Push bytes back to the front of the buffer."""
        self._buf = data + self._buf


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
    """Read frames until 'Password: ' prompt appears, send password, drain banner.

    Also drains the post-login banner ('\r\nWebREPL connected\r\n>>> ') so the
    buffer is clean when _exec_raw_repl starts.
    """
    buf = b""
    while b"Password: " not in buf:
        frame = _ws_read_frame(sock)
        if not frame:
            break
        buf += frame
    _ws_write_frame(sock, password.encode("utf-8") + b"\r", _FRAME_TXT)
    # Drain post-login banner (\r\nWebREPL connected\r\n>>> )
    buf = b""
    while b">>> " not in buf:
        frame = _ws_read_frame(sock)
        if not frame:
            break
        buf += frame


# ── Raw REPL execution ───────────────────────────────────────────────────

def _exec_raw_repl(sock, command: str) -> str:
    """Enter raw REPL, execute command, return output string.

    Protocol (MicroPython v1.14+ on ESP32):
      1. Ctrl-B  — exit raw REPL if a previous session left the board stuck there
      2. Ctrl-A  — enter raw REPL; board replies with text banner ending in ">"
      3. \x05A\x01 — request raw paste mode; board replies R\x01 + 2-byte window + \x01
      4. Send command in window-sized chunks; board sends \x01 flow-control between each
      5. \x04    — trigger execution
      6. Response: \x04<stdout>\x04<stderr>\x04>  (raw paste format)

    Falls back to legacy 64-byte chunked mode if raw paste is unavailable.
    """
    reader = _Reader(sock)
    data = command.encode("utf-8")

    # Step 1: Ctrl-B — ensure interactive REPL (recovers from stuck raw REPL state)
    _ws_write_frame(sock, b"\x02", _FRAME_TXT)
    reader.read_until(b">>> ")

    # Step 2: Ctrl-A — enter raw REPL; drain text banner to ">"
    _ws_write_frame(sock, b"\x01", _FRAME_TXT)
    reader.read_until(b"raw REPL; CTRL-B to exit\r\n>")

    # Step 3: \x05A\x01 — request raw paste mode
    _ws_write_frame(sock, b"\x05A\x01", _FRAME_TXT)
    resp = reader.read(2)
    if resp == b"R\x01":
        window = struct.unpack("<H", reader.read(2))[0]
        reader.read(1)  # consume initial \x01 flow-control token
    else:
        window = 0

    # Step 4: Send command
    if window:
        # Raw paste mode: send in window-sized chunks, wait for \x01 between each
        i = 0
        while i < len(data):
            chunk = data[i:i + window]
            _ws_write_frame(sock, chunk, _FRAME_TXT)
            i += len(chunk)
            if i < len(data):
                reader.read(1)  # wait for \x01 flow-control token
    else:
        # Legacy fallback: 64-byte chunks (works for commands ≤255 bytes only)
        for j in range(0, len(data), 64):
            _ws_write_frame(sock, data[j:j + 64], _FRAME_TXT)

    # Step 5: Ctrl-D triggers execution
    _ws_write_frame(sock, b"\x04", _FRAME_TXT)

    # Step 6: Parse response
    # Raw paste format: \x04<stdout>\x04<stderr>\x04>
    # Legacy format:    OK<stdout>\x04<errors>\x04>
    raw = reader.read_until(b"\x04>")
    text = raw.decode("utf-8", errors="replace")

    ok_idx = text.find("OK")
    if ok_idx >= 0:
        # Legacy format: skip "OK" prefix
        text = text[ok_idx + 2:]
    elif text.startswith("\x04"):
        # Raw paste format: skip leading \x04 separator
        text = text[1:]

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
