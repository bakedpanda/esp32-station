---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Provisioning & Onboarding
current_phase: 5
current_plan: Not started
status: planning
last_updated: "2026-03-29T19:02:25.484Z"
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 2
  completed_plans: 2
---

# STATE — ESP32 MicroPython Dev Station

**Project:** ESP32 MicroPython Dev Station
**Initialized:** 2026-03-28
**Current Phase:** 5

---

## Project Reference

**Core Value:** Claude can flash, deploy, and debug any connected ESP32 without the user having to leave their editor or remember tooling commands.

**Architecture:** Python MCP server (FastMCP) running on a Linux host (Raspberry Pi or any ARM SBC/x86 machine); Streamable HTTP transport over LAN; subprocess wrappers for esptool (flashing), mpremote (deployment), and pyserial (REPL); per-device serial locking to prevent USB conflicts.

**Key Stack:**

- MCP Server: Python 3.10+ with FastMCP (mcp[cli] v1.26+)
- Flashing: esptool v5+ (command: `esptool`, not `esptool.py`)
- Deployment: mpremote (v1.23+)
- Serial I/O: pyserial (v3.5+)
- Process Management: systemd
- Transport: Streamable HTTP over LAN (`/mcp` endpoint)

**Constraints:**

- Linux with Python 3.10+ and systemd (Raspberry Pi, ARM SBCs, x86 thin clients, etc.)
- Trusted LAN only (no internet-facing security required)
- Mixed ESP32 variants (must auto-detect chip type)
- Single board operations at a time (serial lock enforces this)

---

## Current Position

Phase: 02 (core-usb-workflows) — EXECUTING
Plan: 3 of 3
**Milestone:** v1 (Core USB + MCP)
**Current Phase:** Planning (roadmap approval pending)
**Current Plan:** Not started
**Status:** Ready to plan

**Progress Bar:**

```
ROADMAP:    [████████████████████████████████] 100%
PHASE 1:    [                                  ]   0%
PHASE 2:    [                                  ]   0%
PHASE 3:    [                                  ]   0%
```

---

## Performance Metrics

| Metric | Target | Current | Notes |
|--------|--------|---------|-------|
| Phase 1 completion | ~7 days | — | Foundation: MCP + esptool + board detection |
| Flash success rate | >95% (post-Phase 1) | — | Depends on USB cable quality and chip detection |
| Deployment reliability | >90% (post-Phase 2) | — | File integrity + SPIFFS space checks critical |
| REPL response time | <5s per command (Phase 2) | — | Timeout framework needed for robustness |

---
| Phase 01-foundation-infrastructure P01 | 3 | 2 tasks | 14 files |
| Phase 02-core-usb-workflows P03 | 269 | 2 tasks | 4 files |
| Phase 03 P01 | 720 | 3 tasks | 4 files |
| Phase 03 P03 | 255 | 1 tasks | 1 files |
| Phase 03 P04 | 316 | 1 tasks | 1 files |
| Phase 04 P02 | 281 | 2 tasks | 7 files |

## Accumulated Context

### Key Decisions

1. **MCP server over REST API:** Allows Claude to call tools directly without user copying output; better DX for primary use case.

2. **Pi as deployment hub:** Centralizes USB connections and WiFi bridge; main machine stays clean.

3. **GitHub as code source:** User's existing workflow; Pi pulls latest from repo to deploy.

4. **Serial lock mechanism (per-device):** File-based mutex prevents concurrent USB access; queues operations at MCP layer.

5. **Subprocess isolation for external tools:** esptool, mpremote, and pyserial called as subprocesses; cleaner than in-process bindings.

6. **Streamable HTTP over stdio:** FastMCP's built-in `transport="streamable-http"` transport; no Flask/FastAPI wrapper needed; debuggable with curl. (SSE transport is deprecated in Claude Code as of 2025.)

7. **Never rely on esptool auto-detect:** Require explicit variant in config; use chip_id as validation step before flash, not source of truth.

8. **Firmware caching with TTL:** Cache firmware for 7 days; re-download if stale. Balances speed with freshness.

### High-Risk Areas (from Research)

1. **USB reliability & chip detection (Pitfalls 1-3):** Serial permissions, unstable disconnections, chip identification failures. Phase 1 must validate esptool chip detection on multiple variants.

2. **File deployment & SPIFFS constraints (Pitfalls 7-9):** Filesystem full, encoding issues, partial transfers. Phase 2 must include pre-flight checks and post-deployment verification.

3. **Concurrency & error propagation (Pitfalls 13-15):** Concurrent tool calls to same board, timeout handling, generic error messages. Phase 2 must implement per-device locking and structured error codes.

4. **REPL output buffering (Pitfalls 16-18):** Partial output, line ending confusion, blocking reads. Phase 3 must use markers around command/output and non-blocking serial.

5. **OTA reliability over WiFi (Pitfall 11):** WebREPL timeout during large transfer. Phase 3 can limit OTA to <200KB and fallback to USB.

### Blockers

None currently. Stack is well-charted. Research confidence is MEDIUM overall, degrading to MEDIUM-HIGH after Phase 1 validation.

### Todos

- [ ] Before Phase 1: Verify esptool + mpremote work as subprocess wrappers on target host
- [ ] Before Phase 1: Test FastMCP streamable-http transport with hello-world tool
- [ ] Before Phase 1: Validate systemd service scaffold on target host
- [ ] Phase 1: Flash a test board via MCP tool with correct chip detection
- [ ] Phase 1: Test with multiple ESP32 variants (classic, S3, C3)
- [ ] Phase 1: Health check `curl http://<host>:8000/mcp` from main machine

---

## Session Continuity

**Last Session:** 2026-03-29T19:02:25.444Z

- Analyzed 24 v1 requirements
- Derived 3-phase structure from research recommendations
- Validated 100% coverage (no orphans)
- Created ROADMAP.md with success criteria
- Created STATE.md (this file)
- Ready for Phase 1 planning

**Next Session:** Phase 1 planning

- Decompose Phase 1 goal into executable plans
- Identify must-haves vs. nice-to-haves
- Estimate effort per plan
- Create PLAN-01.md documents

---

**Last Updated:** 2026-03-28
