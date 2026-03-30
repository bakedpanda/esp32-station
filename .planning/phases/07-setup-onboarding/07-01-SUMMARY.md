---
phase: 07-setup-onboarding
plan: 01
subsystem: testing
tags: [pytest, tdd, setup-script, readme, contracts]

# Dependency graph
requires:
  - phase: 03-wifi-advanced
    provides: all 11 Phase 1-3 MCP tools registered and validated
provides:
  - Pytest test scaffold defining SETUP-01 acceptance criteria (setup.sh structure)
  - Pytest test scaffold defining SETUP-03 acceptance criteria (README.md content)
  - Failing tests that confirm exactly which Phase 5-6 tools and modules are missing from README
affects: [07-02-setup-sh-plan, 07-03-readme-update-plan]

# Tech tracking
tech-stack:
  added: []
  patterns: [TDD contract-first: write failing tests before implementation plans run]

key-files:
  created:
    - tests/test_setup_script.py
    - tests/test_readme.py
  modified: []

key-decisions:
  - "Used pytest.mark.skipif on all setup.sh tests so they skip cleanly (not error) before Plan 02 creates setup.sh"
  - "test_existing_credentials_overwrite_guard checks for 'verwrite' (matches both 'Overwrite' and 'overwrite') to avoid case sensitivity issues"

patterns-established:
  - "Contract-first TDD: test files written before implementation; tests define targets, not outcomes"
  - "Parametrized tests for tool/module presence checks — easy to extend when new tools are added"

requirements-completed: [SETUP-01, SETUP-03]

# Metrics
duration: 3min
completed: 2026-03-30
---

# Phase 7 Plan 01: Setup Onboarding Test Scaffolds Summary

**TDD contracts for setup.sh (20 structural tests) and README.md (parametrized tool/module checks) that define the acceptance criteria Plans 02 and 03 must satisfy**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T00:05:00Z
- **Completed:** 2026-03-30T00:07:43Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `tests/test_setup_script.py` with 20 structural content tests covering setup.sh shebang, idempotency guards, credential prompts, file paths, systemd patching, and user-facing output
- Created `tests/test_readme.py` with parametrized tests covering all 15 MCP tools, 12 architecture modules, and 5 additional README structural requirements
- Confirmed test behavior: test_setup_script.py skips 19 tests cleanly and fails 1 (setup.sh missing); test_readme.py passes 21 existing-content tests and fails 11 future-state tests identifying gaps for Plans 02-03

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test_setup_script.py** - `19e12ce` (test)
2. **Task 2: Create test_readme.py** - `2ccd6a1` (test)

## Files Created/Modified
- `tests/test_setup_script.py` — 20 tests: shebang+strict mode, idempotency (clone/venv/dialout/service), credential prompts (ssid/password/webrepl), file path/keys/permissions, venv pip isolation, service sed-patch, endpoint print, MCP add command, python3-venv preflight, overwrite guard, re-login notice
- `tests/test_readme.py` — Parametrized: 15 tool names, 12 architecture modules; plus MCP registration command, hostname/IP note, setup.sh reference, phases 4-6 status rows

## Decisions Made
- Used `pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")` on all test_setup_script.py tests except `test_setup_sh_exists` so the entire file is safely importable before Plan 02 runs
- `test_existing_credentials_overwrite_guard` checks for `"verwrite"` substring (matches both `Overwrite` and `overwrite`) per Pitfall 5 in the context notes

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The project venv is not present in this worktree; used the shared venv from `agent-abe4d031` worktree for verification. Tests ran correctly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 02 (setup.sh creation) has 20 concrete grep-verifiable targets to hit
- Plan 03 (README update) has 11 currently-failing tests that will pass once it adds the 4 Phase 5-6 tools, 5 missing modules, setup.sh reference, and phases 4-6 status rows
- Both test files are safe to run at any point — no import errors, no external dependencies

---
*Phase: 07-setup-onboarding*
*Completed: 2026-03-30*
