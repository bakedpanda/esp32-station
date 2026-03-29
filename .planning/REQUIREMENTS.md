# Requirements: ESP32 MicroPython Dev Station

**Defined:** 2026-03-28
**Core Value:** Claude can flash, deploy, and debug any connected ESP32 without the user having to leave their editor or remember tooling commands.

## v1 Requirements

### Board Management

- [x] **BOARD-01**: Claude can list all ESP32 boards currently connected via USB
- [x] **BOARD-02**: Claude can identify the chip variant of a connected board (ESP32, S2, S3, C3, C6)
- [ ] **BOARD-03**: Claude can reset a board (soft reset and hard reset)
- [x] **BOARD-04**: Board state is persisted across MCP server restarts

### Firmware Flashing

- [x] **FLASH-01**: Claude can flash MicroPython firmware onto a board via USB
- [x] **FLASH-02**: Correct firmware variant is selected automatically based on detected chip type
- [x] **FLASH-03**: Firmware images are cached locally; network not required at flash time
- [x] **FLASH-04**: Flash operation fails fast with a clear error if chip cannot be identified
- [x] **FLASH-05**: Pre-flight check verifies board is responsive before flashing begins

### Code Deployment

- [x] **DEPLOY-01**: Claude can deploy a single file to a board via USB serial
- [x] **DEPLOY-02**: Claude can deploy a full project directory to a board via USB serial
- [x] **DEPLOY-03**: Pre-deployment check verifies sufficient filesystem space (60–70% safe capacity)
- [x] **DEPLOY-04**: Deployment verifies file integrity after transfer
- [ ] **DEPLOY-05**: Claude can pull the latest code from a GitHub repo and deploy it to the board

### REPL & Serial Access

- [ ] **REPL-01**: Claude can execute a MicroPython command on a board and capture the output
- [ ] **REPL-02**: Claude can read recent serial output from a board
- [ ] **REPL-03**: REPL commands time out cleanly (no blocking hangs)

### MCP Server

- [x] **MCP-01**: MCP server runs as a persistent daemon on the host machine
- [x] **MCP-02**: MCP server is reachable from Claude on the main machine over LAN (Streamable HTTP)
- [x] **MCP-03**: MCP server starts automatically on host boot via systemd
- [ ] **MCP-04**: All board operations serialize per device (no concurrent USB access conflicts)
- [ ] **MCP-05**: All errors returned to Claude include a code and actionable description

### OTA (WiFi Updates)

- [ ] **OTA-01**: Claude can push a code update to a board over WiFi (WebREPL or equivalent)
- [ ] **OTA-02**: OTA falls back to USB if WiFi is unavailable

## v2 Requirements

### Monitoring

- **MON-01**: Claude can stream live serial output from a board
- **MON-02**: Claude can query board health (free memory, uptime, connected status)
- **MON-03**: Deployment history is tracked and queryable

### Advanced Automation

- **AUTO-01**: Incremental file sync (only changed files deployed)
- **AUTO-02**: Claude can deploy a specific git branch or commit (not just latest)
- **AUTO-03**: Automatic syntax validation before deployment

### Infrastructure

- **INFRA-01**: Disk space management (firmware cache limits, log rotation)
- **INFRA-02**: Structured JSON logging on Pi for debug inspection

## Out of Scope

| Feature | Reason |
|---------|--------|
| Web UI / dashboard | Claude is the interface; no browser UI needed |
| Multi-user auth / API tokens | Trusted LAN only; single user |
| Fleet inventory / multi-board tracking | Single board at a time for now |
| Non-MicroPython firmware (Arduino, ESP-IDF) | Out of stated scope |
| Docker containerization | venv + systemd simpler; no benefit at this scale |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BOARD-01 | Phase 1 | Complete |
| BOARD-02 | Phase 1 | Complete |
| BOARD-03 | Phase 2 | Pending |
| BOARD-04 | Phase 1 | Complete |
| FLASH-01 | Phase 1 | Complete |
| FLASH-02 | Phase 1 | Complete |
| FLASH-03 | Phase 1 | Complete |
| FLASH-04 | Phase 1 | Complete |
| FLASH-05 | Phase 1 | Complete |
| DEPLOY-01 | Phase 2 | Complete |
| DEPLOY-02 | Phase 2 | Complete |
| DEPLOY-03 | Phase 2 | Complete |
| DEPLOY-04 | Phase 2 | Complete |
| DEPLOY-05 | Phase 3 | Pending |
| REPL-01 | Phase 2 | Pending |
| REPL-02 | Phase 2 | Pending |
| REPL-03 | Phase 2 | Pending |
| MCP-01 | Phase 1 | Complete |
| MCP-02 | Phase 1 | Complete |
| MCP-03 | Phase 1 | Complete |
| MCP-04 | Phase 2 | Pending |
| MCP-05 | Phase 2 | Pending |
| OTA-01 | Phase 3 | Pending |
| OTA-02 | Phase 3 | Pending |

**Coverage:**
- v1 requirements: 24 total
- Mapped to phases: 24
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-28*
*Last updated: 2026-03-28 after initial definition*
