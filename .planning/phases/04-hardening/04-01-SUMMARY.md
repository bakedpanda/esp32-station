---
phase: 04-hardening
plan: 01
subsystem: testing, systemd
tags: [tech-debt, testing, service-config]
dependency_graph:
  requires: [03-04]
  provides: [clean-test-baseline]
  affects: [tests/test_mcp_server.py, esp32-station.service]
tech_stack:
  added: []
  patterns: [debt-verification-tests]
key_files:
  created: []
  modified:
    - tests/test_mcp_server.py
    - esp32-station.service
decisions:
  - "DEBT-01 already resolved -- test_detect_chip_success passes without changes"
  - "Added verification test for DEBT-02 to prevent regression"
metrics:
  duration_seconds: 233
  completed: "2026-03-29T18:31:24Z"
  tasks_completed: 1
  tasks_total: 1
---

# Phase 04 Plan 01: Fix v1.0 Tech Debt Summary

Removed stale planning comment from systemd service file, added Phase 3 tool assertions (5 to 7 tools), and added regression test for service file cleanliness.

## Task Results

| Task | Name | Commit | Status | Files |
|------|------|--------|--------|-------|
| 1 | Fix test_detect_chip_success and remove stale service comment | acf5c42 | Done | tests/test_mcp_server.py, esp32-station.service |

## What Was Done

**DEBT-01 (test_detect_chip_success):** Ran the test and confirmed it already passes. The patching of `tools.board_detection.BOARDS_JSON` and `tools.board_detection.STATE_DIR` to `tmp_path` works correctly. No code changes needed.

**DEBT-02 (stale service comment):** Removed line 1 (`# Full implementation in Plan 04 (01-04-PLAN.md)`) from `esp32-station.service`. File now starts with `[Unit]` as expected by systemd.

**DEBT-03 (Phase 3 tool assertions):** Updated `test_new_tools_registered` expected list from 5 tools to 7 tools, adding `deploy_ota_wifi` and `pull_and_deploy_github`. Updated docstring to reflect "Phase 2 + Phase 3". Added `test_systemd_no_stale_comments` to prevent regression on DEBT-02.

## Verification

- `test_detect_chip_success` -- PASSED
- `test_new_tools_registered` -- PASSED (7 tools)
- `test_systemd_no_stale_comments` -- PASSED
- `test_systemd_service_file_content` -- PASSED
- Full suite: 43 passed, 3 deselected (pre-existing environment issue with SerialLock in sandbox -- read-only `/home/chris/.esp32-station/locks/`)

## Deviations from Plan

None -- plan executed exactly as written.

## Known Stubs

None.

## Deferred Issues

3 pre-existing test failures (`test_deploy_file_returns_error_dict_on_failure`, `test_exec_repl_returns_error_dict_on_timeout`, `test_reset_board_invalid_type`) fail in sandboxed environments because `SerialLock.__enter__` tries to write to `/home/chris/.esp32-station/locks/`. These tests need `SerialLock` patching or `LOCK_DIR` override. Not caused by this plan's changes.

## Self-Check: PASSED

- [x] tests/test_mcp_server.py exists
- [x] esp32-station.service exists
- [x] 04-01-SUMMARY.md exists
- [x] Commit acf5c42 exists in git log
