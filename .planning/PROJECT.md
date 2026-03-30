# ESP32 MicroPython Dev Station

## What This Is

A Raspberry Pi-based development server for managing ESP32 boards running MicroPython. It handles full provisioning (flashing firmware + deploying code) via USB and OTA updates over WiFi, with serial/REPL access to connected boards. Claude on the main machine drives the whole thing through an MCP server with 11 tools.

## Core Value

Claude can flash, deploy, and debug any connected ESP32 without the user having to leave their editor or remember tooling commands.

## Current Milestone: v1.1 Provisioning & Onboarding

**Goal:** Seamless path from raw/used ESP32 to running code, reliable resets, one-command Pi setup for new users, and v1.0 tech debt cleanup.

**Target features:**
- One-command Pi setup script (setup.sh)
- WiFi credentials on Pi, read locally by MCP server
- Hard reset (DTR/RTS) with power-cycle fallback
- Always-erase provisioning
- WiFi config deployment to boards
- Clear user guidance for manual steps
- Batch-friendly separate tools
- Tech debt cleanup from v1.0 audit

## Current State

v1.1 milestone complete — all 7 phases done. 15 MCP tools, 12 tool modules, full provisioning workflow, and one-command Pi onboarding.
Phase 7 complete — setup.sh at repo root takes a fresh Pi from zero to running dev station (clone, virtualenv, pip deps, dialout group, WiFi credential prompt, credentials file, service install+start). README updated with all 15 tools, 12 architecture modules, and MCP registration instructions.
Tech stack: FastMCP, esptool, mpremote, pyserial, webrepl_cli.py, zeroconf, git subprocess.
Deployed on Raspberry Pi at 192.168.10.123 as systemd service.

## Requirements

### Validated (v1.0)

- Flash MicroPython firmware onto ESP32 boards via USB (5 variants) — v1.0
- Expose all capabilities as MCP server over LAN — v1.0
- Deploy files/directories to ESP32 via USB serial — v1.0
- Read serial output and run REPL commands — v1.0
- Per-port serial locking for concurrent safety — v1.0
- Deploy files to ESP32 via OTA WiFi (WebREPL) — v1.0
- Pull project code from GitHub and deploy — v1.0

### Active

- [x] One-command Pi setup script (clone, deps, WiFi credential prompts, systemd install) — Validated in Phase 7: Setup & Onboarding
- [x] WiFi credentials stored on Pi, read locally by MCP server — Validated in Phase 6: Provisioning
- [x] Hard reset (DTR/RTS) as default post-deploy, with power-cycle fallback prompt — Validated in Phase 4: Hardening
- [x] Always full-erase before flash — Validated in Phase 6: Provisioning
- [x] WiFi config deployment to boards (boot.py with credentials from Pi-local file) — Validated in Phase 6: Provisioning
- [x] Clear user guidance for all manual steps (BOOT button, power cycle, credentials) — Validated in Phase 6: Provisioning
- [x] Batch board prep — Claude chains tools at user-chosen readiness level — Validated in Phase 6: Provisioning
- [x] Tech debt: fix test_detect_chip_success, stale service comment, Phase 3 test assertions, enforce explicit --chip — Validated in Phase 4: Hardening
- [x] Query board firmware version, WiFi status, IP, free memory/storage via MCP tool — Validated in Phase 5: Board Status
- [x] Detect whether MicroPython is running and board is responsive — Validated in Phase 5: Board Status
- [x] Discover MicroPython boards on LAN via mDNS — Validated in Phase 5: Board Status

### Out of Scope

- Fleet management / multi-board inventory — single board at a time for now
- Web UI — Claude is the interface, no dashboard needed
- Authentication/security hardening — trusted LAN only
- Non-MicroPython firmware (Arduino, ESP-IDF, Zephyr, etc.)

## Context

- **Hardware**: Raspberry Pi on the same LAN as the main dev machine; ESP32 boards connected via USB serial
- **Firmware source**: MicroPython official releases (esptool for flashing)
- **Code source**: Main machine → GitHub → Pi → ESP32; Pi pulls from GitHub to deploy
- **User**: Tinkering and experimenting with mixed ESP32 variants, sensor/control projects
- **Claude access**: MCP server is the primary interface — Claude should be able to do everything without copy-pasting output
- **Known issues**: Soft reset unreliable on ESP32 classic; esptool auto-detect should enforce explicit --chip

## Constraints

- **Platform**: Raspberry Pi (Linux/ARM) — Pi-compatible tooling only
- **Connectivity**: LAN only — no internet-facing exposure required
- **Boards**: Mixed ESP32 variants — must auto-detect chip type for correct firmware selection
- **Protocol**: MCP server for Claude integration (preferred over REST API for direct tool use)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MCP server over REST API | Allows Claude to call tools directly without user copying output | ✓ Implemented — streamable-http on port 8000 |
| Pi as deployment hub | Centralizes USB connections and WiFi bridge; main machine stays clean | ✓ Implemented — systemd daemon, auto-start on boot |
| GitHub as code source | User's existing workflow; Pi pulls latest from repo to deploy | ✓ Implemented — pull_and_deploy_github MCP tool |
| host/port on FastMCP() not run() | FastMCP.run() does not accept host/port in mcp>=1.26 | ✓ Applied in Phase 01 |
| Subprocess isolation | esptool, mpremote, git, webrepl_cli as subprocesses not in-process | ✓ Cleaner error handling, no import conflicts |
| Error dicts not exceptions | All tools return {error, detail} dicts; never raise to MCP layer | ✓ Consistent structured errors for Claude |
| Auto soft-reset after deploy | Board runs new code immediately after file/dir/GitHub deploy | ✓ Replaced with DTR/RTS hard reset in Phase 4 |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-30 after Phase 7: Setup & Onboarding completion — v1.1 milestone complete*
