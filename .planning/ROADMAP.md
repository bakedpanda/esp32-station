# ROADMAP -- ESP32 MicroPython Dev Station

**Project:** ESP32 MicroPython Dev Station (MCP server on Linux host)
**Created:** 2026-03-28

---

## Milestones

- ✅ **v1.0 MVP** -- Phases 1-3 (shipped 2026-03-29)
- 🚧 **v1.1 Provisioning & Onboarding** -- Phases 4-7 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-3) -- SHIPPED 2026-03-29</summary>

- [x] Phase 1: Foundation & Infrastructure (4/4 plans) -- completed 2026-03-28
- [x] Phase 2: Core USB Workflows (3/3 plans) -- completed 2026-03-29
- [x] Phase 3: WiFi & Advanced (4/4 plans) -- completed 2026-03-29

</details>

### 🚧 v1.1 Provisioning & Onboarding (In Progress)

**Milestone Goal:** Seamless path from raw/used ESP32 to running code, reliable resets, one-command Pi setup, and v1.0 tech debt cleanup.

- [ ] **Phase 4: Hardening** - Fix v1.0 tech debt and make resets reliable
- [ ] **Phase 5: Board Status** - Query board health, firmware, WiFi, and resource usage
- [ ] **Phase 6: Provisioning** - Always-erase flash, WiFi config deployment, clear user guidance
- [ ] **Phase 7: Setup & Onboarding** - One-command Pi setup script and MCP registration docs

## Phase Details

### Phase 4: Hardening
**Goal**: Existing tools are reliable and the codebase is clean -- hard reset works, esptool never auto-detects, tests pass correctly
**Depends on**: Phase 3 (v1.0 complete)
**Requirements**: DEBT-01, DEBT-02, DEBT-03, REL-01, REL-02, REL-03
**Success Criteria** (what must be TRUE):
  1. Post-deploy reset uses DTR/RTS hardware signal and the board restarts without user intervention
  2. When hardware reset fails, user receives a clear prompt to unplug and replug the board
  3. Every esptool subprocess call passes an explicit --chip flag (no auto-detect anywhere in codebase)
  4. All existing tests pass, including the fixed test_detect_chip_success and Phase 3 tool assertions
  5. The systemd service file has no stale planning comments
**Plans:** 2 plans
Plans:
- [x] 04-01-PLAN.md -- Fix tech debt: flaky test, stale service comment, missing Phase 3 tool assertions
- [ ] 04-02-PLAN.md -- Reliability: DTR/RTS hardware reset, fallback message, --chip enforcement on all esptool calls

### Phase 5: Board Status
**Goal**: Claude can check whether a board is alive, what firmware it runs, and its resource state -- without the user running REPL commands manually
**Depends on**: Phase 4 (reliable resets needed for consistent board queries)
**Requirements**: STAT-01, STAT-02, STAT-03
**Success Criteria** (what must be TRUE):
  1. MCP tool returns firmware version, WiFi connection status, IP address, free memory, and free storage for a connected board
  2. MCP tool detects whether MicroPython is running and the board is responsive, reporting clear issues if not
  3. MCP tool discovers MicroPython boards on the local network via mDNS and returns their IP addresses
**Plans:** 3 plans
Plans:
- [x] 05-01-PLAN.md -- Board status collection and health check with dual USB/WiFi transport
- [x] 05-02-PLAN.md -- mDNS discovery of MicroPython boards via python-zeroconf
- [x] 05-03-PLAN.md -- Wire 3 new tools into MCP server and update registration tests

### Phase 6: Provisioning
**Goal**: Claude can take a raw or used ESP32 from blank chip to WiFi-connected MicroPython board, with credentials managed securely on the Pi
**Depends on**: Phase 4 (reliable resets, explicit --chip), Phase 5 (board status to verify provisioning success)
**Requirements**: PROV-01, PROV-02, PROV-03, PROV-04, SETUP-02
**Success Criteria** (what must be TRUE):
  1. Every firmware flash automatically performs a full erase before writing -- no partial flash states possible
  2. WiFi credentials are stored in a Pi-local file and never appear in MCP tool calls or logs
  3. Claude can deploy a boot.py with WiFi, WebREPL, and mDNS advertisement config to a board, reading credentials from the Pi-local file
  4. Every step requiring physical user action (BOOT button, power cycle) includes an explanation of what to do and why
  5. Tools remain separate and chainable -- Claude asks the user what readiness level they want and chains accordingly
**Plans**: TBD

### Phase 7: Setup & Onboarding
**Goal**: A new user can go from bare Pi to working dev station with one script and clear documentation
**Depends on**: Phase 6 (setup script installs everything provisioning needs, including WiFi credential file format)
**Requirements**: SETUP-01, SETUP-03
**Success Criteria** (what must be TRUE):
  1. Running setup.sh on a fresh Pi clones the repo, installs all dependencies, prompts for WiFi credentials, writes the credentials file, and installs+starts the systemd service
  2. README contains clear instructions for registering the MCP server URL in Claude Code on the main machine
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 4 -> 5 -> 6 -> 7

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & Infrastructure | v1.0 | 4/4 | Complete | 2026-03-28 |
| 2. Core USB Workflows | v1.0 | 3/3 | Complete | 2026-03-29 |
| 3. WiFi & Advanced | v1.0 | 4/4 | Complete | 2026-03-29 |
| 4. Hardening | v1.1 | 1/2 | In Progress | - |
| 5. Board Status | v1.1 | 0/3 | Planned | - |
| 6. Provisioning | v1.1 | 0/? | Not started | - |
| 7. Setup & Onboarding | v1.1 | 0/? | Not started | - |

---

**Last Updated:** 2026-03-29 -- Phase 5 planned (3 plans)
