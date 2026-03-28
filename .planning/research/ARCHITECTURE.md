# Architecture Research — ESP32 MicroPython Dev Station

**Project:** ESP32 MicroPython Dev Station (Raspberry Pi + MCP Server)
**Researched:** 2026-03-28
**Overall Confidence:** MEDIUM (training data + first principles; needs validation during implementation)

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│ Main Development Machine                                            │
│ ┌──────────────────────────────────────────────────────────────┐   │
│ │ Claude (with MCP client)                                     │   │
│ │ - Calls tools via MCP protocol                              │   │
│ │ - Receives results and streams                              │   │
│ └──────────────┬───────────────────────────────────────────────┘   │
└─────────────────┼──────────────────────────────────────────────────┘
                  │ LAN (TCP/HTTP transport)
                  │
┌─────────────────▼──────────────────────────────────────────────────┐
│ Raspberry Pi (Deployment Hub)                                       │
│                                                                      │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ MCP Server (Python/Node)                                      │ │
│ │ ┌──────────────────────────────────────────────────────────┐ │ │
│ │ │ Tool Handlers (orchestrate sub-services)                │ │ │
│ │ │ - flash_firmware()  → esptool wrapper service          │ │ │
│ │ │ - deploy_files()    → mpremote wrapper service         │ │ │
│ │ │ - update_ota()      → WiFi OTA service                 │ │ │
│ │ │ - read_serial()     → serial monitor service           │ │ │
│ │ │ - sync_repo()       → git service                      │ │ │
│ │ └──────────────────────────────────────────────────────────┘ │ │
│ ├─────────────────────────────────────────────────────────────── │ │
│ │ Sub-Services (background daemons)                             │ │
│ │ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │ │
│ │ │ esptool      │ │ mpremote     │ │ Serial       │         │ │
│ │ │ wrapper      │ │ wrapper      │ │ monitor      │         │ │
│ │ └──────────────┘ └──────────────┘ └──────────────┘         │ │
│ │ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐         │ │
│ │ │ WiFi OTA     │ │ Git puller   │ │ Config       │         │ │
│ │ │ service      │ │ (cron)       │ │ manager      │         │ │
│ │ └──────────────┘ └──────────────┘ └──────────────┘         │ │
│ └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│ ┌────────────────────────────────────────────────────────────────┐ │
│ │ Hardware Interfaces                                           │ │
│ │ - USB serial connections (multiple ESP32 boards)            │ │
│ │ - Network interface (WiFi/Ethernet to ESP32 devices)       │ │
│ └────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                  ▲
                  │ USB serial + WiFi
                  │
┌─────────────────▼──────────────────────────────────────────────────┐
│ ESP32 Board(s)                                                      │
│ - MicroPython firmware                                              │
│ - User project code                                                 │
│ - WebREPL for OTA + interactive console                            │
└──────────────────────────────────────────────────────────────────────┘
```

## Components

### 1. MCP Server (Main Orchestrator)

**Responsibility:** Expose unified tool interface to Claude; coordinate sub-services; manage state and serialization.

**Language/Framework:** Python with `mcp` library or Node.js with `@modelcontextprotocol/sdk`

**Interfaces:**
- **Inbound:** HTTP transport from Claude (Claude's native transport for non-stdio MCP)
- **Outbound:** IPC/subprocess calls to sub-services; reads/writes to device state files

**Key Behaviors:**
- Hosts tools: `flash_firmware`, `deploy_files`, `update_ota`, `read_serial`, `run_repl`, `sync_repo`, `list_boards`
- Queues/serializes USB operations (enforces mutual exclusion to prevent conflicts)
- Maintains device inventory (detected boards, firmware versions, WiFi IPs)
- Returns streaming results for long-running operations (progress updates)

**Implementation Notes:**
- Python recommended for MicroPython ecosystem alignment (reuses Espressif toolchain knowledge)
- Should run as systemd service on Pi for auto-restart
- HTTP transport chosen over stdio because:
  - Claude connects over network, not subprocess stdin/stdout
  - Allows persistent daemon (survives Claude disconnections)
  - Enables multiple concurrent Claude instances to coexist
  - Standard HTTP debugging/logging tools available

---

### 2. esptool Wrapper Service

**Responsibility:** Flash MicroPython firmware onto ESP32 variants; detect chip type; handle fallback versions.

**Interfaces:**
- **Input:** RPC call with `board_device` (e.g., `/dev/ttyUSB0`), `chip_variant` (auto-detect or specified), `firmware_url` (optional)
- **Output:** JSON with firmware version, chip detected, flash status, duration

**Key Behaviors:**
- Invokes `esptool.py` as subprocess with chip detection (`esptool.py chip_id`)
- Maps detected chip to firmware variant (ESP32, ESP32-S2, ESP32-S3, ESP32-C3, ESP32-C6)
- Downloads firmware if not cached locally (`~/.cache/micropython-firmware/`)
- Handles USB device acquisition safely (fails if board already in use)
- Streams progress to MCP server (percentage complete, current step)

**Why Separate Service:**
- esptool is CPU-intensive and can hang; subprocess isolation prevents MCP server from blocking
- Allows cleanup of USB resources on error/timeout
- Can be restarted independently if needed

---

### 3. mpremote Wrapper Service

**Responsibility:** Deploy project files and sync state; handle USB file operations and soft resets.

**Interfaces:**
- **Input:** RPC call with `board_device`, `local_dir` (source), `remote_dir` (optional, defaults to `/`), `file_list` (optional filter)
- **Output:** JSON with files deployed, bytes transferred, timestamp, board state before/after

**Key Behaviors:**
- Invokes `mpremote` with `--device` and `--baud` flags
- Syncs files via `cp :` command
- Performs soft reset after deploy (`machine.soft_reset()` via REPL)
- Validates sync by listing remote directory
- Handles partial deploys (only changed files)
- Times out after 30s per file to catch hung boards

**Why Separate Service:**
- mpremote can hang if ESP32 is unresponsive; isolation prevents MCP server blocking
- Multiple deployments would queue (enforced by MCP server's serial lock)
- Soft reset requires REPL interaction; cleaner in dedicated handler

---

### 4. Serial Monitor Service

**Responsibility:** Stream serial output from one connected ESP32; multiplex across devices; enable REPL input.

**Interfaces:**
- **Input:** RPC call with `board_device`, `baud_rate` (default 115200)
- **Output:** Streaming JSON lines with `{timestamp, source_device, data, level}`

**Key Behaviors:**
- Opens serial connection (`pyserial`) with configurable baud rate
- Captures all output (stdout, exceptions, tracebacks)
- Multiplexes multiple boards (tracks device → open serial handle)
- Allows REPL input (feeds user commands back to board)
- Auto-reconnects if board resets
- Buffers last 1000 lines (for latecomers to tail history)

**Why Separate Service:**
- Serial I/O is blocking; dedicated service prevents CLI tool from blocking MCP
- Enables long-running monitoring without timeout
- Can be reused by multiple Claude instances simultaneously (read-only or multiplexed write)

---

### 5. WiFi OTA Service

**Responsibility:** Push firmware/code updates over-the-air via WebREPL or custom HTTP server.

**Interfaces:**
- **Input:** RPC call with `board_ip`, `firmware_url` or `code_tar_gz`, `auth_token` (if WebREPL protected)
- **Output:** JSON with update status, board IP discovered, verification hash

**Key Behaviors:**
- Connects to WebREPL (`webrepl_client.py`)
- Uploads firmware binary to `/tmp` on board
- Executes board-side update script (`update_fw.py`)
- Alternatively: Hosts HTTP server, board pulls `firmware.bin` and verifies checksum
- Validates post-update by running device diagnostic script
- Handles network timeouts (retries 3x with exponential backoff)

**Why Separate Service:**
- OTA is async/fire-and-forget; MCP server should not block waiting for board
- Network issues can be complex; isolation simplifies debugging
- Allows concurrent USB and WiFi operations without contention

---

### 6. Git Sync Service

**Responsibility:** Pull user's GitHub repo; deploy to all boards; validate syntax.

**Interfaces:**
- **Input:** RPC call with `repo_url`, `branch` (default: main), `deploy_targets` (all/usb/ota)
- **Output:** JSON with clone status, commit hash, files deployed, errors (if any)

**Key Behaviors:**
- Clones/pulls repo into `~/esp32-projects/{repo_name}`
- Validates Python syntax of all `.py` files locally
- Invokes `deploy_files` for each target board
- Logs deployment manifest (files, sizes, checksums)
- Can be triggered by GitHub webhook (optional future enhancement)

**Why Separate Service:**
- Git operations are I/O bound; subprocess isolation prevents blocking
- Syntax validation before deploy saves time (fail fast)
- Enables scheduled pulls (cron) without MCP server being up

---

### 7. State Manager / Config

**Responsibility:** Track board inventory, deployment history, and configuration.

**Interfaces:**
- **Input:** File-based (JSON) or Redis (for scale)
- **Output:** Board metadata, last-known state, firmware versions

**Files to Track:**
```
~/.esp32-station/
├── config.json          # Service config, WiFi credentials
├── boards.json          # Detected boards: {port, chip_id, ip, fw_version}
├── deployments.json     # History: {timestamp, board, repo, commit, status}
└── cache/
    ├── micropython-firmware/
    │   ├── esp32-1.x.x.bin
    │   ├── esp32-s2-1.x.x.bin
    │   └── ...
    └── git-repos/
        └── {repo_name}/
```

**Key Behaviors:**
- Persists board metadata across restarts
- Deduplicates firmware downloads
- Logs all deployments for audit trail

---

## Data Flow

### Scenario 1: Flash Firmware + Deploy Code (USB)

```
Claude (main machine)
  │
  └─ [MCP] flash_firmware(device=/dev/ttyUSB0, chip=auto)
       │
       ▼ (HTTP transport over LAN)
  MCP Server (Pi)
  │
  ├─ [acquire serial lock for /dev/ttyUSB0]
  │
  ├─ [subprocess] esptool_wrapper.py
  │  │
  │  └─ esptool.py chip_id /dev/ttyUSB0
  │     │ (USB device discovered: ESP32-S3)
  │     └─ download firmware, flash, verify
  │
  └─ [release serial lock]
       │
       └─ return {status: "success", chip: "ESP32-S3", fw_version: "1.23"}

Claude
  │
  └─ [MCP] sync_repo(repo=https://github.com/user/sensor-project)
       │
       ▼ HTTP (LAN)
  MCP Server
  │
  └─ git_sync_service.py
     │
     ├─ git clone/pull into ~/esp32-projects/sensor-project
     ├─ validate Python syntax
     └─ invoke deploy_files(local_dir=..., remote_dir=/)
        │
        └─ [subprocess] mpremote_wrapper.py
           │
           ├─ [acquire serial lock for /dev/ttyUSB0]
           ├─ mpremote --device=/dev/ttyUSB0 cp -r src/ :/
           ├─ soft_reset()
           └─ [release serial lock]
              │
              └─ return {files: 42, bytes: 125000, status: "success"}

Claude
  │
  └─ [MCP] read_serial(device=/dev/ttyUSB0, tail=100)
       │
       ▼ HTTP (LAN)
  Serial Monitor Service
  │
  ├─ [open serial handle, buffer 1000 lines]
  └─ stream {"timestamp": "...", "data": "..."}
```

### Scenario 2: OTA Update (WiFi)

```
Claude
  │
  └─ [MCP] list_boards()
       │
       ▼ HTTP
  MCP Server
  │
  └─ read boards.json
     │
     └─ return [{port: "/dev/ttyUSB0", ip: "192.168.1.42", fw: "1.23"}]

Claude
  │
  └─ [MCP] update_ota(board_ip=192.168.1.42, firmware_url=https://...)
       │
       ▼ HTTP
  MCP Server → WiFi OTA Service
  │
  ├─ connect to WebREPL at board_ip:8266
  ├─ download firmware from URL
  ├─ upload to board via REPL
  ├─ execute update script
  ├─ verify checksum
  └─ return {status: "success", new_version: "1.24"}

(No USB involvement — ESP32 updates over network independently)
```

### Scenario 3: Multiple Tool Calls in Sequence

```
Claude
  │
  ├─ [MCP tool 1] flash_firmware(device=/dev/ttyUSB0)
  │  │
  │  └─ → MCP Server acquires lock, flashes, releases lock
  │
  ├─ [MCP tool 2] sync_repo(repo=...) — waits for tool 1 to finish
  │  │
  │  └─ → MCP Server acquires lock, deploys, releases lock
  │
  └─ [MCP tool 3] read_serial(device=/dev/ttyUSB0)
     │
     └─ → Serial Monitor (already open, streaming)
```

**Critical:** MCP Server enforces a **serial lock** (mutex per device) to prevent:
- esptool and mpremote competing for `/dev/ttyUSB0`
- Flash operations being interrupted by file sync
- REPL operations interfering with serial output capture

---

## MCP Transport Mechanism

### Decision: HTTP SSE (Server-Sent Events) over LAN

**Why not stdio:**
- stdio requires MCP server to be a subprocess of Claude client
- This breaks the requirement that Pi runs a persistent daemon
- Limits Claude to single connection at a time
- Loses ability to log/debug independently

**Why HTTP SSE:**
- **Persistent:** Pi daemon runs always; Claude connects on-demand
- **Resilient:** Connection drops don't kill the server
- **Debuggable:** Standard HTTP logs, curl testing, monitoring
- **Multi-client:** Multiple Claude instances can connect simultaneously (though serial ops still serialize)
- **Firewall-friendly:** Single port (8000), standard protocols

**Implementation:**
```python
# mcp_server.py (Raspberry Pi daemon)
from flask import Flask
from mcp.server.stdio import StdioServer  # OR custom HTTP adapter
import json

app = Flask(__name__)

@app.route('/mcp', methods=['POST'])
def handle_mcp_call():
    """Claude sends {jsonrpc, method, params}; return result"""
    request_data = request.json
    method = request_data['method']
    params = request_data.get('params', {})

    # Route to tool handlers
    if method == 'flash_firmware':
        return flash_firmware(params)
    # ... etc

    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

**Alternative: Standard MCP HTTP Server**
- Some MCP libraries already support HTTP transport natively
- Check `@modelcontextprotocol/sdk` for Node.js or Anthropic's Python SDK
- If available, prefer official implementation over custom Flask wrapper

**Claude Connection (Main Machine):**
```bash
# Claude's MCP config (~/.claude/mcp.json)
{
  "mcpServers": {
    "esp32-station": {
      "command": "http",
      "args": ["http://raspberry-pi.local:8000/mcp"]
    }
  }
}
```

---

## Serial Lock / Concurrency Control

**Problem:** Multiple tools (flash, deploy, REPL) compete for `/dev/ttyUSB0`

**Solution:** File-based mutex in MCP Server

```python
# mcp_server.py
import fcntl
import os
from contextlib import contextmanager

class SerialLock:
    def __init__(self, device_path):
        self.device_path = device_path
        self.lock_file = f"/tmp/esp32-lock-{device_path.replace('/', '-')}"

    @contextmanager
    def acquire(self, timeout=30):
        """Exclusive lock on USB device"""
        with open(self.lock_file, 'w') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Block until available
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

# Usage in MCP tool handler
def flash_firmware(params):
    device = params['device']
    lock = SerialLock(device)

    with lock.acquire(timeout=30):
        # Safe to use /dev/ttyUSB0 now
        result = subprocess.run(['esptool.py', ...], capture_output=True)

    return {"status": "success", ...}
```

---

## Build Order (Phase Dependencies)

Based on architecture, suggested implementation sequence:

### Phase 1: Foundation
1. **MCP Server skeleton** — HTTP endpoint, tool registration framework
   - *Why first:* All other components depend on this interface
   - *Deliverable:* Bare-bones server with one dummy tool

2. **State Manager** — boards.json, config.json, caching
   - *Why early:* Needed for device discovery, persistence
   - *Deliverable:* Board inventory API, file schema

### Phase 2: Core USB Operations
3. **esptool Wrapper** — Firmware flashing
   - *Why next:* Most common operation; validates USB integration
   - *Deliverable:* flash_firmware() tool, chip detection

4. **mpremote Wrapper** — File deployment
   - *Why immediately after:* Completes flash+deploy workflow
   - *Deliverable:* deploy_files() tool, soft reset

5. **Serial Lock** — Mutex enforcement
   - *Why after both USB tools:* Prevents race conditions
   - *Deliverable:* Lock mechanism, test concurrent calls

### Phase 3: Monitoring & Control
6. **Serial Monitor** — Real-time output streaming
   - *Why after core ops:* Completes debugging workflow
   - *Deliverable:* read_serial() tool, REPL input

### Phase 4: Advanced Features
7. **WiFi OTA Service** — Over-the-air updates
   - *Why later:* Not critical path; USB deployment sufficient for MVP
   - *Deliverable:* update_ota() tool, WebREPL integration

8. **Git Sync Service** — Repository pulling & deployment
   - *Why last:* Builds on deploy_files(), optional automation
   - *Deliverable:* sync_repo() tool, syntax validation

---

## Open Architectural Questions

### Q1: Single ESP32 vs. Multi-Board Support

**Status:** Pending (PROJECT.md says "single board at a time for now")

**Current Architecture Assumption:** Multi-board ready (state manager stores board list, serial lock per device)

**Decision Point:**
- If staying single-board: Simplify to hard-coded `/dev/ttyUSB0`
- If expanding to multi-board: Implement auto-discovery of USB devices, board naming

**Recommendation:** Build multi-board support now (small overhead) — keeps options open, enables testing with multiple ESP32s.

---

### Q2: Firmware Caching Strategy

**Status:** Design decision needed

**Options:**
1. **Cache locally on Pi** (`~/.cache/micropython-firmware/`) — Fast re-flashes, offline capable
   - Pro: Faster deployments, works without internet
   - Con: Disk space, manual cleanup needed

2. **Always fetch fresh** — Simple, no disk management
   - Pro: Always latest version
   - Con: Slow, requires internet, fragile on flaky networks

3. **Hybrid:** Cache with TTL (e.g., re-download every 7 days)
   - Pro: Balance between speed and freshness
   - Con: More code complexity

**Recommendation:** Hybrid with TTL. Microcontroller projects iterate fast; stale firmware is risky.

---

### Q3: Error Recovery & Retry Logic

**Status:** Implementation detail, but architectural impact

**Problem:** USB/WiFi operations fail silently sometimes (board hung, cable disconnected)

**Current Approach:**
- esptool: Single attempt, fail fast
- mpremote: 30s timeout per file, fail on timeout
- OTA: 3x retry with exponential backoff

**Design Decision:** Should MCP server auto-retry failed operations, or should Claude decide?

**Recommendation:** MCP server should retry once for timeouts only (recoverable errors); fail immediately for permission/device-not-found (hard errors). Log all retries. Let Claude decide on second failure.

---

### Q4: Board Discovery and Provisioning

**Status:** Pending

**Current Approach:** Manual `/dev/ttyUSB0` specification

**Better Approach:** Auto-discovery by chip ID and serial number

```python
def list_boards():
    """Discover all connected ESP32 boards"""
    # Use esptool.py list_ports or pyserial
    return [
        {"port": "/dev/ttyUSB0", "chip": "ESP32-S3", "serial": "A1B2C3D4"},
        {"port": "/dev/ttyUSB1", "chip": "ESP32-C3", "serial": "X9Y8Z7W6"}
    ]
```

**Recommendation:** Implement early (Phase 1) — makes multi-board support seamless, improves UX.

---

### Q5: WebREPL vs. Serial for REPL Access

**Status:** Design choice

**Options:**
1. **Serial REPL only** — Connect via USB, use `screen` or similar
   - Pro: Always available, reliable
   - Con: Requires USB cable, doesn't work over WiFi

2. **WebREPL only** — Use WiFi REPL endpoint
   - Pro: Wireless, enables remote access
   - Con: Requires board to run WebREPL daemon, adds complexity

3. **Both** — Prefer serial, fall back to WebREPL
   - Pro: Best of both
   - Con: Code complexity

**Current Architecture:** Supports both (serial monitor + OTA via WebREPL)

**Recommendation:** Start with serial (simpler), add WebREPL support in Phase 4 as convenience feature.

---

### Q6: MCP Server Language

**Status:** Pending

**Options:**
1. **Python** (recommended for this project)
   - Pro: Aligns with MicroPython ecosystem, reuses Espressif tooling knowledge, easy esptool/mpremote integration
   - Con: Slower than Node, requires Python 3.9+

2. **Node.js**
   - Pro: Faster, async/await paradigm good for I/O
   - Con: More distance from MicroPython culture, harder subprocess management

3. **Rust**
   - Pro: Extremely fast, type-safe
   - Con: Overkill, longer dev cycle, smaller MCP library ecosystem

**Recommendation:** Python. The project is Pi-based (not resource-constrained), performance is not critical, and alignment with MicroPython ecosystem is valuable.

---

## Data Persistence & Logging

**Recommendation:** Structure state storage for debuggability

```
~/.esp32-station/
├── config.json                 # Service configuration
├── boards.json                 # Detected boards + last-known state
├── logs/
│   ├── mcp-server.log         # Main server activity
│   ├── flash-{timestamp}.log  # Each flash operation
│   ├── deploy-{timestamp}.log # Each deployment
│   └── serial-{device}.log    # Per-device serial output
└── state/
    ├── deployments.json       # Audit trail (all deployments)
    └── firmware-cache/        # Downloaded firmware binaries
```

**Logging Level:** Debug-by-default on Pi (Claude can ask for logs). Rotate logs daily, keep 7 days.

---

## Security Considerations (Deferred to Phase 3+)

**Current Assumption:** Trusted LAN only (per PROJECT.md)

**Gaps to Address Later:**
- Board authentication (WebREPL password, SSH key for Git)
- MCP server authentication (API token or mTLS)
- Encrypted storage of credentials
- Rate limiting (prevent brute-force)
- Audit logging (who did what, when)

**Recommendation:** Out of scope for MVP. Add after Phase 2.

---

## Summary

**Recommended Architecture:**
- **MCP Server** (HTTP transport) as central orchestrator on Pi
- **Sub-services** as decoupled Python subprocess handlers
- **Serial lock** to prevent USB conflicts
- **Persistent state** for board inventory and deployment history
- **Build order:** Foundation → USB ops → Monitoring → Advanced features

**Key Design Principles:**
1. **Isolation:** Each major operation (flash, deploy, monitor) runs in its own subprocess
2. **Serialization:** USB operations queue via mutex; no concurrent access
3. **Persistence:** Daemon survives Claude disconnections; full audit trail
4. **Observability:** Detailed logging, history, error recovery
5. **Extensibility:** Clean separation of MCP interface from service implementations

**Confidence Assessment:**
- **Component design:** MEDIUM-HIGH (aligns with MicroPython ecosystem patterns)
- **MCP transport choice:** MEDIUM (HTTP preferred, needs validation with MCP SDK)
- **Serial safety:** HIGH (standard mutex approach, well-proven)
- **Scalability:** MEDIUM (single-board assumption; multi-board ready but untested)
- **Implementation complexity:** MEDIUM (MCP integration is main unknown)
