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

- [x] **Phase 4: Hardening** - Fix v1.0 tech debt and make resets reliable (completed 2026-03-30)
- [x] **Phase 5: Board Status** - Query board health, firmware, WiFi, and resource usage (completed 2026-03-29)
- [x] **Phase 6: Provisioning** - Always-erase flash, WiFi config deployment, clear user guidance (completed 2026-03-29)
- [x] **Phase 7: Setup & Onboarding** - One-command Pi setup script and MCP registration docs
- [ ] **Phase 8: End-to-End UAT** - Full manual validation on real hardware: all 15 MCP tools, provisioning workflow, and fresh Pi install via setup.sh

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
**Plans:** 2/2 plans complete
Plans:
- [x] 04-01-PLAN.md -- Fix tech debt: flaky test, stale service comment, missing Phase 3 tool assertions
- [x] 04-02-PLAN.md -- Reliability: DTR/RTS hardware reset, fallback message, --chip enforcement on all esptool calls

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
**Plans:** 2/2 plans complete
Plans:
- [x] 06-01-PLAN.md -- Credentials utility (load_credentials) and boot.py template with WiFi + WebREPL + hostname
- [x] 06-02-PLAN.md -- Wire deploy_boot_config MCP tool, update flash docstring for always-erase, add user_action guidance

### Phase 7: Setup & Onboarding
**Goal**: A new user can go from bare Pi to working dev station with one script and clear documentation
**Depends on**: Phase 6 (setup script installs everything provisioning needs, including WiFi credential file format)
**Requirements**: SETUP-01, SETUP-03
**Success Criteria** (what must be TRUE):
  1. Running setup.sh on a fresh Pi clones the repo, installs all dependencies, prompts for WiFi credentials, writes the credentials file, and installs+starts the systemd service
  2. README contains clear instructions for registering the MCP server URL in Claude Code on the main machine
**Plans:** 2/3 plans executed
Plans:
- [x] 07-01-PLAN.md -- Test scaffolds: test_setup_script.py (SETUP-01 content tests) and test_readme.py (SETUP-03 content tests)
- [x] 07-02-PLAN.md -- Write setup.sh: idempotent Pi onboarding script (SETUP-01)
- [x] 07-03-PLAN.md -- Update README.md: 15 tools table, 12 architecture modules, setup.sh reference, MCP registration (SETUP-03)

### Phase 8: End-to-End UAT
**Goal**: Every MCP tool is validated on real hardware; setup.sh is proven on a fresh Pi; the full provisioning workflow (erase → flash → WiFi → deploy) works end-to-end
**Depends on**: Phase 7 (setup.sh and README complete)
**Requirements**: SETUP-01, SETUP-03, all v1.1 requirements
**Success Criteria** (what must be TRUE):
  1. All 15 MCP tools exercised from Claude Code on the main machine via the live Pi server
  2. Full provisioning workflow confirmed: erase, flash firmware, deploy WiFi credentials, deploy boot.py, deploy code from GitHub
  3. setup.sh runs successfully on a fresh Pi (clean OS, nothing pre-installed) and leaves a working MCP server
  4. setup.sh re-run on an existing Pi is idempotent (no duplicate entries, no errors)
  5. MCP server registration (`claude mcp add --transport http`) works from main machine
**Plans:** 0 plans (manual UAT phase — plans created during /gsd:discuss-phase 8)

## Progress

**Execution Order:**
Phases execute in numeric order: 4 -> 5 -> 6 -> 7 -> 8

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation & Infrastructure | v1.0 | 4/4 | Complete | 2026-03-28 |
| 2. Core USB Workflows | v1.0 | 3/3 | Complete | 2026-03-29 |
| 3. WiFi & Advanced | v1.0 | 4/4 | Complete | 2026-03-29 |
| 4. Hardening | v1.1 | 2/2 | Complete | 2026-03-30 |
| 5. Board Status | v1.1 | 3/3 | Complete | 2026-03-29 |
| 6. Provisioning | v1.1 | 2/2 | Complete   | 2026-03-29 |
| 7. Setup & Onboarding | v1.1 | 3/3 | Complete | 2026-03-30 |
| 8. End-to-End UAT | v1.1 | 0/0 | Planned | - |

---

**Last Updated:** 2026-03-30 -- Phase 8 added (end-to-end UAT)

---

## Backlog

### Phase 999.1: Rename GitHub repo from ESP32-server to esp32-station (BACKLOG)

**Goal:** Standardize the project name — `esp32-station` is used 49 times across 15 files (service name, MCP name, paths, tests); `ESP32-server` appears only 5 times in GitHub clone URLs.
**Requirements:** TBD
**Plans:** 0 plans

**Approach:**
1. Copy (not move) `/mnt/anton/Claude/ESP32-server` → `/mnt/anton/Claude/esp32-station`
2. Copy Claude Code memory: `cp -r ~/.claude/projects/-mnt-anton-Claude-ESP32-server ~/.claude/projects/-mnt-anton-Claude-esp32-station`
3. Work from the new folder — old folder stays as backup
4. Rename GitHub repo (Settings → Rename to esp32-station)
5. Update the 5 clone URLs in README.md and setup.sh
6. Delete old folder once stable

Plans:
- [ ] TBD (promote with /gsd:review-backlog when ready)
