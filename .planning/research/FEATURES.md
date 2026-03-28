# Features Research — ESP32 MicroPython Dev Station

**Domain:** IoT device management server (firmware deployment + REPL access over MCP)
**Researched:** 2026-03-28
**Overall Confidence:** MEDIUM (training knowledge of MicroPython ecosystem + verified esptool/rshell capabilities)

## Table Stakes

Features that must exist for this tool to be useful as a dev station. Without these, it's not a development tool—it's incomplete infrastructure.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Firmware flashing via USB** | Core requirement in PROJECT.md; every MicroPython dev tool (esptool, rshell, pyboard) includes this | Medium | Must support ESP32 variants (classic, S2/S3, C3/C6); auto-detect chip type for correct firmware selection |
| **File deployment to board** | PRIMARY use case: push code to ESP32 without manual REPL. All tools (rshell, mpremote, pyboard) support this | Medium | Via USB serial (primary); later OTA. Must handle single files + project directories |
| **REPL/serial access** | Must run commands on board and read output. Core to debugging and validation. rshell, mpremote, WebREPL all provide this | Low | Interactive shell + execute single commands; capture output for Claude |
| **Board detection/enumeration** | Without knowing what's connected and accessible, you can't deploy. Standard in all tools | Low | List connected boards, identify by port/chip type, show connectivity status |
| **Chip identification** | Critical for firmware selection—flashing wrong firmware bricks board. esptool includes this | Low | Auto-detect ESP32 variant on connection; prevent user from flashing incompatible firmware |
| **MCP server interface** | The entire value prop: Claude calls tools directly. PROJECT.md mandates this | Medium | All deployment/REPL/management features must be callable as MCP tools |
| **Error handling + feedback** | Flash fails? File sync fails? REPL times out? Must report clearly to Claude | Medium | Detailed error messages, recovery suggestions, clear failure modes |

## Differentiators

Features that elevate this beyond a generic Pi-based serial wrapper. These add real value but aren't strictly required for MVP.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **OTA (over-the-air) updates** | Deploy without USB. Essential for remote/already-deployed boards. WebREPL is standard MicroPython approach | High | Requires board to run WebREPL or custom OTA server; handles WiFi + reliability |
| **GitHub integration** | "Deploy this commit/branch" without manual Git pull on Pi. Tighter user workflow | Medium | Clone/pull repo, specify branch/commit, deploy directly to board. Requires Git on Pi (standard) |
| **Incremental sync** | Don't re-upload unchanged files. Saves time, reduces serial chatter. rshell calls this "rsync" | Medium | Hash/timestamp-based detection; only push changed files + detect board-side deletions |
| **Firmware version tracking** | Know what's running on each board. Prevent firmware downgrade accidents | Low | Store version info on board (boot.py metadata); expose in status queries |
| **Concurrent multi-board support** | Manage multiple ESP32s on same Pi. Natural extension of rshell's design | High | Route commands to correct board by port/identifier; allow parallel REPL sessions |
| **Log streaming** | Real-time board output without polling. Claude can watch logs while testing | High | Subscribe to serial output, deliver as stream to MCP client; handle reconnects |
| **Persistent connection pooling** | Keep serial ports open between commands; avoid reconnect latency | Medium | Maintain open serial handles; timeout idle connections; graceful reconnect on board reset |
| **Health/status monitoring** | Show board state: connected? running? free memory? response time? | Low | Periodic ping + memory query; expose as tool for Claude to check status before operations |

## Anti-Features (v1)

Explicitly NOT building these. They increase scope, add complexity, or solve problems we don't have yet.

| Anti-Feature | Why Defer/Avoid | What to Do Instead |
|--------------|-----------------|-------------------|
| **Web UI / dashboard** | Claude is the UI. No browser needed. Adds deployment complexity (Node, reverse proxy, etc.) | Claude interface IS the dashboard—full transparency through MCP tools |
| **Multi-user / authentication** | Trusted LAN only (PROJECT.md). Security hardening is out of scope | Trust network boundary; no auth layer |
| **Fleet inventory database** | Single board at a time (PROJECT.md). Inventory is local filesystem (boards.json) | Manual board list; extend only if MVP validates need |
| **Non-MicroPython firmware** | Arduino, ESP-IDF, Zephyr all have different workflows. Out of scope per PROJECT.md | Reject non-MicroPython gracefully; document why |
| **Wireless provisioning** | WiFi credentials setup via Bluetooth/captive portal. Too complex for v1 | Manual WiFi config in code before flashing; or assume network already configured |
| **Advanced debugging** | GDB integration, breakpoints, memory dumps. Debuggers exist (esp-idf-tools); not our focus | REPL + log output sufficient for tinkering use case |
| **IDE integration** | VSCode extension, Thonny plugin, etc. Adds maintenance burden | Claude is the IDE; no separate plugin needed |
| **Firmware building/compilation** | Compile MicroPython from source. Pre-built official releases are sufficient | Use official MicroPython releases; skip custom builds for v1 |
| **Storage/artifact management** | Archive old firmware versions, save deployment history, etc. | Keep only current firmware; user keeps Git history |

## MCP Tool Inventory

Claude will call these as MCP tools through the server. Each maps to one or more internal operations.

### Firmware Management

```
flash_firmware(
  board_id: str,           # /dev/ttyUSB0 or identifier from list_boards
  firmware_path: str,      # Path to .bin firmware file or URL to download
  chip_type?: str,         # ESP32, ESP32-S2, ESP32-S3, etc. Auto-detect if not provided
  erase_flash?: bool       # Full erase vs minimal? Default: minimal
) -> { success: bool, output: str, board_id: str, new_version?: str }
```

```
list_boards() -> [
  {
    port: str,             # /dev/ttyUSB0
    chip_type: str,        # ESP32-S3 (auto-detected)
    firmware_version?: str, # From boot.py or None if unknown
    connected: bool,       # Can we talk to it?
  }
]
```

### Code Deployment

```
deploy_files(
  board_id: str,
  files: [
    { src_path: str, dst_path: str },  # /home/user/project/main.py -> /main.py
    ...
  ],
  mode?: "force" | "sync"              # force=upload all, sync=only changed
) -> { success: bool, uploaded: [str], skipped: [str], errors?: [str] }
```

```
sync_project(
  board_id: str,
  local_dir: str,        # /home/user/project/
  board_dir?: str        # /flash (default)
) -> { success: bool, summary: { uploaded: int, deleted: int, skipped: int } }
```

```
pull_github_and_deploy(
  board_id: str,
  repo_url: str,         # https://github.com/user/project.git
  branch?: str,          # main (default)
  target_dir?: str       # /tmp/repo or user-specified
) -> { success: bool, commit_hash: str, deployed_files: [str], errors?: [str] }
```

### REPL / Serial Interaction

```
run_command(
  board_id: str,
  command: str           # Python code: "print(2+2)"
) -> { output: str, error?: str, exception?: str }
```

```
get_repl_session(
  board_id: str,
  timeout?: int          # seconds to wait for response
) -> { session_id: str, ready: bool }
```

```
repl_execute_and_read(
  board_id: str,
  code: str,
  timeout?: int
) -> { output: str, error?: str, status: "ok" | "timeout" | "error" }
```

### Board State & Monitoring

```
get_board_status(
  board_id: str
) -> {
  connected: bool,
  chip_type: str,
  firmware_version?: str,
  uptime_seconds?: int,
  free_memory_bytes?: int,
  response_time_ms: int
}
```

```
stream_logs(
  board_id: str,
  follow?: bool          # Keep connection open and stream new output
) -> EventStream of { timestamp: str, output: str }
```

### Management

```
identify_board(
  port: str
) -> { chip_type: str, unique_id?: str, version?: str }
```

```
reset_board(
  board_id: str,
  soft?: bool            # soft=REPL Ctrl-D, hard=USB reset
) -> { success: bool, output: str }
```

```
check_board_health(
  board_id: str
) -> {
  accessible: bool,
  can_run_commands: bool,
  filesystem_ok: bool,
  free_space_bytes?: int,
  recommendations: [str]
}
```

## Feature Dependencies

Critical ordering and prerequisites for implementation.

```
[Foundation]
    ↓
list_boards() + identify_board()
    ↓
get_repl_session() + run_command()      [REPL layer]
    ↓
deploy_files()                          [Deploy layer]
    ↓
flash_firmware()                        [Firmware layer — requires knowing chip type]
    ↓
[Value-adds]
    ├─ sync_project() (extends deploy_files)
    ├─ pull_github_and_deploy() (extends deploy + Git)
    ├─ get_board_status() (extends run_command)
    ├─ stream_logs() (extends REPL/serial)
    ├─ reset_board() (uses run_command + USB control)
    └─ check_board_health() (uses all above)

[OTA updates]
    ├─ Requires: get_repl_session() + custom OTA server/WebREPL
    └─ Not in MVP but enabled by core layer
```

## Implementation Roadmap (Feature Sequence)

**Phase 1: Core (MVP)**
1. `list_boards()` + `identify_board()` — Know what's connected
2. `get_repl_session()` + `run_command()` — Talk to boards
3. `deploy_files()` — Push code to board (USB serial)
4. `flash_firmware()` — Flash MicroPython, auto-detect chip

**Phase 2: Value-adds**
1. `sync_project()` — Incremental deployment
2. `get_board_status()` — Health monitoring
3. `reset_board()` — Programmatic resets
4. `pull_github_and_deploy()` — Direct repo → board

**Phase 3: Streaming & Advanced**
1. `stream_logs()` — Real-time output subscription
2. `check_board_health()` — Diagnostics
3. OTA update infrastructure (WebREPL-based or custom)

## Complexity Scoring Summary

| Tier | Features | Effort | Risk |
|------|----------|--------|------|
| **Trivial** | list_boards, identify_board, run_command, reset_board | <1d | Low |
| **Easy** | get_board_status, deploy_files, check_board_health | 1-2d | Low-Med |
| **Medium** | flash_firmware (multi-chip), sync_project, get_repl_session | 2-3d | Medium |
| **Hard** | stream_logs (async events), pull_github_and_deploy (Git), OTA updates | 3-5d | High |

## Sources

**Verified via WebFetch (HIGH confidence):**
- esptool GitHub repo: Flashing, provisioning, interaction capabilities
- rshell GitHub repo: File management, REPL, multi-device support
- MicroPython tools directory: pyboard.py, mpremote, uf2conv, build tools

**Training knowledge (MEDIUM confidence):**
- MicroPython REPL and serial protocol standards
- WebREPL as standard OTA mechanism
- Common failure modes in MicroPython deployment (baud rate, chip detection, partition tables)

**Not verified (would need current docs):**
- Exact mpremote feature parity vs rshell
- Latest MicroPython OTA frameworks (2025-2026)
- ESP32 S3/C6 specific quirks in 2026 tooling

