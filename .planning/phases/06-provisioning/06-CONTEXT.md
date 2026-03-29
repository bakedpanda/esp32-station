# Phase 6: Provisioning - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Claude can take a raw or used ESP32 from blank chip to WiFi-connected MicroPython board, with credentials managed securely on the Pi. Includes always-erase flash enforcement, WiFi credential management, boot.py deployment (WiFi + WebREPL + mDNS + hostname), and clear user guidance for physical actions. Tools remain separate and chainable -- Claude orchestrates based on user-chosen readiness level.

Out of scope: setup.sh script (Phase 7), MCP registration docs (Phase 7), fleet management.

</domain>

<decisions>
## Implementation Decisions

### Credential Storage
- **D-01:** JSON format -- `/etc/esp32-station/wifi.json` with `{"ssid": "...", "password": "...", "webrepl_password": "..."}`. File permissions 600, created by setup.sh (Phase 7) or manually by user.
- **D-02:** Single network vs multiple -- Claude's discretion. Start simple, can extend later.
- **D-03:** WebREPL password stored in the same credentials file alongside WiFi credentials. Single source of truth.
- **D-04:** Shared utility `tools/credentials.py` with `load_credentials()` -- returns dict or error dict. Follows existing `tools/` module pattern.
- **D-05:** Lazy validation -- credentials file checked only when a tool needs it, not at server startup. Non-provisioning tools work without it.
- **D-06:** When credentials file is missing, tool returns error dict with clear instructions: file path, expected JSON format, example content. No MCP tool writes credentials -- user handles it manually or via setup.sh. Credentials never pass through MCP tool calls (SETUP-02).

### boot.py Generation
- **D-07:** Template with placeholder injection -- `templates/boot.py.tpl` in the repo with `{{SSID}}`, `{{PASSWORD}}`, `{{WEBREPL_PASSWORD}}`, `{{HOSTNAME}}` placeholders. Deploy tool reads credentials from wifi.json, fills placeholders, writes to temp file, deploys via mpremote.
- **D-08:** boot.py configures four things: WiFi auto-connect, WebREPL start, mDNS advertisement (`_webrepl._tcp`), and hostname setting.
- **D-09:** Hostname -- Claude prompts the user for a hostname if one isn't specified in the MicroPython code being deployed. Enables meaningful mDNS identification (e.g. `esp32-kitchen`).
- **D-10:** Dedicated MCP tool `deploy_boot_config(port, hostname=None)` -- reads credentials, fills template, deploys as boot.py. Self-contained, one step in provisioning chain.
- **D-11:** Overwrite silently -- provisioning implies starting fresh (board was just erased and flashed). No confirmation needed for replacing boot.py.

### User Guidance Style
- **D-12:** Physical action instructions delivered via `user_action` key in tool return dict. e.g. `{"user_action": "Hold BOOT button, then press EN to enter flash mode", "reason": "ESP32 needs manual bootloader entry for flashing"}`. Claude reads and relays naturally.
- **D-13:** Proactive guidance -- tool returns `user_action` BEFORE the step that needs physical intervention. Claude tells user, waits for confirmation, then proceeds. Two-step process for actions requiring physical interaction.
- **D-14:** First-timer friendly detail level -- full explanation of what button, where it is, what happens, when to release. Claude can condense for repeat users based on conversation context.

### Provisioning Flow
- **D-15:** Five readiness levels, Claude orchestrates by chaining separate tools:
  1. **Flash only** -- erase + flash MicroPython. USB development ready, no WiFi.
  2. **Flash + WiFi config** -- flash + deploy boot.py. Network-connected on boot.
  3. **Full provisioning (WiFi)** -- flash + WiFi config + deploy project code. Fully operational.
  4. **WiFi config only** -- deploy boot.py to already-flashed board. For boards needing WiFi setup.
  5. **Full provisioning (USB only)** -- flash + deploy project code, no WiFi/boot.py. For battery-powered or USB-only projects.
- **D-16:** Claude asks whether WiFi should be disabled to save battery for projects that don't need it. Important for battery-powered sensor/control setups.
- **D-17:** No readiness-level tool -- Claude knows the levels from tool descriptions and chains accordingly. Tools stay separate (PROV-04).
- **D-18:** Auto-verify after provisioning -- Claude always calls `check_board_health()` and/or `get_board_status()` to confirm the board is alive (and WiFi-connected if applicable). Closes the loop without user asking.

### Always-Erase (PROV-01)
- **D-19:** Already satisfied by existing `flash_firmware()` which always calls `erase_flash` in step 4 with no skip option. Implementation: update tool description to explicitly state "always performs full erase" and add a test verifying the erase subprocess call is present.

### Patterns (carried from prior phases)
- **D-20:** Error dict pattern: `{"error": "snake_case_code", "detail": "human string"}` -- never raise.
- **D-21:** Tool modules in `tools/`, thin `@mcp.tool()` wrappers in `mcp_server.py`.
- **D-22:** Separate `port`/`host` parameters for USB/WiFi tools.

### Claude's Discretion
- Single vs multiple network support in credentials file (start simple)
- boot.py template exact MicroPython code (WiFi connect, WebREPL init, mDNS setup)
- Exact `user_action` message wording for each physical step
- How to condense guidance for experienced users in follow-up interactions
- mDNS service name and TXT record content in boot.py

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` -- PROV-01, PROV-02, PROV-03, PROV-04, SETUP-02

### Existing Implementation (patterns to follow)
- `tools/firmware_flash.py` -- flash_firmware() with always-erase pattern; PROV-01 reference implementation
- `tools/file_deploy.py` -- deploy_file() for mpremote file deployment; boot.py deployment will use similar pattern
- `tools/board_status.py` -- get_board_status(), check_board_health() for post-provisioning verification
- `tools/mdns_discovery.py` -- discover_boards() expects `_webrepl._tcp` mDNS service; boot.py must advertise this
- `tools/ota_wifi.py` -- WebREPL subprocess pattern; reference for WiFi-side operations
- `tools/serial_lock.py` -- SerialLock for USB operations
- `mcp_server.py` -- @mcp.tool() registration pattern, currently 14 tools

### Prior Phase Context
- `.planning/phases/05-board-status/05-CONTEXT.md` -- D-10 says Phase 6 automates board-side mDNS via boot.py; D-08 specifies `_webrepl._tcp` service type
- `.planning/phases/02-core-usb-workflows/02-CONTEXT.md` -- error dict pattern, deployment patterns
- `.planning/phases/03-wifi-advanced/03-CONTEXT.md` -- WebREPL transport, WiFi addressing

### Project Context
- `.planning/PROJECT.md` -- core value, constraints, known issues (soft reset unreliable, explicit --chip)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/firmware_flash.py:flash_firmware()` -- already implements erase + flash flow; PROV-01 satisfied here
- `tools/file_deploy.py:deploy_file()` -- mpremote cp pattern for deploying files to board; boot.py deployment can reuse
- `tools/board_status.py` -- post-provisioning verification tools (health check, status query)
- `tools/mdns_discovery.py` -- Pi-side mDNS browser expecting `_webrepl._tcp`; boot.py must match

### Established Patterns
- Error returns: `{"error": "snake_case_code", "detail": "human string"}` -- never raise
- subprocess: `subprocess.run([...], capture_output=True, text=True, timeout=N)`
- Tool modules in `tools/`, thin wrappers in `mcp_server.py`
- WiFi tools take `host` parameter; USB tools take `port` parameter

### Integration Points
- `mcp_server.py` -- add `deploy_boot_config` as new `@mcp.tool()` (15th tool)
- `tools/credentials.py` -- new shared module for credential loading
- `templates/boot.py.tpl` -- new template file for boot.py generation
- `requirements.txt` -- no new dependencies expected (JSON stdlib, mpremote already present)

</code_context>

<specifics>
## Specific Ideas

- Hostname prompted by Claude if not in the code being deployed -- makes mDNS identification meaningful
- Claude asks about WiFi/battery tradeoff for USB-only projects -- important for battery-powered sensor setups
- Auto-verification after provisioning closes the loop -- user gets confirmation without asking
- Credentials error includes exact file path, format, and example JSON -- user can create the file immediately

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope.

</deferred>

---

*Phase: 06-provisioning*
*Context gathered: 2026-03-29*
