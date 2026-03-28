# ESP32 MicroPython Dev Station

## What This Is

A Raspberry Pi-based development server for managing ESP32 boards running MicroPython. It handles full provisioning (flashing firmware + deploying code) via USB and OTA updates over WiFi, with serial/REPL access to connected boards. Claude on the main machine can drive the whole thing through an MCP server.

## Core Value

Claude can flash, deploy, and debug any connected ESP32 without the user having to leave their editor or remember tooling commands.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Flash MicroPython firmware onto ESP32 boards via USB (supports mixed variants: classic, S2/S3, C3/C6)
- [ ] Deploy MicroPython project files to ESP32 via USB serial
- [ ] Deploy MicroPython project files to ESP32 via OTA over WiFi
- [ ] Read serial output and run REPL commands on connected ESP32 boards
- [ ] Expose all capabilities as an MCP server accessible to Claude on the main machine over LAN
- [ ] Pull project code from GitHub for deployment

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

## Constraints

- **Platform**: Raspberry Pi (Linux/ARM) — Pi-compatible tooling only
- **Connectivity**: LAN only — no internet-facing exposure required
- **Boards**: Mixed ESP32 variants — must auto-detect chip type for correct firmware selection
- **Protocol**: MCP server for Claude integration (preferred over REST API for direct tool use)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| MCP server over REST API | Allows Claude to call tools directly without user copying output; better DX for the primary use case | — Pending |
| Pi as deployment hub | Centralizes USB connections and WiFi bridge; main machine stays clean | — Pending |
| GitHub as code source | User's existing workflow; Pi pulls latest from repo to deploy | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-28 after initialization*
