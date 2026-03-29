---
phase: 03-wifi-advanced
plan: 01
subsystem: testing
tags: [pytest, webrepl, tdd, test-stubs]

# Dependency graph
requires:
  - phase: 02-core-usb-workflows
    provides: existing test patterns (test_file_deploy.py), tools/ module structure
provides:
  - vendored webrepl_cli.py for OTA WiFi subprocess calls
  - 5 failing test stubs for OTA WiFi (OTA-01, OTA-02)
  - 3 failing test stubs for GitHub deploy (DEPLOY-05)
  - pytest runnable in project venv
affects: [03-02-PLAN, 03-03-PLAN]

# Tech tracking
tech-stack:
  added: [pytest, pytest-asyncio, webrepl_cli.py (vendored)]
  patterns: [TDD RED stubs with ImportError gating]

key-files:
  created:
    - tools/vendor/webrepl_cli.py
    - tools/vendor/__init__.py
    - tests/test_ota_wifi.py
    - tests/test_github_deploy.py
  modified: []

key-decisions:
  - "Vendored webrepl_cli.py from micropython/webrepl rather than pip-installing third-party fork"
  - "Test stubs fail with ImportError (not NotImplementedError) to gate on module existence"

patterns-established:
  - "Wave 0 test-first: write failing stubs before implementation plans"
  - "Vendor scripts without pip packages into tools/vendor/"

requirements-completed: []

# Metrics
duration: 12min
completed: 2026-03-29
---

# Phase 3 Plan 01: Wave 0 Prerequisites Summary

**Vendored webrepl_cli.py and created 8 RED test stubs (5 OTA WiFi + 3 GitHub deploy) gating Phase 3 implementation plans**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-29T12:27:43Z
- **Completed:** 2026-03-29T12:39:43Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments
- Installed pytest and all project dependencies into venv (Python 3.14 compatible)
- Vendored webrepl_cli.py (10KB) from official micropython/webrepl repo
- Created 5 failing test stubs for OTA WiFi covering success, size limit, timeout, connection error, and missing CLI
- Created 3 failing test stubs for GitHub deploy covering success, clone timeout, and token leak prevention
- Verified all 42 existing tests still pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Install venv dependencies and vendor webrepl_cli.py** - `0b3ba00` (chore)
2. **Task 2: Write failing test stubs for OTA WiFi** - `307c50a` (test)
3. **Task 3: Write failing test stubs for GitHub deploy** - `13cf1dc` (test)

## Files Created/Modified
- `tools/vendor/webrepl_cli.py` - Vendored WebREPL CLI script for OTA file transfer
- `tools/vendor/__init__.py` - Package init for vendor directory
- `tests/test_ota_wifi.py` - 5 test stubs for deploy_ota_wifi (OTA-01, OTA-02)
- `tests/test_github_deploy.py` - 3 test stubs for pull_and_deploy_github (DEPLOY-05)

## Decisions Made
- Vendored webrepl_cli.py directly from micropython/webrepl master via curl (the `webrepl` pip package is a third-party fork with a different API)
- Test stubs import from not-yet-existing modules (tools.ota_wifi, tools.github_deploy) so they fail with ImportError rather than NotImplementedError -- this gates on module creation, not just function stubs
- Used --copies flag for venv creation due to symlink-unsupported filesystem, then manually created lib64 directory

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created venv with --copies and manual lib64 workaround**
- **Found during:** Task 1 (venv creation)
- **Issue:** Filesystem does not support symlinks; Python venv creates lib64 -> lib symlink
- **Fix:** Created lib64 as a copy of lib directory, then re-ran venv --copies successfully
- **Files modified:** venv/ (gitignored)
- **Verification:** venv/bin/pytest --version exits 0
- **Committed in:** N/A (venv is gitignored)

**2. [Rule 3 - Blocking] Used --no-compile for pip install on Python 3.14**
- **Found during:** Task 1 (pip install)
- **Issue:** pip wheel installation fails with AssertionError on pyc compilation under Python 3.14
- **Fix:** Used `pip install --no-compile` to skip bytecode compilation
- **Files modified:** venv/ (gitignored)
- **Verification:** All packages installed successfully
- **Committed in:** N/A (venv is gitignored)

---

**Total deviations:** 2 auto-fixed (both blocking issues)
**Impact on plan:** Both workarounds for Python 3.14 + symlink-less filesystem. No scope creep.

## Issues Encountered
- Python 3.14 has a bug in pip's wheel installer where it asserts on .pyc file existence after compilation; `--no-compile` flag works around it
- Worktree filesystem doesn't support symlinks, requiring manual lib64 directory creation for venv

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Test stubs ready for Plans 02 (OTA WiFi) and 03 (GitHub deploy) to turn GREEN
- webrepl_cli.py vendored and available for OTA implementation
- All existing tests (42) still passing

---
## Self-Check: PASSED

All 5 files verified present. All 3 task commits verified in git log.

---
*Phase: 03-wifi-advanced*
*Completed: 2026-03-29*
