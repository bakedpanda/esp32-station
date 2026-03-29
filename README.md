# ESP32 MicroPython Dev Station

A Raspberry Pi-based MCP server for managing ESP32 boards running MicroPython. Claude on your main machine can flash firmware, deploy code, and interact with boards over the LAN — no terminal switching, no copy-pasting tool output.

## What it does

- **Flash firmware** — flash MicroPython onto any connected ESP32 (classic, S2, S3, C3, C6); correct firmware auto-selected by chip type; firmware cached locally with 7-day TTL
- **Deploy code** — deploy a single file or a full project directory to a board via USB serial
- **REPL access** — execute MicroPython commands and capture output; read recent serial output; soft/hard reset
- **OTA updates** — push code updates over WiFi via WebREPL; falls back to USB on timeout *(Phase 3)*
- **GitHub deploy** — pull latest code from a GitHub repo and deploy to a board in one tool call *(Phase 3)*

All capabilities are exposed as MCP tools — Claude calls them directly, no copy-pasting required.

## Requirements

- Linux machine running Python 3.10+ (Raspberry Pi, ARM SBCs, or x86)
- systemd
- ESP32 board(s) connected via USB
- Claude Code on your main machine with MCP configured

## Setup

**1. Clone and install dependencies**

```bash
git clone https://github.com/bakedpanda/ESP32-server.git
cd ESP32-server
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**2. Add serial port permissions**

```bash
sudo usermod -aG dialout $USER
# Log out and back in for this to take effect
```

**3. Install the systemd service**

```bash
sudo cp esp32-station.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable esp32-station
sudo systemctl start esp32-station
```

The service starts automatically on boot and runs the MCP server on port 8000.

**4. Register with Claude Code (on your main machine)**

```bash
claude mcp add --transport http esp32-station http://raspberrypi.local:8000/mcp
```

Replace `raspberrypi.local` with your Pi's hostname or IP if different.

## MCP Tools

| Tool | Description |
|------|-------------|
| `list_connected_boards` | List all ESP32 boards connected via USB |
| `identify_chip` | Detect chip variant (ESP32, S2, S3, C3, C6) at a serial port |
| `flash_micropython` | Flash MicroPython firmware onto a board |
| `get_board_state` | Return persisted board state (chip type, last detected) |
| `deploy_file_to_board` | Deploy a single file to a board via USB |
| `deploy_directory_to_board` | Deploy a full project directory to a board via USB |
| `exec_repl_command` | Execute a MicroPython command and capture output |
| `read_board_serial` | Read recent serial output from a board |
| `reset_board` | Soft or hard reset a board via USB |

## Architecture

```
Main machine (Claude Code)
    │  MCP over Streamable HTTP
    ▼
Raspberry Pi :8000
    ├── mcp_server.py         — FastMCP tool registration
    └── tools/
        ├── board_detection.py  — USB enumeration, chip ID (esptool)
        ├── firmware_flash.py   — Firmware cache + flash (esptool)
        ├── file_deploy.py      — File/dir deploy (mpremote)
        ├── repl.py             — REPL exec, serial read, reset (mpremote)
        └── serial_lock.py      — Per-port file lock (prevents USB conflicts)
    │
    ▼
ESP32 board(s) via USB
```

**Key decisions:**
- MCP over Streamable HTTP (not stdio) — debuggable with curl, works over LAN
- Per-port serial locking — concurrent tool calls to different boards work fine; same-board calls serialize safely
- Subprocess isolation — esptool, mpremote, and git run as subprocesses; cleaner than in-process bindings
- Never rely on esptool auto-detect — chip variant is explicitly provided or validated before flashing

## Running tests

```bash
source venv/bin/activate
pytest
```

## Status

| Phase | What it delivers | Status |
|-------|-----------------|--------|
| 1 — Foundation & Infrastructure | MCP server + board detection + firmware flashing | Complete |
| 2 — Core USB Workflows | File deploy + REPL + serial lock + error handling | Complete |
| 3 — WiFi & Advanced | WebREPL OTA + GitHub deploy | In progress |

## Out of scope

- Web UI / dashboard — Claude is the interface
- Fleet inventory / multi-board tracking — single board at a time
- Non-MicroPython firmware (Arduino, ESP-IDF, Zephyr)
- Authentication / security hardening — trusted LAN only
