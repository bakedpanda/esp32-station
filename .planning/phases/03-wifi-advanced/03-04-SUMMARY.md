---
phase: 03-wifi-advanced
plan: 04
subsystem: api
tags: [mcp, fastmcp, tool-registration, webrepl, github, serial-lock]

# Dependency graph
requires:
  - phase: 03-wifi-advanced/02
    provides: "deploy_ota_wifi() function for WiFi OTA"
  - phase: 03-wifi-advanced/03
    provides: "pull_and_deploy_github() function for GitHub deploy"
provides:
  - "deploy_ota_wifi MCP tool — WiFi OTA callable by Claude"
  - "pull_and_deploy_github MCP tool — GitHub clone+deploy callable by Claude"
  - "11 total MCP tools registered in esp32-station server"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns: ["WiFi tool without SerialLock (no serial port)", "GitHub tool with SerialLock wrapping USB deploy"]

key-files:
  created: []
  modified: [mcp_server.py]

key-decisions:
  - "deploy_ota_wifi has no SerialLock — WiFi operations do not touch serial ports (D-06)"
  - "pull_and_deploy_github wraps call in SerialLock(port) — reuses USB deploy pipeline (D-12)"
  - "Aliased imports (_deploy_ota_wifi, _pull_and_deploy_github) to avoid name collision with tool functions"

patterns-established:
  - "WiFi tool pattern: no SerialLock, direct passthrough to module function"
  - "Aliased import pattern: from tools.X import func as _func to avoid collision with @mcp.tool() function"

requirements-completed: [OTA-01, OTA-02, DEPLOY-05]

# Metrics
duration: 3min
completed: 2026-03-29
---

# Phase 03 Plan 04: MCP Wiring Summary

**Two new @mcp.tool() registrations (deploy_ota_wifi, pull_and_deploy_github) wired into mcp_server.py completing Phase 3 with 11 total tools**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-29T12:56:58Z
- **Completed:** 2026-03-29T12:59:50Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Wired deploy_ota_wifi as MCP tool without SerialLock (WiFi-only, no serial port)
- Wired pull_and_deploy_github as MCP tool with SerialLock(port) for USB deploy serialization
- Server now exposes 11 total MCP tools; all 12 relevant tests pass GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Add deploy_ota_wifi and pull_and_deploy_github to mcp_server.py** - `b600b5e` (feat)

## Files Created/Modified
- `mcp_server.py` - Added 2 imports (aliased) and 2 @mcp.tool() registrations with full docstrings

## Decisions Made
- Used aliased imports (`_deploy_ota_wifi`, `_pull_and_deploy_github`) to avoid name collisions with the @mcp.tool() wrapper functions — consistent with the plan's interface spec
- No SerialLock on deploy_ota_wifi per D-06 — WiFi operations are port-free
- SerialLock(port) wrapping on pull_and_deploy_github per D-12 — USB deploy must serialize

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failures (`test_deploy_file_returns_error_dict_on_failure`, `test_exec_repl_returns_error_dict_on_timeout`) due to read-only filesystem preventing SerialLock directory creation in test environment. These are environment-specific, not caused by this plan's changes. All 12 tests targeting this plan's scope pass.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 3 is complete: all 3 requirements (OTA-01, OTA-02, DEPLOY-05) implemented and registered
- ESP32 station MCP server now has full USB + WiFi + GitHub deployment capabilities
- 11 MCP tools available for Claude to call

## Known Stubs
None - all tools are fully wired to their implementation modules.

## Self-Check: PASSED

- FOUND: mcp_server.py
- FOUND: 03-04-SUMMARY.md
- FOUND: commit b600b5e
- Tool count: 11 (correct)

---
*Phase: 03-wifi-advanced*
*Completed: 2026-03-29*
