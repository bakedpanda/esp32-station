---
phase: 02-core-usb-workflows
plan: 01
subsystem: deployment
tags: [mpremote, subprocess, file-deploy, integrity-check, error-dict]

# Dependency graph
requires:
  - phase: 01-foundation-infrastructure
    provides: board_detection error-dict pattern and subprocess wrapping conventions
provides:
  - deploy_file() — single-file USB deploy with space check and integrity verify
  - deploy_directory() — recursive project deploy with exclusion filtering
  - check_board_space() — mpremote df parser with 70%/90% thresholds
  - verify_file_size() — post-transfer board-side os.stat integrity check
affects: [02-02-repl-access, 03-ota-deployment, mcp-server-tool-wiring]

# Tech tracking
tech-stack:
  added: [mpremote subprocess wrapper]
  patterns: [error-dict returns (never raise), subprocess isolation, TDD RED/GREEN]

key-files:
  created:
    - tools/file_deploy.py
    - tests/test_file_deploy.py

key-decisions:
  - "Parse mpremote df output by regex on bytes-total/bytes-used fields — more robust than column index parsing"
  - "Single pre-flight df call per deploy_directory() invocation rather than per-file to avoid repeated overhead"
  - "remote_path defaults to filename only (board root) for deploy_file; directory preserves relative path hierarchy"

patterns-established:
  - "Error-dict pattern: all functions return {'error': 'snake_code', 'detail': '...'} on failure, never raise"
  - "Space threshold constants (SPACE_WARN_PCT, SPACE_FAIL_PCT) at module level for easy adjustment"
  - "Exclusion sets (DEPLOY_EXCLUDE_DIRS, DEPLOY_EXCLUDE_EXTS) defined as module-level constants"

requirements-completed: [DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04]

# Metrics
duration: 4min
completed: 2026-03-29
---

# Phase 02 Plan 01: File Deployment Summary

**mpremote-backed file deploy with 70%/90% space thresholds and post-transfer os.stat integrity verification**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-29T01:27:53Z
- **Completed:** 2026-03-29T01:31:00Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- Implemented `tools/file_deploy.py` with `deploy_file()`, `deploy_directory()`, `check_board_space()`, and `verify_file_size()`
- Filesystem space check parses `mpremote df` output: warns at 70% (deploy proceeds), hard-fails at 90% (deploy stops)
- Post-transfer integrity verification reads remote file size via `mpremote exec` and compares to local `os.stat()`
- `deploy_directory()` filters out `__pycache__/`, `.git/`, `tests/`, `.planning/`, and `*.pyc` files before deploying
- All 7 tests pass; 24/24 total tests pass (zero regressions)

## Task Commits

Each task committed atomically:

1. **RED — Failing tests** - `3d9fde9` (test)
2. **GREEN — Implementation + test constant fix** - `d94436e` (feat)

_TDD task: two commits (RED failing tests, then GREEN implementation)_

## Files Created/Modified

- `/mnt/anton/Claude/ESP32-server/.claude/worktrees/agent-a25efc78/tools/file_deploy.py` — Core deploy module: check_board_space, verify_file_size, deploy_file, deploy_directory
- `/mnt/anton/Claude/ESP32-server/.claude/worktrees/agent-a25efc78/tests/test_file_deploy.py` — 7 tests covering all decision points (space warn, space fail, integrity pass, integrity fail, exclusion filter, success, board unreachable)

## Decisions Made

- Regex-based df output parsing instead of column-splitting: `mpremote df` output format is `/ : NNN bytes total, NNN bytes used, NNN bytes free` — regex on bytes fields is more stable than column index arithmetic.
- Single pre-flight space check in `deploy_directory()`: one `df` call before the loop avoids per-file overhead; the space situation won't change mid-deploy in practice.
- `remote_path` in `deploy_file` defaults to `Path(local_path).name` (board root placement), which matches the most common MicroPython pattern of deploying scripts to `/`.

## Deviations from Plan

### Minor Adjustments

**1. [Rule 1 - Bug] Test df format constant corrected during RED phase**
- **Found during:** Task 1 (RED — writing tests)
- **Issue:** Test helper constants initially used a column-format df output; the plan spec and mpremote's actual output use a colon-separated bytes format (`/ : NNN bytes total, NNN bytes used, NNN bytes free`)
- **Fix:** Updated `DF_OUTPUT_OK`, `DF_OUTPUT_WARN`, `DF_OUTPUT_FULL` constants in test file to match mpremote format before committing GREEN
- **Files modified:** tests/test_file_deploy.py
- **Verification:** All 7 tests pass with regex parser matching the corrected format
- **Committed in:** d94436e (GREEN commit)

---

**Total deviations:** 1 minor format correction (Rule 1 - corrected test constants to match actual mpremote output format)
**Impact on plan:** No scope change; test fidelity improved by using the actual mpremote df format.

## Issues Encountered

- The plan's `venv/bin/pytest` path did not exist in the worktree; resolved by locating the system venv at `/home/chris/esp32-station-venv/bin/pytest` and running with `PYTHONPATH` set to the worktree root.

## Known Stubs

None — `deploy_file()` and `deploy_directory()` are fully wired to real subprocess calls.

## Next Phase Readiness

- File deploy module complete and tested; ready for MCP server tool wiring (expose `deploy_file`/`deploy_directory` as MCP tools)
- No blockers; subprocess pattern is consistent with Phase 1 board detection and flashing tools

## Self-Check: PASSED

All expected files and commits verified present.

---
*Phase: 02-core-usb-workflows*
*Completed: 2026-03-29*
