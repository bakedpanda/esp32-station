# Phase 1: Foundation & Infrastructure - Research

**Researched:** 2026-03-28
**Domain:** FastMCP / Python MCP server + esptool.py + systemd daemon on Raspberry Pi
**Confidence:** MEDIUM-HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| BOARD-01 | Claude can list all ESP32 boards currently connected via USB | pyserial `list_ports` + USB VID/PID filtering |
| BOARD-02 | Claude can identify the chip variant (ESP32, S2, S3, C3, C6) | esptool `chip_id` subprocess call; parse "Chip is ESP32-XX" from stdout |
| BOARD-03 | Claude can reset a board (soft and hard reset) | Phase 2 — mpremote reset commands; in scope here only as board state tracked in BOARD-04 |
| BOARD-04 | Board state persisted across MCP server restarts | `boards.json` file; load on startup, write on detection |
| FLASH-01 | Claude can flash MicroPython firmware onto a board via USB | esptool `write_flash` subprocess wrapper |
| FLASH-02 | Correct firmware variant auto-selected based on chip type | Chip→firmware URL mapping table in server config |
| FLASH-03 | Firmware images cached locally; network not required at flash time | Download-on-first-use to `~/.cache/esp32-station/firmware/`; TTL 7 days |
| FLASH-04 | Flash fails fast with clear error if chip cannot be identified | Pre-flight chip detection; structured error code `chip_id_failed` |
| FLASH-05 | Pre-flight check verifies board is responsive before flashing | `chip_id` command used as responsiveness probe |
| MCP-01 | MCP server runs as a persistent daemon on the Raspberry Pi | systemd unit file; `Type=simple`, `Restart=on-failure` |
| MCP-02 | MCP server reachable from Claude on the main machine over LAN (HTTP) | FastMCP `transport="streamable-http"`, `host="0.0.0.0"`, port 8000 |
| MCP-03 | MCP server starts automatically on Pi boot via systemd | `WantedBy=multi-user.target`; `systemctl enable` |
</phase_requirements>

---

## Summary

Phase 1 builds the minimal server skeleton that proves every component can be wired together end-to-end: a FastMCP HTTP server running on the Pi under systemd, esptool subprocess calls for chip detection and firmware flashing, firmware downloaded once and cached locally, and board inventory persisted to JSON. No file deployment (Phase 2), no REPL (Phase 2), no concurrency hardening beyond avoiding obvious collisions.

The primary research finding is a **critical stack update**: the prior project research was written before two breaking changes became current. First, the official Claude Code MCP client now marks SSE as **deprecated** and recommends Streamable HTTP (`/mcp` endpoint, `transport="streamable-http"`). Second, esptool v5.x dropped the `.py` suffix and Python ≤ 3.9 support — the command is now `esptool` not `esptool.py`, and requires Python 3.10+. Raspberry Pi OS Bookworm (the current default) ships Python 3.11, so the minimum version constraint is satisfied, but the command name change must be reflected in every subprocess call.

The firmware caching design follows the decision already locked in STATE.md: 7-day TTL, download from `micropython.org/download/`, one `.bin` per chip variant. The state persistence model (boards.json in a well-known directory) is straightforward; no database is needed for Phase 1.

**Primary recommendation:** Build the FastMCP server with `transport="streamable-http"`, register Claude Code with `claude mcp add --transport http esp32-station http://raspberrypi.local:8000/mcp`, and use `esptool` (no `.py`) for all subprocess calls on a Pi running Python 3.11.

---

## Project Constraints (from CLAUDE.md)

No `./CLAUDE.md` found in project root. No project-level constraints to propagate.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11 (Bookworm default) | Runtime for all server code | Ships on Raspberry Pi OS Bookworm; meets esptool v5 minimum (3.10+) |
| mcp[cli] | 1.26.0 (latest Jan 2026) | FastMCP server framework, HTTP transport | Official Anthropic SDK; `FastMCP` API + built-in Streamable HTTP transport |
| esptool | 5.2.0 (Feb 2025) | Chip detection, firmware flashing | Official Espressif tool; supports all ESP32 variants |
| pyserial | 3.5+ | Serial port enumeration (`list_ports`) | Used internally by esptool; also needed for direct port listing |
| requests | 2.31+ | Firmware download with streaming | Standard HTTP client; simpler than httpx for one-shot downloads |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| mpremote | 1.23+ | Board reset, file ops (Phase 2+) | Not needed in Phase 1; install now to validate it works |
| anyio | pulled by mcp | Async execution inside FastMCP | Transitive dependency; no direct usage needed in Phase 1 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Streamable HTTP transport | SSE transport | SSE is deprecated in Claude Code; use Streamable HTTP for all new servers |
| esptool v5 | esptool v4.x | v4 uses `esptool.py` command; v5 is `esptool`. Pin v5 for new projects; only use v4 if Python 3.9 is forced |
| requests for firmware download | httpx / aiohttp | requests is sync but adequate; Phase 1 downloads are one-shot; async adds complexity for no benefit |
| systemd | supervisor / pm2 | systemd native on Pi OS Bookworm; no extra install; integrates with journald |

**Installation:**
```bash
# On Raspberry Pi (Bookworm) — must use venv due to PEP 668
python3 -m venv ~/esp32-station/venv
source ~/esp32-station/venv/bin/activate
pip install "mcp[cli]>=1.26.0,<2.0.0" "esptool>=5.0.0,<6.0.0" "pyserial>=3.5,<4.0" "requests>=2.31,<3.0" "mpremote>=1.23,<2.0"
```

**Version verification (run on target Pi):**
```bash
python3 --version          # expect 3.11.x
esptool version            # expect v5.2.0 (note: no .py suffix in v5)
python3 -c "import mcp; print(mcp.__version__)"  # expect 1.26.x
mpremote --version         # expect 1.23.x
```

---

## Architecture Patterns

### Recommended Project Structure

```
~/esp32-station/
├── venv/                     # isolated Python environment
├── mcp_server.py             # FastMCP entry point + tool registration
├── tools/
│   ├── board_detection.py    # list_boards(), detect_chip()
│   └── firmware_flash.py     # flash_firmware(), firmware cache logic
├── state/
│   ├── boards.json           # persisted board inventory
│   └── firmware/             # downloaded .bin cache (TTL 7 days)
├── requirements.txt
└── esp32-station.service     # systemd unit (copy to /etc/systemd/system/)
```

### Pattern 1: FastMCP Streamable HTTP Server

**What:** FastMCP server with `transport="streamable-http"` exposes tools at `/mcp` on port 8000.
**When to use:** All new MCP servers intended for LAN or remote use. SSE (`/sse`) is deprecated.

```python
# mcp_server.py — runs on Raspberry Pi
from mcp.server.fastmcp import FastMCP
from tools.board_detection import list_boards, detect_chip
from tools.firmware_flash import flash_firmware

mcp = FastMCP("esp32-station")

@mcp.tool()
def list_connected_boards() -> list[dict]:
    """List all ESP32 boards currently connected via USB."""
    return list_boards()

@mcp.tool()
def flash_micropython(port: str) -> dict:
    """Flash MicroPython onto the board at the given port. Auto-selects firmware by chip type."""
    return flash_firmware(port)

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

### Pattern 2: esptool Subprocess Call (v5 API)

**What:** Invoke `esptool` (no `.py`) as a subprocess. The public Python API in v5 changed to explicit parameters — use the CLI subprocess pattern for isolation and forward-compatibility.
**When to use:** All chip detection and flash operations.

```python
# tools/firmware_flash.py
import subprocess
import json

# CRITICAL: v5 command is "esptool", NOT "esptool.py"
ESPTOOL_CMD = "esptool"

def detect_chip(port: str) -> dict:
    """Run chip_id; return parsed chip info or raise on failure."""
    result = subprocess.run(
        [ESPTOOL_CMD, "--port", port, "--baud", "115200", "chip_id"],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"chip_id_failed: {result.stderr.strip()}")
    return _parse_chip_output(result.stdout)

def _parse_chip_output(stdout: str) -> dict:
    """Extract chip variant from esptool stdout.
    Example line: "Chip is ESP32-S3 (revision v0.1)"
    """
    for line in stdout.splitlines():
        if "Chip is" in line:
            # Returns e.g. "ESP32-S3"
            chip = line.split("Chip is")[1].split("(")[0].strip()
            return {"chip": chip, "raw": stdout}
    raise ValueError(f"chip_not_parsed: could not find 'Chip is' in output")
```

### Pattern 3: Board Enumeration via pyserial

**What:** `serial.tools.list_ports.comports()` returns all serial ports. Filter by USB VID/PIDs known to be ESP32-compatible USB-UART bridges.
**When to use:** `list_connected_boards` tool to discover what's plugged in before attempting operations.

```python
import serial.tools.list_ports

# Known USB VID/PID pairs for ESP32 USB-UART bridges
ESP32_VIDS = {
    0x1A86,  # CH340 (common cheap Chinese boards)
    0x10C4,  # CP2102 (Silabs, many Adafruit/SparkFun boards)
    0x0403,  # FTDI FT232
    0x239A,  # Adafruit
    0x303A,  # Espressif native USB (S2/S3/C3/C6 with built-in USB)
}

def list_boards() -> list[dict]:
    boards = []
    for port in serial.tools.list_ports.comports():
        if port.vid in ESP32_VIDS:
            boards.append({
                "port": port.device,
                "description": port.description,
                "vid": hex(port.vid),
                "pid": hex(port.pid),
                "serial_number": port.serial_number,
            })
    return boards
```

### Pattern 4: Board State Persistence

**What:** Load `boards.json` on startup; update when boards are detected with their chip variant; persist after every mutation.
**When to use:** BOARD-04 — survive server restarts.

```python
import json, os, pathlib

STATE_DIR = pathlib.Path.home() / ".esp32-station"
BOARDS_JSON = STATE_DIR / "boards.json"

def load_board_state() -> dict:
    STATE_DIR.mkdir(exist_ok=True)
    if BOARDS_JSON.exists():
        return json.loads(BOARDS_JSON.read_text())
    return {}

def save_board_state(state: dict) -> None:
    BOARDS_JSON.write_text(json.dumps(state, indent=2))
```

### Pattern 5: Firmware Cache with TTL

**What:** Download firmware `.bin` to local cache dir; skip download if file exists and is less than 7 days old.
**When to use:** FLASH-03 — network-independent flashing.

```python
import time, hashlib, requests, pathlib

FIRMWARE_DIR = pathlib.Path.home() / ".esp32-station" / "firmware"
FIRMWARE_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# MicroPython firmware URL pattern (as of v1.27.0):
# https://micropython.org/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.bin
FIRMWARE_URLS = {
    "ESP32":     "https://micropython.org/download/ESP32_GENERIC/",
    "ESP32-S2":  "https://micropython.org/download/ESP32_GENERIC_S2/",
    "ESP32-S3":  "https://micropython.org/download/ESP32_GENERIC_S3/",
    "ESP32-C3":  "https://micropython.org/download/ESP32_GENERIC_C3/",
    "ESP32-C6":  "https://micropython.org/download/ESP32_GENERIC_C6/",
}
# NOTE: Resolve the actual .bin URL by scraping the download page or
# maintaining a hardcoded mapping to specific release URLs.
# Hardcoded mapping is more reliable for offline scenarios.

def firmware_path(chip: str) -> pathlib.Path:
    return FIRMWARE_DIR / f"{chip.replace('-', '_')}.bin"

def firmware_is_fresh(path: pathlib.Path) -> bool:
    if not path.exists():
        return False
    age = time.time() - path.stat().st_mtime
    return age < FIRMWARE_TTL_SECONDS
```

### Pattern 6: systemd Unit File

**What:** Minimal unit file for the MCP server daemon. `Type=simple`; `Restart=on-failure`; run as `pi` user; activate venv via `ExecStart` path.

```ini
[Unit]
Description=ESP32 MicroPython Dev Station (MCP Server)
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/esp32-station
ExecStart=/home/pi/esp32-station/venv/bin/python3 /home/pi/esp32-station/mcp_server.py
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=esp32-station

[Install]
WantedBy=multi-user.target
```

**Deploy commands:**
```bash
sudo cp esp32-station.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable esp32-station
sudo systemctl start esp32-station
sudo systemctl status esp32-station
```

### Pattern 7: Claude Code MCP Registration

**What:** Register the Pi's MCP server with Claude Code using the **HTTP transport** (Streamable HTTP). SSE is deprecated.

```bash
# Run on the main machine (not the Pi)
claude mcp add --transport http esp32-station http://raspberrypi.local:8000/mcp
# Or with IP if mDNS not working:
claude mcp add --transport http esp32-station http://192.168.1.xxx:8000/mcp

# Verify
claude mcp list
# Then /mcp inside a Claude Code session to check connection
```

### Anti-Patterns to Avoid

- **`esptool.py` command name:** In v5 the command is `esptool`. Using `esptool.py` will fail with command not found on any pip-installed v5 environment.
- **`mcp.run(transport="sse")`:** SSE is deprecated in Claude Code. New servers must use `transport="streamable-http"`.
- **Running `pip install` system-wide on Bookworm:** Raspberry Pi OS Bookworm enforces PEP 668 (externally managed Python). Always use a venv.
- **Relying on esptool chip auto-detect as source-of-truth:** Use it as a validation probe. The locked decision in STATE.md says: "Never rely on esptool auto-detect; require explicit variant in config; use chip_id as validation step before flash."
- **Binding MCP server to `127.0.0.1`:** Claude is on a different machine; server must bind to `0.0.0.0`.
- **Calling esptool in-process via its Python API in v5:** v5 redesigned the API with explicit parameters. Subprocess isolation is simpler and remains stable across minor versions.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MCP protocol implementation | Custom JSON-RPC server | `mcp[cli]` FastMCP | Protocol versioning, schema generation, transport management already solved |
| USB serial port enumeration | Manual `/dev/ttyUSB*` globbing | `pyserial list_ports` | Handles platform differences, VID/PID metadata, returns structured data |
| Firmware flashing | Custom UART bootloader protocol | `esptool` subprocess | Espressif's protocol is complex (ROM, SPI flash addressing, baud negotiation); not reimplementable |
| Process management / auto-restart | Custom watchdog loop | systemd | Battle-tested; journald integration; socket activation if needed |

**Key insight:** Every critical piece of hardware interaction (flash protocol, serial enumeration) has an official maintained tool. The MCP server's job is orchestration, not re-implementing protocol stacks.

---

## Common Pitfalls

### Pitfall 1: `/dev/ttyUSB*` Permission Denied

**What goes wrong:** esptool subprocess exits immediately with `PermissionError`; works as root but fails as service user.
**Why it happens:** `/dev/ttyUSB*` owned by `root:dialout`; systemd service user not in `dialout` group.
**How to avoid:**
```bash
sudo usermod -a -G dialout pi
# ALSO add udev rules for CH340 (VID 1a86) and CP2102 (VID 10c4):
echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", MODE="0666"' | sudo tee /etc/udev/rules.d/99-esp32.rules
echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="10c4", MODE="0666"' | sudo tee -a /etc/udev/rules.d/99-esp32.rules
echo 'SUBSYSTEMS=="usb", ATTRS{idVendor}=="303a", MODE="0666"' | sudo tee -a /etc/udev/rules.d/99-esp32.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
# Log out and back in for group membership to take effect
```
**Warning signs:** `esptool` subprocess stderr contains "Permission denied"; `ls -la /dev/ttyUSB0` shows `dialout` group with no world read.

### Pitfall 2: esptool v5 Command Name Change

**What goes wrong:** `subprocess.run(["esptool.py", ...])` raises `FileNotFoundError`.
**Why it happens:** esptool v5 removed the `.py` suffix. The installed command is `esptool`.
**How to avoid:** Use `ESPTOOL_CMD = "esptool"` as a constant; verify with `esptool version` after installation.
**Warning signs:** `FileNotFoundError: [Errno 2] No such file or directory: 'esptool.py'`

### Pitfall 3: SSE Deprecation in Claude Code

**What goes wrong:** Claude Code can connect but shows deprecation warnings; future Claude Code versions may drop SSE support entirely.
**Why it happens:** MCP specification 2025-03-26 deprecated SSE in favor of Streamable HTTP.
**How to avoid:** Use `transport="streamable-http"` in `mcp.run()`; register with `claude mcp add --transport http`.
**Warning signs:** `claude mcp add --transport sse` shows a deprecation warning in Claude Code output.

### Pitfall 4: MCP Server Bound to localhost Only

**What goes wrong:** MCP server starts successfully on Pi but Claude on main machine cannot connect; `curl http://raspberrypi.local:8000/mcp` times out.
**Why it happens:** Default FastMCP host is `127.0.0.1` (localhost only).
**How to avoid:** Always pass `host="0.0.0.0"` to `mcp.run()`.
**Warning signs:** Server starts without error but connection from remote machine times out; `ss -tlnp | grep 8000` shows `127.0.0.1:8000` not `0.0.0.0:8000`.

### Pitfall 5: systemd Service Fails Due to Bookworm venv Requirement

**What goes wrong:** `systemctl start esp32-station` fails; journalctl shows `No module named mcp`.
**Why it happens:** Bookworm enforces PEP 668; pip packages installed in venv; systemd's `ExecStart` must use the venv's Python interpreter, not the system `/usr/bin/python3`.
**How to avoid:** `ExecStart` must point to `/home/pi/esp32-station/venv/bin/python3` (the venv interpreter), not `python3`.
**Warning signs:** `ModuleNotFoundError` in journalctl for any pip-installed package.

### Pitfall 6: esptool Chip Detection Misidentifies Variant

**What goes wrong:** `chip_id` returns "ESP32" but the board is an ESP32-S3; wrong firmware flashed; board won't boot.
**Why it happens:** CH340 USB-UART bridge can corrupt DTR/RTS handshake needed to enter download mode; detection falls back to classic ESP32.
**How to avoid:** Per STATE.md locked decision — treat `chip_id` as a validation probe, not source of truth. Require explicit chip config from user; use detected chip to verify config matches before proceeding.
**Warning signs:** `chip_id` succeeds but returns a different chip than expected from the board's physical markings.

### Pitfall 7: systemd Service Starts Before USB Device Is Available

**What goes wrong:** Server starts but `list_boards` returns empty because udev hasn't created device nodes yet.
**Why it happens:** `After=network.target` does not wait for USB devices to settle; service starts before boards are plugged in (or at boot before USB enumeration).
**How to avoid:** This is expected behavior — boards may be plugged in after the server starts. `list_boards` should always enumerate live at call time, not cache on startup. Only persist board *state* (last known chip type) in `boards.json`, not current connection status.
**Warning signs:** `list_boards` returns empty immediately after service starts even with boards plugged in.

---

## Code Examples

### Full mcp_server.py Skeleton

```python
# Source: mcp[cli] 1.26.x FastMCP API + project patterns
from mcp.server.fastmcp import FastMCP
import serial.tools.list_ports
import subprocess
import json
import time
import pathlib
import requests

mcp = FastMCP("esp32-station")

# ── State ──────────────────────────────────────────────────────────────────
STATE_DIR = pathlib.Path.home() / ".esp32-station"
BOARDS_JSON = STATE_DIR / "boards.json"
FIRMWARE_DIR = STATE_DIR / "firmware"
ESPTOOL = "esptool"   # v5: no .py suffix
BAUD = 115200

ESP32_VIDS = {0x1A86, 0x10C4, 0x0403, 0x239A, 0x303A}

FIRMWARE_URLS = {
    "ESP32":    "https://micropython.org/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.bin",
    "ESP32-S2": "https://micropython.org/resources/firmware/ESP32_GENERIC_S2-20251209-v1.27.0.bin",
    "ESP32-S3": "https://micropython.org/resources/firmware/ESP32_GENERIC_S3-20251209-v1.27.0.bin",
    "ESP32-C3": "https://micropython.org/resources/firmware/ESP32_GENERIC_C3-20251209-v1.27.0.bin",
    "ESP32-C6": "https://micropython.org/resources/firmware/ESP32_GENERIC_C6-20251209-v1.27.0.bin",
}

def _load_state() -> dict:
    STATE_DIR.mkdir(exist_ok=True)
    FIRMWARE_DIR.mkdir(exist_ok=True)
    if BOARDS_JSON.exists():
        return json.loads(BOARDS_JSON.read_text())
    return {}

def _save_state(state: dict) -> None:
    BOARDS_JSON.write_text(json.dumps(state, indent=2))

# ── Tools ──────────────────────────────────────────────────────────────────
@mcp.tool()
def list_connected_boards() -> list[dict]:
    """List all ESP32 boards currently connected via USB with their last-known chip type."""
    state = _load_state()
    boards = []
    for port in serial.tools.list_ports.comports():
        if port.vid in ESP32_VIDS:
            key = port.device
            entry = {
                "port": port.device,
                "description": port.description,
                "vid": hex(port.vid),
                "chip": state.get(key, {}).get("chip", "unknown"),
            }
            boards.append(entry)
    return boards

@mcp.tool()
def identify_chip(port: str) -> dict:
    """Detect the ESP32 chip variant at the given serial port. Updates board state."""
    result = subprocess.run(
        [ESPTOOL, "--port", port, "--baud", str(BAUD), "chip_id"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        return {"error": "chip_id_failed", "detail": result.stderr.strip()}
    chip = "unknown"
    for line in result.stdout.splitlines():
        if "Chip is" in line:
            chip = line.split("Chip is")[1].split("(")[0].strip()
            break
    if chip == "unknown":
        return {"error": "chip_not_parsed", "detail": result.stdout}
    state = _load_state()
    state[port] = {"chip": chip, "detected_at": time.time()}
    _save_state(state)
    return {"port": port, "chip": chip}

@mcp.tool()
def flash_micropython(port: str, chip: str | None = None) -> dict:
    """Flash MicroPython onto the board at the given port.
    If chip is None, auto-detects. Firmware is cached locally (7-day TTL).
    """
    # Pre-flight: identify chip
    if chip is None:
        detection = identify_chip(port)
        if "error" in detection:
            return {"error": "preflight_failed", "detail": detection}
        chip = detection["chip"]

    if chip not in FIRMWARE_URLS:
        return {"error": "unsupported_chip", "chip": chip, "supported": list(FIRMWARE_URLS)}

    # Ensure firmware cached
    fw_path = FIRMWARE_DIR / f"{chip.replace('-', '_')}.bin"
    if not fw_path.exists() or (time.time() - fw_path.stat().st_mtime) > 7 * 86400:
        url = FIRMWARE_URLS[chip]
        try:
            resp = requests.get(url, timeout=60, stream=True)
            resp.raise_for_status()
            fw_path.write_bytes(resp.content)
        except Exception as e:
            if fw_path.exists():
                pass  # use stale cache rather than fail
            else:
                return {"error": "firmware_download_failed", "detail": str(e)}

    # Erase flash, then write
    erase = subprocess.run(
        [ESPTOOL, "--port", port, "--baud", str(BAUD), "erase_flash"],
        capture_output=True, text=True, timeout=60
    )
    if erase.returncode != 0:
        return {"error": "erase_failed", "detail": erase.stderr.strip()}

    write_offset = "0x1000" if chip == "ESP32" else "0x0"
    flash = subprocess.run(
        [ESPTOOL, "--port", port, "--baud", "460800", "write_flash", write_offset, str(fw_path)],
        capture_output=True, text=True, timeout=120
    )
    if flash.returncode != 0:
        return {"error": "flash_failed", "detail": flash.stderr.strip()}

    return {"status": "success", "port": port, "chip": chip, "firmware": str(fw_path)}

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=8000)
```

### Testing the Server Without Claude

```bash
# Test that the /mcp endpoint responds
curl -s http://raspberrypi.local:8000/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/list","params":{},"id":1}'

# Use mcp dev for interactive browser-based testing
mcp dev ~/esp32-station/mcp_server.py

# Check logs
sudo journalctl -u esp32-station -f
```

### Flash Write Offset by Chip

| Chip | Erase command | Write offset | Notes |
|------|--------------|--------------|-------|
| ESP32 (classic) | `erase_flash` | `0x1000` | Bootloader at 0x1000 |
| ESP32-S2 | `erase_flash` | `0x0` | Bootloader at 0x0 |
| ESP32-S3 | `erase_flash` | `0x0` | Bootloader at 0x0 |
| ESP32-C3 | `erase_flash` | `0x0` | Bootloader at 0x0 |
| ESP32-C6 | `erase_flash` | `0x0` | Bootloader at 0x0 |

Source: [MicroPython ESP32 Getting Started](https://docs.micropython.org/en/latest/esp32/tutorial/intro.html)

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `mcp.run(transport="sse")` | `mcp.run(transport="streamable-http")` | MCP spec 2025-03-26 | SSE deprecated in Claude Code; all new servers use Streamable HTTP at `/mcp` |
| `esptool.py` command | `esptool` command | esptool v5.0 (Feb 2025) | Subprocess calls must drop the `.py` suffix |
| Python 3.9 compatible code | Python 3.10+ required for esptool v5 | esptool v5.0 (Feb 2025) | Bookworm's Python 3.11 satisfies this; Bullseye (3.9) would need esptool v4 |
| `pip install` system-wide | `pip install` inside venv only | Raspberry Pi OS Bookworm | PEP 668 enforced; system-wide pip fails on Bookworm |
| Firmware pinned at v1.23 | MicroPython v1.27.0 current | Dec 2025 | Firmware URL and filename patterns updated |

**Deprecated/outdated:**
- `esptool.py`: Use `esptool`. The `.py` suffix was removed in v5.
- SSE transport (`/sse`): Use Streamable HTTP (`/mcp`). Deprecated in MCP spec March 2025; Claude Code marks it deprecated in the CLI.
- Bullseye as target OS: Current Pi OS is Bookworm (Python 3.11); Bullseye gets esptool v5 incompatibility.

---

## Open Questions

1. **Exact firmware binary URLs for v1.27.0**
   - What we know: Download page is at `micropython.org/download/ESP32_GENERIC_C6/` etc.; filename pattern is `ESP32_GENERIC_C6-YYYYMMDD-vX.Y.Z.bin`
   - What's unclear: The hardcoded URLs in the code example above use the v1.27.0 Dec 2025 filenames — these need to be verified on the Pi during setup, as micropython.org may have released newer versions by implementation time.
   - Recommendation: Wave 0 task should verify URLs and update `FIRMWARE_URLS` dict; or implement download-page scraping with a fallback to hardcoded latest-known.

2. **ESP32-C5 and ESP32-H2 variants**
   - What we know: esptool v5 dropped support for ESP32-C5 beta3 and ESP32-C6 beta
   - What's unclear: Whether the user has C5 or H2 boards; MicroPython support for C5/H2 may be incomplete
   - Recommendation: Phase 1 supports the five variants in requirements (ESP32, S2, S3, C3, C6). Document C5/H2 as out of scope.

3. **mDNS resolution of `raspberrypi.local`**
   - What we know: `raspberrypi.local` works via mDNS (avahi) on most LANs
   - What's unclear: Whether the user's main machine has mDNS support (macOS/Linux: yes; Windows: maybe)
   - Recommendation: Document both mDNS and IP-based registration commands; have the user verify hostname resolution before registering Claude Code MCP.

---

## Environment Availability

| Dependency | Required By | Available (this machine) | Notes / Pi Expectation |
|------------|------------|--------------------------|------------------------|
| Python 3.10+ | esptool v5, mcp server | Python 3.14.3 (dev machine) | Pi Bookworm ships 3.11.2 — satisfied |
| esptool v5 | FLASH-01..05, BOARD-02 | Not installed (dev machine) | Must install on Pi via pip in venv |
| mpremote | Phase 2 only | Not installed (dev machine) | Install on Pi now to validate; not used in Phase 1 |
| pyserial | BOARD-01, BOARD-02 | Not installed (dev machine) | Must install on Pi via pip in venv |
| systemd | MCP-01, MCP-03 | systemd 260 (dev machine) | Pi Bookworm uses systemd natively |
| mcp[cli] | MCP-01, MCP-02 | Not installed (dev machine) | Must install on Pi via pip in venv |

**Note:** This research was run on the development machine (`linux x86_64`), not on the target Raspberry Pi. All "Available" results reflect the dev machine. The execution environment is the Pi; the table above projects expected Pi availability based on Bookworm defaults.

**Missing dependencies with no fallback (must be installed on Pi before Phase 1 can execute):**
- `mcp[cli]` — required for any MCP server functionality
- `esptool` — required for chip detection and firmware flashing
- `pyserial` — required for USB port enumeration

**Missing dependencies with fallback:**
- None in Phase 1 scope.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (to be installed — Wave 0 gap) |
| Config file | `pytest.ini` in project root — Wave 0 gap |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOARD-01 | `list_connected_boards` returns list of dicts | unit (mock pyserial) | `pytest tests/test_board_detection.py::test_list_boards -x` | Wave 0 |
| BOARD-02 | `identify_chip` parses esptool stdout correctly | unit (mock subprocess) | `pytest tests/test_board_detection.py::test_identify_chip -x` | Wave 0 |
| BOARD-02 | `identify_chip` returns error dict on bad exit code | unit (mock subprocess) | `pytest tests/test_board_detection.py::test_identify_chip_failure -x` | Wave 0 |
| BOARD-04 | Board state survives server restart (JSON round-trip) | unit | `pytest tests/test_state.py::test_state_persistence -x` | Wave 0 |
| FLASH-01 | `flash_micropython` invokes esptool with correct args | unit (mock subprocess) | `pytest tests/test_firmware_flash.py::test_flash_invocation -x` | Wave 0 |
| FLASH-02 | Correct firmware URL selected per chip variant | unit | `pytest tests/test_firmware_flash.py::test_firmware_url_mapping -x` | Wave 0 |
| FLASH-03 | Fresh firmware cache skips download; stale triggers re-download | unit (mock requests) | `pytest tests/test_firmware_flash.py::test_cache_ttl -x` | Wave 0 |
| FLASH-04 | Flash returns `chip_id_failed` error when chip detection fails | unit (mock subprocess) | `pytest tests/test_firmware_flash.py::test_flash_preflight_failure -x` | Wave 0 |
| FLASH-05 | `flash_micropython` calls `identify_chip` before `write_flash` | unit (mock subprocess call order) | `pytest tests/test_firmware_flash.py::test_preflight_called_first -x` | Wave 0 |
| MCP-01 | MCP server starts without error | smoke (local `mcp dev`) | Manual — `python3 mcp_server.py &` then `curl http://localhost:8000/mcp` | Manual |
| MCP-02 | `/mcp` endpoint reachable from remote host | smoke (curl from main machine) | Manual — `curl http://raspberrypi.local:8000/mcp` | Manual |
| MCP-03 | systemd unit enables and starts | smoke (systemctl) | Manual — `systemctl is-active esp32-station` | Manual |

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q` (unit tests only, < 5s)
- **Per wave merge:** `pytest tests/ -v` (full suite)
- **Phase gate:** Full suite green + manual smoke tests (MCP-01, MCP-02, MCP-03) before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_board_detection.py` — covers BOARD-01, BOARD-02
- [ ] `tests/test_state.py` — covers BOARD-04
- [ ] `tests/test_firmware_flash.py` — covers FLASH-01 through FLASH-05
- [ ] `tests/conftest.py` — shared fixtures (mock pyserial, mock subprocess, tmp path for state dir)
- [ ] `pytest.ini` — minimal config (testpaths, addopts)
- [ ] Framework install: `pip install pytest pytest-mock` in venv

---

## Sources

### Primary (HIGH confidence)
- [MCP Python SDK PyPI](https://pypi.org/project/mcp/) — confirmed v1.26.0, Streamable HTTP recommendation
- [Claude Code MCP docs](https://code.claude.com/docs/en/mcp) — confirmed SSE deprecated, `--transport http` is current pattern, `/mcp` endpoint
- [esptool GitHub Releases](https://github.com/espressif/esptool/releases) — confirmed v5.2.0, Python 3.10+ minimum, `esptool` command (no `.py`)
- [MicroPython ESP32 Download](https://micropython.org/download/ESP32_GENERIC/) — confirmed v1.27.0 (Dec 2025), firmware URL pattern

### Secondary (MEDIUM confidence)
- [MCP Transports spec 2025-03-26](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports) — Streamable HTTP as successor to SSE; single `/mcp` endpoint
- [FastMCP run() docs](https://gofastmcp.com/deployment/running-server) — `transport="streamable-http"`, `host`, `port` parameters confirmed
- [Raspberry Pi OS Bookworm](https://www.raspberrypi.com/news/bookworm-the-new-version-of-raspberry-pi-os/) — Python 3.11.2 default; PEP 668 venv enforcement
- [esptool v5 blog post](https://developer.espressif.com/blog/2025/04/esptool-v5/) — Breaking changes summary (CLI renamed, Python 3.10+ required)

### Tertiary (LOW confidence)
- WebSearch results for flash write offsets by chip variant — cross-verified with MicroPython docs; HIGH after verification
- Prior project research (STACK.md, ARCHITECTURE.md, PITFALLS.md) — written 2026-03-28; stack facts superseded by items above; architecture patterns remain valid

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified versions from PyPI and GitHub releases
- Architecture patterns: HIGH — derived from official FastMCP API docs and established project decisions
- Pitfalls: HIGH — Pitfalls 1-5 verified from official sources; Pitfall 6 (chip misidentification) from prior project research (MEDIUM)
- Test map: MEDIUM — test structure is straightforward but file paths unvalidated until Wave 0 creates them

**Research date:** 2026-03-28
**Valid until:** 2026-06-28 (90 days) for stable components; re-verify mcp version and MicroPython firmware URLs before implementation (fast-moving)

**Critical update vs. prior research (STACK.md):**
1. SSE deprecated → use Streamable HTTP
2. `esptool.py` → `esptool` (v5 command rename)
3. Python minimum 3.10 required for esptool v5 (Bookworm satisfies)
4. MicroPython latest is v1.27.0 (Dec 2025), not v1.23
5. mcp package is v1.26.0, not "1.x"
