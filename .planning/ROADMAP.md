# ROADMAP — ESP32 MicroPython Dev Station

**Project:** ESP32 MicroPython Dev Station (MCP server on Linux host)
**Created:** 2026-03-28
**Granularity:** Coarse (3-5 phases)
**Coverage:** 24/24 v1 requirements mapped

---

## Phases

- [ ] **Phase 1: Foundation & Infrastructure** - MCP server skeleton + board detection + firmware flashing via USB
- [ ] **Phase 2: Core USB Workflows** - File deployment + REPL access + error handling
- [ ] **Phase 3: WiFi & Advanced** - OTA updates + GitHub integration

---

## Phase Details

### Phase 1: Foundation & Infrastructure

**Goal:** Prove core USB communication works; MCP server + esptool integration established; Claude can flash firmware and detect board types.

**Depends on:** Nothing (first phase)

**Requirements:** BOARD-01, BOARD-02, BOARD-04, FLASH-01, FLASH-02, FLASH-03, FLASH-04, FLASH-05, MCP-01, MCP-02, MCP-03

**Success Criteria** (what must be TRUE):
1. Claude can list all ESP32 boards currently connected via USB and identify each board's chip variant (ESP32, S2, S3, C3, C6)
2. Claude can flash MicroPython firmware onto a connected board via USB, with the correct firmware automatically selected based on chip type
3. MCP server is running as a persistent daemon on the host machine and reachable from Claude on the main machine over LAN (Streamable HTTP)
4. Firmware images are cached locally on the host; MCP server continues to function if network is down during flashing
5. Flash operations fail fast with clear error messages if the chip cannot be identified or the board is unresponsive

**Plans:** 4 plans

Plans:
- [x] 01-01-PLAN.md — Project scaffold: skeleton files, requirements.txt, pytest test stubs
- [x] 01-02-PLAN.md — Board detection: USB enumeration, chip identification, state persistence
- [x] 01-03-PLAN.md — Firmware flash: firmware cache (7-day TTL), esptool erase+write_flash
- [x] 01-04-PLAN.md — MCP server wiring: 4 registered tools, systemd service, LAN verification

---

### Phase 2: Core USB Workflows

**Goal:** Complete flash+deploy+REPL pipeline; handle file system constraints; robust error handling at every step.

**Depends on:** Phase 1

**Requirements:** DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04, REPL-01, REPL-02, REPL-03, MCP-04, MCP-05

**Success Criteria** (what must be TRUE):
1. Claude can deploy a single file or a full project directory to a board via USB serial, and the deployment completes successfully without file corruption
2. Pre-deployment checks verify sufficient filesystem space (safe capacity at 60-70%); deployments fail gracefully if insufficient space with actionable error messages
3. Claude can execute MicroPython commands on a board and capture the output without timeouts or hanging; REPL commands complete cleanly within specified time limits
4. Claude can read recent serial output from a board and can reset a board (soft and hard reset) via USB without requiring manual intervention
5. All MCP server errors include a unique code and actionable description; operations on the same board serialize correctly with no USB access conflicts

**Plans:** 1/3 plans executed

Plans:
- [ ] 02-01-PLAN.md — File deployment: deploy_file/deploy_directory via mpremote, space check, integrity verify
- [x] 02-02-PLAN.md — REPL + board reset: exec_repl, read_serial, soft_reset, hard_reset via mpremote
- [ ] 02-03-PLAN.md — MCP wiring + serialization: SerialLock per-port, 5 new tools registered, error code audit

---

### Phase 3: WiFi & Advanced

**Goal:** Enable code updates over WiFi and automated deployment from GitHub repositories.

**Depends on:** Phase 2

**Requirements:** DEPLOY-05, OTA-01, OTA-02

**Success Criteria** (what must be TRUE):
1. Claude can push a code update to a board over WiFi (via WebREPL or equivalent) without requiring USB connection
2. OTA updates fall back to USB automatically if WiFi is unavailable or times out
3. Claude can pull the latest code from a GitHub repository and deploy it to a board with a single MCP tool call

**Plans:** TBD

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Infrastructure | 0/4 | Planned | - |
| 2. Core USB Workflows | 1/3 | In Progress|  |
| 3. WiFi & Advanced | 0/3 | Not started | - |

---

**Last Updated:** 2026-03-29 — Phase 2 plans created (3 plans)
