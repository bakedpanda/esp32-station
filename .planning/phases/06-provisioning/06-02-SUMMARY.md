---
phase: 06-provisioning
plan: 02
subsystem: provisioning
tags: [boot.py, wifi, webrepl, mcp, mpremote, template]

# Dependency graph
requires:
  - phase: 06-01
    provides: credentials utility (load_credentials), boot.py template
  - phase: 02
    provides: file_deploy (deploy_file), serial_lock (SerialLock)
  - phase: 01
    provides: firmware_flash (flash_firmware), MCP server skeleton
provides:
  - deploy_boot_config MCP tool (#15) for WiFi + WebREPL boot.py provisioning
  - flash_micropython user_action guidance on erase failure
  - flash_micropython always-erase documentation
affects: [07-setup, provisioning-workflow]

# Tech tracking
tech-stack:
  added: []
  patterns: [template placeholder injection, user_action error enrichment]

key-files:
  created:
    - tools/boot_deploy.py
    - tests/test_boot_deploy.py
  modified:
    - mcp_server.py
    - tests/test_mcp_server.py
    - tests/test_flash.py

key-decisions:
  - "Temp file for boot.py is created, deployed, then deleted -- never persists on Pi"
  - "deploy_file mock uses side_effect to capture temp file content before os.unlink"
  - "flash_micropython user_action/reason keys added only on erase_failed error"

patterns-established:
  - "user_action key in error dicts for physical action guidance"
  - "Template injection via simple .replace() for boot.py generation"

requirements-completed: [PROV-01, PROV-02, PROV-03, PROV-04]

# Metrics
duration: 6min
completed: 2026-03-29
---

# Phase 6 Plan 2: Boot Deploy MCP Tool and Flash Guidance Summary

**deploy_boot_config MCP tool reads Pi-local WiFi creds, fills boot.py template, deploys via mpremote; flash_micropython enriched with always-erase docs and BOOT button user_action on failure**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-29T23:03:40Z
- **Completed:** 2026-03-29T23:09:26Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created tools/boot_deploy.py with deploy_boot_config that reads credentials, validates WebREPL password length, fills template placeholders, and deploys boot.py via mpremote
- Registered deploy_boot_config as MCP tool #15 (total now 15) with SerialLock protection
- Updated flash_micropython docstring to document always-erase behavior and BOOT button instructions
- Added user_action/reason fields to flash_micropython response on erase_failed errors
- 10 new tests (8 boot_deploy + 2 flash) all passing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create boot_deploy module with deploy_boot_config and tests** - `0817387` (feat, TDD)
2. **Task 2: Wire MCP tool, update flash docstring/guidance, update test expectations** - `c6604c5` (feat)

## Files Created/Modified
- `tools/boot_deploy.py` - deploy_boot_config function: creds -> template -> deploy
- `tests/test_boot_deploy.py` - 8 tests covering happy path, errors, hostname, placeholders
- `mcp_server.py` - Added deploy_boot_config as tool #15, updated flash_micropython
- `tests/test_mcp_server.py` - Updated expected tools list to 15
- `tests/test_flash.py` - Added test_erase_always_called and test_user_action_guidance

## Decisions Made
- Used side_effect in mock_deploy fixture to capture temp file content before it is deleted by os.unlink in the finally block
- Patched flash_firmware via patch.object on mcp_server module (not tools.firmware_flash) since mcp_server imports it at module level

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_user_action_guidance patching target**
- **Found during:** Task 2
- **Issue:** Plan specified `patch("tools.firmware_flash.flash_firmware", ...)` but mcp_server imports flash_firmware at module level, so the patch had no effect on the already-imported reference
- **Fix:** Changed to `patch.object(mcp_server, "flash_firmware", ...)` to target the imported reference
- **Verification:** test_user_action_guidance passes
- **Committed in:** c6604c5

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary fix for test correctness. No scope creep.

## Issues Encountered
- Pre-existing test failures in test_mcp_server.py (test_deploy_file_returns_error_dict_on_failure, test_exec_repl_returns_error_dict_on_timeout) due to read-only filesystem preventing SerialLock from creating lock files -- not caused by this plan's changes

## User Setup Required
None - no external service configuration required.

## Known Stubs
None - all functionality is fully wired.

## Next Phase Readiness
- All 15 MCP tools registered and functional
- Provisioning chain complete: flash_micropython -> deploy_boot_config -> check_board_health
- Ready for Phase 7 (setup.sh, documentation)

---
*Phase: 06-provisioning*
*Completed: 2026-03-29*
