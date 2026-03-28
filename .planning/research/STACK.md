# Technology Stack

**Project:** ESP32 MicroPython Dev Station
**Researched:** 2026-03-28
**Confidence:** MEDIUM-HIGH (ecosystem patterns established; MCP SDK HTTP SSE transport well-documented; specific version compatibility needs Phase 1 validation)

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Python** | 3.9+ | MCP server, all sub-services | Language choice for Pi daemon. Aligns with MicroPython ecosystem; Espressif tooling all Python-based. Raspberry Pi has native Python support. |
| **Flask or FastAPI** | 2.3+ or 0.100+ | Optional supplementary HTTP endpoints | NOT needed for MCP itself — the SDK's built-in SSE transport handles that. Add Flask/FastAPI only if you need custom non-MCP HTTP routes (e.g. a `/health` endpoint or webhook receiver). |
| **Model Context Protocol (MCP) SDK** | 1.x (Python) | MCP server interface | Official Anthropic Python SDK (`mcp` on PyPI). Provides `@mcp.tool()` decorator, schema generation, and built-in transport options (stdio and HTTP SSE). HTTP SSE transport runs its own ASGI server — Flask is not needed when using it directly. |

### Flashing & Firmware

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **esptool.py** | 4.7+ | Firmware flashing, chip detection | Official Espressif tool. Supports all ESP32 variants (classic, S2/S3, C3/C6). Subprocess-based invocation from MCP server. |
| **MicroPython firmware (official)** | 1.23+ | Target firmware image | Latest stable release from micropython.org. Support for multiple chip variants via separate .bin files per chip. |

### File Deployment

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **mpremote** | 1.23+ (bundled with MicroPython tools) | File sync, REPL, soft reset | Official MicroPython tool. Replaces older `rshell`. Better USB handling, subprocess-friendly. |
| **pyserial** | 3.5+ | Low-level serial communication | Fallback for custom serial operations. Used by mpremote; also available directly for custom REPL handling. |

### Serial I/O & REPL

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pyserial** | 3.5+ | Serial port communication | Standard library for serial; used by mpremote and rshell. Direct control for custom REPL monitoring. |
| **webrepl_client.py** | 1.x (from MicroPython repo) | WebREPL connectivity (Phase 4+) | Official MicroPython tool for WiFi-based REPL. Needed for OTA updates and remote debugging. |

### Infrastructure & Development

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **systemd** | built-in | Process management on Pi | Standard on Raspberry Pi OS. Auto-start daemon, restart on crash, logging to journalctl. |
| **Git** | 2.30+ | GitHub integration | Standard on Pi OS. Required for `git clone/pull` in Git sync service. |

## Installation

### Raspberry Pi Setup

```bash
# Update package manager
sudo apt-get update
sudo apt-get upgrade

# Install Python and pip
sudo apt-get install python3 python3-pip python3-venv

# Create project directory and venv
mkdir -p ~/esp32-station
cd ~/esp32-station
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install "mcp[cli]" esptool mpremote pyserial requests

# mcp[cli] installs the official MCP SDK plus the `mcp` CLI tool
# Flask is NOT needed — the SDK's HTTP SSE transport is self-contained
# (uses anyio/starlette/uvicorn under the hood)

# Create systemd service (see below)
sudo nano /etc/systemd/system/esp32-station.service
sudo systemctl daemon-reload
sudo systemctl enable esp32-station
sudo systemctl start esp32-station
```

### Systemd Service File

Save as `/etc/systemd/system/esp32-station.service`:

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

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=esp32-station

[Install]
WantedBy=multi-user.target
```

### Main Machine (Claude Access)

Claude needs to connect to Pi's MCP server. Configuration in `~/.claude/mcp.json` or Claude settings:

```json
{
  "mcpServers": {
    "esp32-station": {
      "type": "sse",
      "url": "http://raspberry-pi.local:8000/sse"
    }
  }
}
```

The `type: "sse"` key tells Claude Code to use HTTP SSE transport. The URL must point at the `/sse` endpoint that the official MCP Python SDK exposes by default when running its SSE server.

**Note:** Claude Code does not support arbitrary `"command": "http"` args — the correct key is `"type": "sse"` with a `"url"` field. If your version of Claude Code predates SSE support, fall back to wrapping the connection in a stdio proxy script:

```json
{
  "mcpServers": {
    "esp32-station": {
      "command": "python3",
      "args": ["/path/to/sse_stdio_proxy.py", "http://raspberry-pi.local:8000/sse"]
    }
  }
}
```

## MCP Python SDK — Usage Pattern

The official SDK (`mcp` on PyPI, maintained by Anthropic) uses a `FastMCP` high-level API as of v1.x. This is the recommended entry point:

```python
# mcp_server.py — runs on Raspberry Pi
from mcp.server.fastmcp import FastMCP
import subprocess, json

mcp = FastMCP("esp32-station")

@mcp.tool()
def flash_firmware(device: str, chip: str = "auto") -> dict:
    """Flash MicroPython firmware onto an ESP32 board."""
    result = subprocess.run(
        ["esptool.py", "--port", device, "chip_id"],
        capture_output=True, text=True, timeout=30
    )
    # ... full impl
    return {"status": "success", "chip": chip}

@mcp.tool()
def list_boards() -> list[dict]:
    """List all connected ESP32 boards."""
    # ... pyserial port enumeration
    return []

if __name__ == "__main__":
    # HTTP SSE transport — listens on 0.0.0.0:8000
    mcp.run(transport="sse", host="0.0.0.0", port=8000)
```

**Key SDK facts:**
- `FastMCP` handles tool schema generation automatically from type hints and docstrings
- `mcp.run(transport="sse")` starts the Starlette/uvicorn ASGI server on the given host/port
- The SSE endpoint is exposed at `/sse`; messages endpoint at `/messages`
- Tools return any JSON-serialisable value; the SDK wraps it in the correct MCP response envelope
- `@mcp.tool()` supports sync and `async def` handlers — use `async` for subprocess calls that should not block
- The lower-level `mcp.server.Server` API exists if you need fine-grained control (e.g. custom resources or prompts)
- For stdio transport (debugging locally): `mcp.run(transport="stdio")`

**Testing during development:**
```bash
# MCP inspector (browser UI for testing tools interactively)
mcp dev mcp_server.py

# Or call over HTTP directly
curl -N http://raspberry-pi.local:8000/sse       # SSE stream
curl -X POST http://raspberry-pi.local:8000/messages \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_boards","arguments":{}},"id":1}'
```

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Language** | Python | Node.js | Aligns better with Espressif tooling; GPIO/serial libraries mature in Python. Node.js faster but less MicroPython-native. |
| **Web Framework** | MCP SDK built-in | Django | MCP SDK SSE transport replaces the need for a web framework entirely for MCP tools. Django is overkill in any case. |
| **Web Framework** | MCP SDK SSE transport | Flask | The official MCP Python SDK ships an HTTP SSE transport built on Starlette/uvicorn. No separate web framework needed for basic MCP. Add Flask only if custom non-MCP HTTP endpoints are required. |
| **Serial Library** | pyserial | pyserial-asyncio | Standard pyserial + threading sufficient. Async version adds complexity for MVP. |
| **File Deployment** | mpremote | rshell | mpremote is newer, actively maintained by MicroPython org. rshell more mature but older. |
| **MCP Transport** | HTTP | stdio | HTTP enables persistent daemon. stdio forces subprocess model, breaks LAN requirement. |
| **MCP SDK** | Official Python SDK | Custom JSON-RPC | Official SDK tested/maintained. Custom adds risk. |
| **Process Manager** | systemd | supervisor/pm2 | systemd standard on Pi OS; pm2 is Node-centric. |

## Version Pinning Strategy

**Approach:** Specify minimum versions, test against latest in Phase 1.

```txt
# requirements.txt
mcp[cli]>=1.0.0,<2.0.0
esptool>=4.7.0,<5.0.0
mpremote>=1.23.0,<2.0.0
pyserial>=3.5,<4.0.0
requests>=2.31.0,<3.0.0
# anyio, starlette, uvicorn pulled in transitively by mcp[cli]
```

**Rationale:**
- Flask removed — MCP SDK HTTP SSE transport is self-contained
- `mcp[cli]` installs the full SDK including the dev CLI (`mcp dev`, `mcp run`)
- Upper bounds prevent breaking changes
- Phase 1 spike will identify any compatibility issues
- Lock exact versions in production after testing

## Platform Constraints

| Constraint | Decision | Impact |
|-----------|----------|--------|
| **Raspberry Pi ARM** | All tools must be Pi-compatible | esptool, pyserial, Flask all support ARM natively; no issues expected |
| **Python 3.9+** | Minimum version | Covers Raspberry Pi OS Buster+ (default); asyncio support if needed |
| **USB Device Perms** | User running daemon must access `/dev/ttyUSB*` | Add `pi` user to `dialout` group: `sudo usermod -a -G dialout pi` |
| **Network Access** | Pi ↔ Main machine over LAN | Port 8000 (MCP server) must be open. Firewalls: allow on trusted subnet only |

## Deployment Architecture

```
Raspberry Pi (runs on startup)
├── venv (isolated Python environment)
└── mcp_server.py (Flask + MCP SDK)
    ├── tool_handlers/
    │   ├── firmware.py (esptool wrapper)
    │   ├── deploy.py (mpremote wrapper)
    │   ├── serial_monitor.py (pyserial)
    │   ├── ota.py (webrepl_client)
    │   └── git_sync.py (subprocess git)
    └── state/
        ├── boards.json (device inventory)
        └── config.json (service configuration)

Port 8000 (HTTP) ← LAN ← Main Machine (Claude)
```

## Development vs. Production

**Development (Phase 1-2):**
```bash
python3 mcp_server.py --debug --log-level DEBUG
# Runs on port 8000 with verbose logging
```

**Production (Phase 2+):**
```bash
# Systemd service runs automatically
sudo systemctl status esp32-station
sudo journalctl -u esp32-station -f  # Follow logs
```

## Hardware Prerequisites

- Raspberry Pi 3B+ or later (4B+ recommended for better performance)
- 2GB+ RAM (4GB+ recommended)
- Power supply (at least 2.5A for Pi)
- USB hub with power (to support multiple ESP32 boards)
- Network connectivity (Ethernet or WiFi to main machine's LAN)

## Dependency Rationale

**Why not Docker/Containers:**
- Pi development often requires direct hardware access
- Containers add complexity for a single daemon
- Easier to iterate with venv + systemd in early phases
- Container support deferred to Phase 5 if scaling needed

**Why not AWS/Cloud:**
- PROJECT.md specifies LAN-only, Pi-local deployment
- Latency critical for serial operations
- USB device bridging over network is complex
- Local daemon simplifies debugging

## Monitoring & Observability (Phase 3+)

**Not in MVP but consider for hardening:**
- Prometheus metrics (esptool duration, flash success rate, error types)
- Structured logging (JSON format for aggregation)
- Health check endpoint (`/health` for uptime monitoring)
- Database for deployment history (SQLite on Pi)

## Security Considerations (Phase 4+)

**Out of scope for MVP (trusted LAN only) but plan for:**
- TLS/HTTPS for MCP transport (certificate pinning or self-signed)
- API token authentication (bearer token or mTLS)
- Encrypted storage of WiFi/Git credentials
- Rate limiting on tool endpoints
- Audit logging of all operations

## Upgrade Path

**Phase 2→3:** No stack changes. Add async (FastAPI) only if streaming logs becomes bottleneck.

**Phase 3→4:** Consider PostgreSQL if deployment history grows. SQLite sufficient for MVP.

**Phase 5:** Evaluate clustering (Redis) only if multi-board concurrency becomes critical.

## Rationale for Stack Choices

1. **Python chosen because:**
   - Espressif (ESP32 manufacturer) uses Python for all tools
   - MicroPython development culture is Python-centric
   - Raspberry Pi has first-class Python support
   - MCP SDK mature in Python

2. **HTTP transport chosen because:**
   - Enables persistent daemon mode (survives Claude disconnections)
   - Standard debugging/testing tools (curl, Postman)
   - Claude connects over network (not subprocess stdin/stdout)
   - Future multi-client support without changes

3. **Flask chosen because:**
   - Minimal dependencies; works on Pi
   - Proven in production
   - Sufficient for MVP (single daemon, moderate load)
   - Upgrade path to FastAPI is straightforward if async needed

4. **esptool + mpremote chosen because:**
   - Official Espressif/MicroPython tools (maintained)
   - Reference implementations; feature-complete
   - Community-tested; well-documented
   - Subprocess isolation prevents blocking

## Sources

- esptool GitHub: https://github.com/espressif/esptool
- MicroPython tools: https://github.com/micropython/micropython/tree/master/tools
- Model Context Protocol: https://modelcontextprotocol.io/
- MCP Python SDK (PyPI `mcp`): https://github.com/modelcontextprotocol/python-sdk
- MCP Python SDK docs: https://modelcontextprotocol.io/docs/tools/python
- Raspberry Pi official docs: https://www.raspberrypi.org/documentation/
