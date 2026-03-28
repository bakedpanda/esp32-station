---
phase: 1
slug: foundation-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-28
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini or pyproject.toml — Wave 0 installs |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-xx-01 | TBD | 1 | BOARD-01 | unit | `pytest tests/test_board_detect.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-02 | TBD | 1 | BOARD-02 | unit | `pytest tests/test_board_detect.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-03 | TBD | 1 | BOARD-03 | unit | `pytest tests/test_board_detect.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-04 | TBD | 1 | BOARD-04 | unit | `pytest tests/test_board_detect.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-05 | TBD | 1 | FLASH-01 | unit | `pytest tests/test_flash.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-06 | TBD | 1 | FLASH-02 | unit | `pytest tests/test_flash.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-07 | TBD | 1 | FLASH-03 | unit | `pytest tests/test_flash.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-08 | TBD | 1 | FLASH-04 | integration | `pytest tests/test_flash.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-09 | TBD | 1 | FLASH-05 | unit | `pytest tests/test_flash.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-10 | TBD | 2 | MCP-01 | integration | `pytest tests/test_mcp_server.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-11 | TBD | 2 | MCP-02 | integration | `pytest tests/test_mcp_server.py -x -q` | ❌ W0 | ⬜ pending |
| 1-xx-12 | TBD | 2 | MCP-03 | unit | `pytest tests/test_mcp_server.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_board_detect.py` — stubs for BOARD-01, BOARD-02, BOARD-03, BOARD-04
- [ ] `tests/test_flash.py` — stubs for FLASH-01 through FLASH-05
- [ ] `tests/test_mcp_server.py` — stubs for MCP-01, MCP-02, MCP-03
- [ ] `tests/conftest.py` — shared fixtures (mock esptool, mock USB ports)
- [ ] `pytest` + `pytest-asyncio` — if not yet installed in venv

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Physical USB board detection | BOARD-01 | Requires hardware | Connect board, run `list_boards` tool, verify chip type displayed |
| Physical firmware flash | FLASH-01 | Requires hardware | Run `flash_firmware` tool on connected board, verify flash completes |
| LAN reachability from main machine | MCP-02 | Requires network setup | Run `curl http://raspberrypi.local:8000/mcp` from main machine |
| Offline flash (network down) | FLASH-04 | Requires network disruption | Disconnect Pi from internet, attempt flash, verify local cache used |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
