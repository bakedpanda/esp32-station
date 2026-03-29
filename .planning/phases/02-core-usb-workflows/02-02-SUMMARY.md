---
phase: 02-core-usb-workflows
plan: "02"
subsystem: repl
tags: [mpremote, subprocess, micropython, serial, repl]

requires:
  - phase: 01-foundation-infrastructure
    provides: subprocess/error-dict patterns established in board_detection.py and firmware_flash.py

provides:
  - exec_repl(port, command) — run MicroPython expression on board via mpremote exec
  - read_serial(port) — capture recent board serial output without blocking
  - soft_reset(port) — soft-reset board via machine.soft_reset()
  - hard_reset(port) — hard-reset board via machine.reset()
  - All functions return error dicts; never raise to callers

affects: [03-ota-and-file-deployment, mcp_server]

tech-stack:
  added: []
  patterns:
    - "mpremote exec pattern: subprocess.run([mpremote, connect, port, exec, cmd], capture_output=True, text=True, timeout=N)"
    - "Timeout handling: except subprocess.TimeoutExpired -> return error dict (no propagation)"
    - "Reset success heuristic: returncode != 0 with empty stderr treated as success (board disconnects mid-exec)"

key-files:
  created:
    - tools/repl.py
    - tests/test_repl.py
  modified: []

key-decisions:
  - "soft_reset treats non-zero returncode with empty stderr as success — board disconnects mid-execution during reset"
  - "read_serial uses mpremote exec '' (empty command) to capture any buffered output without issuing a real command"

patterns-established:
  - "REPL exec pattern: wrap subprocess.run in try/except TimeoutExpired returning {'error': 'repl_timeout', 'detail': '...'}"

requirements-completed: [REPL-01, REPL-02, REPL-03, BOARD-03]

duration: 2min
completed: 2026-03-29
---

# Phase 02 Plan 02: REPL and Board Reset Summary

**exec_repl, read_serial, soft_reset, hard_reset via mpremote subprocess — all returning error dicts, never raising**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-29T01:28:00Z
- **Completed:** 2026-03-29T01:30:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Implemented `exec_repl(port, command)` running `mpremote connect <port> exec <command>` with timeout and error-dict returns
- Implemented `read_serial(port)` using mpremote exec with empty command to capture buffered serial output without blocking
- Implemented `soft_reset()` and `hard_reset()` via `machine.soft_reset()` / `machine.reset()` with correct non-zero-exit handling
- Added `tests/test_repl.py` with 8 tests covering all success and failure paths; full test suite passes (25/25)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement tools/repl.py** - `2c43886` (feat)

## Files Created/Modified

- `tools/repl.py` - REPL execution, serial read, and board reset via mpremote subprocess
- `tests/test_repl.py` - 8 unit tests covering REPL-01, REPL-02, REPL-03, BOARD-03

## Decisions Made

- `soft_reset` treats non-zero returncode with empty stderr as success — the board disconnects mid-execution when reset fires, so a non-zero exit code without error text is expected behavior.
- `read_serial` uses `mpremote exec ""` (empty command) as the mechanism for capturing buffered board output; mpremote has no dedicated serial-read subcommand.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The plan referenced `venv/bin/pytest` but no venv exists in the worktree. Found project venv at `/home/chris/esp32-station-venv/bin/pytest`. Used that path; all tests passed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- REPL foundation complete; `tools/repl.py` exports `exec_repl`, `read_serial`, `soft_reset`, `hard_reset`
- Ready for MCP server wiring (plan 02-03 or later) to expose these as MCP tools
- No blockers or concerns

---
*Phase: 02-core-usb-workflows*
*Completed: 2026-03-29*

## Self-Check: PASSED

- tools/repl.py: FOUND
- tests/test_repl.py: FOUND
- 02-02-SUMMARY.md: FOUND
- commit 2c43886: FOUND
