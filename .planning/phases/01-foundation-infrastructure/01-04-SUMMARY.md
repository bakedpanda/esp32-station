---
phase: 01-foundation-infrastructure
plan: "04"
subsystem: infra
tags: [fastmcp, mcp, systemd, streamable-http, uvicorn]

requires:
  - phase: 01-02
    provides: list_boards, detect_chip, load_board_state
  - phase: 01-03
    provides: flash_firmware
provides:
  - FastMCP server with 4 registered tools (list_connected_boards, identify_chip, flash_micropython, get_board_state)
  - streamable-http transport on 0.0.0.0:8000
  - systemd unit for auto-start on boot with Restart=on-failure
affects: []

tech-stack:
  added: [mcp[cli]>=1.26.0, uvicorn]
  patterns: [host/port set on FastMCP() constructor not run(), streamable-http not SSE]

key-files:
  created: []
  modified: [mcp_server.py, esp32-station.service]

key-decisions:
  - "host/port must be set on FastMCP() constructor — FastMCP.run() does not accept them"
  - "transport=streamable-http (not SSE — deprecated in Claude Code since MCP spec 2025-03-26)"
  - "User=esp32 in service file (not pi — custom username on this install)"

requirements-completed: [MCP-01, MCP-02, MCP-03]

duration: 15min
completed: 2026-03-29
---

# Phase 01 Plan 04: MCP Server + systemd Summary

**FastMCP server with 4 ESP32 tools on streamable-http://0.0.0.0:8000, registered with Claude Code, running as systemd daemon**

## Performance

- **Duration:** 15 min
- **Started:** 2026-03-29T00:50:00Z
- **Completed:** 2026-03-29T01:00:00Z
- **Tasks:** 2 (1 automated + 1 human checkpoint)
- **Files modified:** 2

## Accomplishments
- Implemented `mcp_server.py` with 4 MCP tools wiring board_detection and firmware_flash modules
- Verified server reachable on LAN (HTTP 406 — correct MCP response to non-MCP client)
- Systemd service installed and enabled for auto-start on boot
- Registered with Claude Code: `claude mcp add --transport http esp32-station http://raspberrypi.local:8000/mcp`

## Task Commits

1. **Task 1: Implement mcp_server.py** - `192d338` (feat)
2. **Fix: move host/port to FastMCP() constructor** - `5996176` (fix)

## Files Created/Modified
- `mcp_server.py` — 4 MCP tools registered, streamable-http, 0.0.0.0:8000
- `esp32-station.service` — User=esp32, venv/bin/python3, Restart=on-failure

## Decisions Made
- `host`/`port` belong on `FastMCP("esp32-station", host="0.0.0.0", port=8000)` — not on `.run()`
- Username `esp32` used throughout (not the default `pi`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FastMCP.run() does not accept host/port kwargs**
- **Found during:** Human verification on Pi
- **Issue:** `TypeError: FastMCP.run() got an unexpected keyword argument 'host'` — API changed in mcp>=1.26
- **Fix:** Moved `host="0.0.0.0", port=8000` to `FastMCP()` constructor
- **Files modified:** mcp_server.py
- **Verification:** Server started, HTTP 406 returned from LAN
- **Committed in:** 5996176

---

**Total deviations:** 1 auto-fixed (API mismatch)
**Impact:** Necessary fix, no scope change.

## Issues Encountered
None beyond the API fix above.

## Next Phase Readiness
- MCP server registered and reachable at http://raspberrypi.local:8000/mcp
- All 4 tools available in Claude Code via `/mcp`
- Phase 1 complete — ready for Phase 2 (board discovery enhancements)

---
*Phase: 01-foundation-infrastructure*
*Completed: 2026-03-29*
