"""Step-by-step WebREPL diagnostic — prints every frame received."""
import socket, struct, sys, time
sys.path.insert(0, '.')
from tools.credentials import load_credentials

creds = load_credentials()
host = input("ESP32 IP: ").strip()
pw = creds["webrepl_password"]
PORT = 8266

def ws_write(sock, data, ftype=0x81):
    l = len(data)
    hdr = struct.pack(">BB", ftype, l) if l < 126 else struct.pack(">BBH", ftype, 126, l)
    sock.send(hdr + data)

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

# Send Ctrl-A
print("\n=== CTRL-A (enter raw REPL) ===")
ws_write(s, b"\x01")
banner = read_frames_until(s, b"raw REPL; CTRL-B to exit\r\n>", "raw-banner", timeout=5)
print(f"  Full banner received: {banner!r}")

# Send \x05A (raw paste request)
print("\n=== \\x05A (raw paste request) ===")
ws_write(s, b"\x05A")
s.settimeout(5)
resp_buf = b""
try:
    while len(resp_buf) < 4:
        f = ws_read_frame(s)
        print(f"  [paste-resp] frame: {f!r}")
        if not f: break
        resp_buf += f
except socket.timeout:
    print("  TIMEOUT waiting for raw paste response")
print(f"  Response bytes: {resp_buf!r}")
if resp_buf[:2] == b"R\x00":
    window = struct.unpack("<H", resp_buf[2:4])[0]
    print(f"  Raw paste ACCEPTED, window={window}")
else:
    print(f"  Raw paste NOT accepted (got {resp_buf[:2]!r})")

s.close()
