# Phase 8: End-to-End UAT Checklist

**Goal:** Validate every MCP tool, the full provisioning workflow, and setup.sh on real hardware.

Mark each item `[x]` as you go. Note failures with the actual error.

---

## Section A: Fresh Pi Install (setup.sh)

> Run on a clean Pi — nothing pre-installed beyond OS and git.

- [x] **A1** — Run `bash setup.sh` (or pipe from curl); script completes without errors
- [x] **A2** — Step 1: git and python3-venv pre-flight checks pass
- [x] **A3** — Step 2: Repo cloned to `~/esp32-station`
- [x] **A4** — Step 3: Virtualenv created, `requirements.txt` installed
- [x] **A5** — Step 4: User added to `dialout` group (check `groups`)
- [x] **A6** — Step 5/6: WiFi credentials prompted, written to `/etc/esp32-station/wifi.json`
- [x] **A7** — Step 7: systemd service installed (`cat /etc/systemd/system/esp32-station.service` — shows correct user/path, no planning comments)
- [x] **A8** — Step 8: Service starts and is active (`systemctl is-active esp32-station`)
- [x] **A9** — Step 9: Endpoint URL and `claude mcp add` command printed correctly

**Notes:**

---

## Section B: Idempotency Re-Run

> Re-run setup.sh on the same Pi without a clean OS.

- [x] **B1** — `bash setup.sh` completes without errors on second run
- [x] **B2** — No duplicate dialout group entries
- [x] **B3** — Credentials not re-prompted (file already exists, skipped)
- [x] **B4** — Service not double-installed or left in broken state
- [x] **B5** — `git pull` runs instead of re-clone

**Notes:**

---

## Section C: MCP Server Registration

> From your main machine (where Claude Code runs).

- [x] **C1** — Run the `claude mcp add --transport http` command printed by setup.sh
- [x] **C2** — `claude mcp list` shows `esp32-station` server
- [x] **C3** — Open Claude Code — 15 tools visible in tool list

**Notes:**

---

## Section D: Board Discovery & Identification

> Connect an ESP32 via USB.

- [x] **D1** — `list_connected_boards` — returns board with correct port (e.g. `/dev/ttyUSB0`)
- [x] **D2** — `identify_chip` — returns chip type (esp32, esp32s3, esp32c3, etc.) with explicit `--chip` in subprocess call (no auto-detect)
- [x] **D3** — `get_board_state` — returns list of connected boards with their ports

**Notes:**

---

## Section E: Flash & Provisioning Workflow

> Full path: erase → flash → WiFi config → boot.py deploy

- [x] **E1** — `flash_micropython` — erases board first (always-erase behaviour), downloads firmware, flashes successfully; BOOT button hold required — user guidance displayed
- [x] **E2** — After flash: board boots MicroPython (confirm with `exec_repl_command` → `import sys; sys.version`)
- [x] **E3** — `deploy_boot_config` — deploys boot.py with WiFi + WebREPL + mDNS; reads credentials from Pi-local file (no creds in tool call)
- [x] **E4** — Board connects to WiFi after power cycle (check router or `discover_boards`)
- [x] **E5** — `discover_boards` — finds the newly provisioned board on LAN

**Notes:** Functional. Bootloader entry process varies by board — XIAO ESP32-S3 requires hold-BOOT-while-plugging-in rather than hold-BOOT+press-RESET. Need more board variants to fully validate E1 guidance. `save_board_flash_notes` exists for recording per-chip processes.

**Notes:**

---

## Section F: File Deployment (USB)

> With board connected via USB and MicroPython running.

- [x] **F1** — `deploy_file_to_board` — deploys a single `.py` file; file present on board after deploy
- [x] **F2** — `deploy_directory_to_board` — deploys a directory; all files present on board
- [x] **F3** — `pull_and_deploy_github` — clones/pulls a GitHub repo and deploys to board

**Notes:**

---

## Section G: REPL & Serial

- [x] **G1** — `exec_repl_command` — runs a Python expression, returns output (e.g. `1+1` → `2`)
- [x] **G2** — `exec_repl_command` — handles a command that produces no output (no hang)
- [x] **G3** — `read_board_serial` — returns buffered serial output from board
- [x] **G4** — `reset_board` (soft) — board resets, code restarts
- [x] **G5** — `reset_board` (hard) — DTR/RTS hardware reset triggers; board restarts without user intervention
- [x] **G6** — `reset_board` (hard) failure path — if hardware reset fails, user receives clear prompt to unplug/replug

**Notes:**
- G1: `mpremote exec` uses raw REPL — expressions don't auto-print; `print(1+1)` → `2` as expected. UAT wording updated mentally: pass with `print()` wrapper.
- G3: Fixed post-UAT. Original `mpremote exec ""` approach interrupted the board and never captured anything. Replaced with direct pyserial read (no raw REPL entry). Now captures live output from autonomously running boards correctly. Note: `exec_repl_command` sends Ctrl+C which kills timers — that is expected mpremote behaviour, not a G3 issue.
- G5: Parameter is `reset_type` (not `method`) — returns `{"reset": "hard"}` correctly.

---

## Section H: Board Status & Health

- [x] **H1** — `get_board_status` (USB) — returns firmware version, WiFi status, IP, free memory, free storage
- [x] **H2** — `get_board_status` (WiFi/host) — same fields via WebREPL connection
- [x] **H3** — `check_board_health` — detects MicroPython running, board responsive; reports clear error when board unresponsive

**Notes:**

---

## Section I: OTA WiFi Deploy

> Board must be on WiFi with WebREPL enabled (from Section E).

- [x] **I1** — `deploy_ota_wifi` — deploys a file to board over WiFi; file present after deploy

**Notes:**

---

## Section J: Error Handling Spot-Checks

- [x] **J1** — `flash_micropython` with wrong port — returns structured error, not crash
- [x] **J2** — `exec_repl_command` on unresponsive board — times out cleanly within timeout param
- [x] **J3** — `deploy_boot_config` with no credentials file — returns clear error about missing `/etc/esp32-station/wifi.json`
- [x] **J4** — Two tool calls to same board in quick succession — second call queues or returns a clear "board busy" message (serial lock)

**Notes:**
- J1: Returns `{"error":"erase_failed","chip":"ESP32-S3","port":"/dev/ttyUSB9","detail":"...","saved_flash_notes":"...","user_action":"..."}` — fully structured. Note: chip name is case-sensitive (`ESP32-S3` not `esp32s3`).
- J2: Board unplugged → `{"error":"repl_failed","detail":"mpremote: failed to access /dev/ttyACM0 (it may be in use by another program)"}` — fails fast with clear error rather than hanging to timeout. Better than expected.
- J3: Returns `{"error":"credentials_not_found","detail":"...with full create instructions"}` — exact path, complete fix instructions.
- J4: SerialLock **queues** the second call — both succeed, second waits ~3s for the lock. No "board busy" rejection; queuing is the correct behavior per spec.

---

## Summary

| Section | Items | Pass | Fail | Skip |
|---------|-------|------|------|------|
| A: Fresh Pi Install | 9 | 9 | | |
| B: Idempotency | 5 | 5 | | |
| C: MCP Registration | 3 | 3 | | |
| D: Discovery & ID | 3 | 3 | | |
| E: Flash & Provisioning | 5 | 5 | | |
| F: File Deployment | 3 | 3 | | |
| G: REPL & Serial | 6 | 6 | | |
| H: Board Status | 3 | 3 | | |
| I: OTA WiFi | 1 | 1 | | |
| J: Error Handling | 4 | 4 | | |
| **Total** | **42** | **42** | | |

**UAT Result:** PASS

**Sign-off date:**

**Hardware tested:**
- Pi model:
- ESP32 variant(s):
- MicroPython version:
