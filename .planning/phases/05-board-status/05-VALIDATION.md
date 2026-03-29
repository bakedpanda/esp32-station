---
phase: 5
slug: board-status
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-29
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` (existing) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | STAT-01 | unit | `python -m pytest tests/test_board_status.py -v` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | STAT-02 | unit | `python -m pytest tests/test_board_health.py -v` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | STAT-03 | unit | `python -m pytest tests/test_mdns_discovery.py -v` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | STAT-01 | integration | `python -m pytest tests/test_mcp_status_tools.py -v` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_board_status.py` — stubs for STAT-01 (status collection via REPL)
- [ ] `tests/test_board_health.py` — stubs for STAT-02 (health check ping)
- [ ] `tests/test_mdns_discovery.py` — stubs for STAT-03 (mDNS discovery)
- [ ] `tests/test_mcp_status_tools.py` — stubs for MCP tool integration

*Existing test infrastructure (pytest, conftest.py) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| mDNS discovery finds real board | STAT-03 | Requires physical board advertising mDNS on LAN | 1. Configure board with mDNS. 2. Run discover_boards(). 3. Verify board appears in results. |
| WebREPL status over WiFi | STAT-01 | Requires board with WebREPL enabled on network | 1. Connect board to WiFi with WebREPL. 2. Run get_board_status(host=IP). 3. Verify all fields returned. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
