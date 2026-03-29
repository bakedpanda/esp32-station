# Requirements: ESP32 MicroPython Dev Station

**Defined:** 2026-03-29
**Core Value:** Claude can flash, deploy, and debug any connected ESP32 without the user having to leave their editor or remember tooling commands.

## v1.1 Requirements

Requirements for the Provisioning & Onboarding milestone.

### Setup & Onboarding

- [ ] **SETUP-01**: New user can run a single `setup.sh` script that clones the repo, installs dependencies, prompts for WiFi credentials, writes the credentials file, and installs+starts the systemd service
- [ ] **SETUP-02**: WiFi credentials are stored on the Pi and read locally by the MCP server -- never transmitted through MCP tool calls
- [ ] **SETUP-03**: README includes clear instructions for registering the MCP server URL in Claude Code on the main machine

### Provisioning

- [ ] **PROV-01**: Every firmware flash starts with a full erase (no firmware detection needed)
- [ ] **PROV-02**: User can deploy WiFi + WebREPL config (boot.py) to a board, with credentials read from the Pi-local file
- [ ] **PROV-03**: Every step requiring user action (BOOT button hold, erase progress, power cycle) includes a clear explanation of what to do and why
- [ ] **PROV-04**: Tools remain separate so Claude can chain them; for batch prep Claude asks the user what readiness level they want per board

### Reliability

- [ ] **REL-01**: Post-deploy reset uses DTR/RTS hardware reset by default instead of soft reset
- [ ] **REL-02**: If hardware reset fails, user is prompted to unplug/replug with clear instructions
- [ ] **REL-03**: All esptool calls use explicit `--chip` flag, never auto-detect

### Board Status

- [ ] **STAT-01**: MCP tool returns board status: firmware version, WiFi connected (y/n), IP address, free memory/storage
- [ ] **STAT-02**: Board health check detects whether MicroPython is running, board is responsive, and reports any issues
- [ ] **STAT-03**: MCP tool discovers MicroPython boards on the local network via mDNS and returns their IP addresses

### Tech Debt

- [x] **DEBT-01**: Fix `test_detect_chip_success` for read-only filesystem (patch BOARDS_JSON in test)
- [x] **DEBT-02**: Remove stale planning comment from `esp32-station.service` line 1
- [x] **DEBT-03**: Add Phase 3 tool assertions to `test_new_tools_registered`

## Future Requirements

Deferred to later milestones.

- **FLEET-01**: Multi-board inventory and fleet management
- **SEC-01**: Authentication/security hardening for non-LAN deployments

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Web UI / dashboard | Claude is the interface -- status comes via MCP tool |
| Non-MicroPython firmware | Arduino, ESP-IDF, Zephyr out of scope |
| Internet-facing security | Trusted LAN only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SETUP-01 | Phase 7 | Pending |
| SETUP-02 | Phase 6 | Pending |
| SETUP-03 | Phase 7 | Pending |
| PROV-01 | Phase 6 | Pending |
| PROV-02 | Phase 6 | Pending |
| PROV-03 | Phase 6 | Pending |
| PROV-04 | Phase 6 | Pending |
| REL-01 | Phase 4 | Pending |
| REL-02 | Phase 4 | Pending |
| REL-03 | Phase 4 | Pending |
| STAT-01 | Phase 5 | Pending |
| STAT-02 | Phase 5 | Pending |
| STAT-03 | Phase 5 | Pending |
| DEBT-01 | Phase 4 | Complete |
| DEBT-02 | Phase 4 | Complete |
| DEBT-03 | Phase 4 | Complete |

**Coverage:**
- v1.1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-03-29*
*Last updated: 2026-03-29 after roadmap creation*
