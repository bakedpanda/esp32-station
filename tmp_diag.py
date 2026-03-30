"""Step-by-step WebREPL diagnostic — tests raw paste execution with a short command."""
import socket, struct, sys, time
sys.path.insert(0, '.')
from tools.credentials import load_credentials

creds = load_credentials()
host = sys.argv[1] if len(sys.argv) > 1 else input("ESP32 IP: ").strip()
pw = creds["webrepl_password"]
PORT = 8266

def ws_write(sock, data, ftype=0x81):
    l = len(data)
    hdr = struct.pack(">BB", ftype, l) if l < 126 else struct.pack(">BBH", ftype, 126, l)
    sent = sock.send(hdr + data)
    print(f"  ws_write: sent {sent} bytes (payload={data!r})")

def ws_read_frame(sock):
    header = b""
    while len(header) < 2:
        chunk = sock.recv(2 - len(header))
        if not chunk: return b""
        header += chunk
    fl, sz = struct.unpack(">BB", header)
    if sz == 126:
        ext = b""
        while len(ext) < 2:
            chunk = sock.recv(2 - len(ext))
            if not chunk: return b""
            ext += chunk
        sz, = struct.unpack(">H", ext)
    payload = b""
    while len(payload) < sz:
        chunk = sock.recv(sz - len(payload))
        if not chunk: break
        payload += chunk
    return payload if fl in (0x81, 0x82) else b""

def read_frames_until(sock, marker, label, timeout=5):
    """Read frames until marker found, printing each frame."""
    sock.settimeout(timeout)
    buf = b""
    try:
        while marker not in buf:
            f = ws_read_frame(sock)
            print(f"  [{label}] frame: {f!r}")
            if not f: break
            buf += f
    except socket.timeout:
        print(f"  [{label}] TIMEOUT waiting for {marker!r}")
    return buf

def read_n_bytes(sock, n, label, timeout=5):
    """Read exactly n bytes across frames, printing each frame."""
    sock.settimeout(timeout)
    buf = b""
    try:
        while len(buf) < n:
            f = ws_read_frame(sock)
            print(f"  [{label}] frame: {f!r}")
            if not f: break
            buf += f
    except socket.timeout:
        print(f"  [{label}] TIMEOUT after {len(buf)}/{n} bytes")
    return buf

# Connect
s = socket.socket()
ai = socket.getaddrinfo(host, PORT)
s.settimeout(10)
s.connect(ai[0][4])

# HTTP upgrade
cl = s.makefile("rwb", 0)
cl.write(b"GET / HTTP/1.1\r\nHost: echo.websocket.org\r\nConnection: Upgrade\r\nUpgrade: websocket\r\nSec-WebSocket-Key: foo\r\n\r\n")
cl.readline()
while True:
    l = cl.readline()
    if l == b"\r\n": break

# Login
print("\n=== LOGIN ===")
buf = read_frames_until(s, b"Password: ", "login")
print(f"  Sending password...")
ws_write(s, pw.encode() + b"\r")

# Drain post-login frames (banner, REPL prompt)
print("\n=== POST-LOGIN DRAIN ===")
s.settimeout(3)
post_login = b""
try:
    while True:
        f = ws_read_frame(s)
        print(f"  [drain] frame: {f!r}")
        post_login += f
        if b">>> " in post_login:
            print("  -> Got >>> prompt, stopping drain")
            break
except socket.timeout:
    print("  -> Drain timed out (no >>> prompt seen)")

# Ctrl-B: exit raw REPL (in case a previous session left board in raw REPL mode)
print("\n=== CTRL-B (exit raw REPL -> interactive) ===")
ws_write(s, b"\x02")
ctrlb = read_frames_until(s, b">>> ", "ctrl-b", timeout=5)
print(f"  Response: {ctrlb!r}")
if b">>> " not in ctrlb:
    print("  No >>> after Ctrl-B (board may already be in interactive mode or blocked)")

# Ctrl-C: interrupt any running user code
print("\n=== CTRL-C (interrupt running code) ===")
ws_write(s, b"\r\x03")
ctrlc = read_frames_until(s, b">>> ", "ctrl-c", timeout=5)
print(f"  Response: {ctrlc!r}")
if b">>> " not in ctrlc:
    print("  No >>> after Ctrl-C — board may be hard-blocked")
    s.close()
    sys.exit(1)
print("  Got >>> prompt, REPL is in interactive mode")

time.sleep(0.1)

# Send Ctrl-A — old protocol: text banner, then \x05A for raw paste negotiation
print("\n=== CTRL-A (enter raw REPL) ===")
ws_write(s, b"\x01")
banner = read_frames_until(s, b"raw REPL; CTRL-B to exit\r\n>", "banner", timeout=5)
print(f"  Banner: {banner!r}")
if b"raw REPL; CTRL-B to exit" not in banner:
    print("  ERROR: did not get raw REPL banner")
    s.close()
    sys.exit(1)
print("  Got raw REPL banner")

# Send \x05A\x01 to request raw paste mode (\x01 is required part of the request)
print("\n=== \\x05A\\x01 (raw paste request) ===")
ws_write(s, b"\x05A\x01")
paste_resp = read_n_bytes(s, 2, "paste-resp", timeout=5)
print(f"  First 2 bytes: {paste_resp!r}")

if paste_resp == b"R\x01":
    # Raw paste accepted — read 2-byte window + 1-byte flow-ctl
    rest = read_n_bytes(s, 3, "paste-window", timeout=5)
    print(f"  Next 3 bytes: {rest!r}")
    window = struct.unpack("<H", rest[:2])[0]
    flow = rest[2:3]
    print(f"  Raw paste ACCEPTED, window={window}, flow_ctrl={flow!r}")

    cmd = b"print(1)"
    print(f"\n=== SEND COMMAND: {cmd!r} ({len(cmd)} bytes) ===")
    ws_write(s, cmd)

    print("\n=== CTRL-D (trigger execution) ===")
    ws_write(s, b"\x04")

    print("\n=== READING RESPONSE (expecting OK1\\x04\\x04>) ===")
    resp2 = read_frames_until(s, b"\x04>", "exec-resp", timeout=5)
    print(f"\n  Full response: {resp2!r}")
    if b"OK" in resp2:
        idx = resp2.find(b"OK")
        body = resp2[idx+2:]
        end = body.find(b"\x04")
        output = body[:end].decode("utf-8", errors="replace") if end >= 0 else body.decode("utf-8", errors="replace")
        print(f"  Parsed output: {output!r}")
    else:
        print("  No OK marker found in response")

elif paste_resp == b"R\x00":
    print("  Raw paste NOT supported — firmware too old")
else:
    print(f"  Unexpected paste response: {paste_resp!r}")

s.close()
