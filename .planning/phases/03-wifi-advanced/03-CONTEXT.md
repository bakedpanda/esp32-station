# Phase 3: WiFi & Advanced - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning

<domain>
## Phase Boundary

Enable OTA code updates to ESP32 boards over WiFi (WebREPL), with Claude-driven fallback to USB when WiFi is unavailable. Also enable single-call GitHub deployment: Pi pulls latest code from a GitHub repo via git, then deploys to a board via USB.

Out of scope: board provisioning over WiFi, WebREPL setup/configuration, mDNS discovery, streaming serial over WiFi.

</domain>

<decisions>
## Implementation Decisions

### OTA Transport
- **D-01:** Use WebREPL as the OTA mechanism — MicroPython's built-in WebSocket file transfer. Requires `webrepl_cli.py` script on the Pi and `webrepl_cfg.py` on the board (pre-configured by user).
- **D-02:** Hard limit of 200KB per OTA transfer. Fail fast with `{"error": "ota_payload_too_large", "detail": "..."}` if payload exceeds this.
- **D-03:** WebREPL password passed as a per-call parameter — never stored on Pi. No credential persistence.
- **D-04:** OTA success response matches deploy_file pattern: `{"port": ..., "files_written": [...], "transport": "wifi"}` — consistent with existing USB deploy tools.

### Board WiFi Addressing
- **D-05:** Board's WiFi address (IP or hostname) is provided by the caller as a `host` parameter per-call. No auto-discovery, no persistence in board state.

### OTA Fallback
- **D-06:** Two separate tools — `deploy_ota_wifi()` and the existing `deploy_file_to_board()`. No automatic fallback inside the OTA tool. Claude decides when to call which.
- **D-07:** When the board is unreachable over WiFi, `deploy_ota_wifi()` returns `{"error": "wifi_unreachable", "detail": "...", "fallback": "use deploy_file_to_board"}` — the `fallback` hint tells Claude exactly what to do next.
- **D-08:** WiFi unreachability is detected by connection timeout only — no ICMP ping pre-check. Attempt WebREPL connect; return `wifi_unreachable` if it doesn't complete within the timeout.

### GitHub Integration
- **D-09:** Pi pulls from GitHub using `git` subprocess (`git clone` or `git pull` in a temp/work directory). Follows existing subprocess pattern from Phase 1/2.
- **D-10:** Optional `token` parameter for private repos — passed via URL embedding (`https://token@github.com/...`). Token is never stored by the tool.
- **D-11:** `repo_url` and `branch` (default `main`) provided per-call. No stored per-board repo config.
- **D-12:** After pulling, deploy to board via USB using existing `deploy_directory()` — not via WiFi. GitHub tool is a USB-deploy wrapper with a git pull prefix.

### Patterns (carried from Phase 2)
- **D-13:** Error dict pattern: `{"error": "snake_case_code", "detail": "human string"}` — never raise exceptions to callers (D-02 from Phase 2).
- **D-14:** New tools follow thin `@mcp.tool()` wrapper in `mcp_server.py` + module in `tools/`.

### Claude's Discretion
- Exact WebREPL timeout value for `wifi_unreachable` detection
- Temp directory location for GitHub clones on Pi
- `git clone` vs `git pull` logic (first-time vs subsequent runs)
- Whether to clean up temp dir after deploy or keep as cache

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Implementation (Phase 2 patterns to follow)
- `tools/file_deploy.py` — deploy_file() / deploy_directory() patterns, space check, integrity check, error dict shape
- `mcp_server.py` — @mcp.tool() registration pattern, SerialLock usage
- `tools/serial_lock.py` — SerialLock context manager (wrap USB operations)

### Requirements
- `.planning/REQUIREMENTS.md` — DEPLOY-05, OTA-01, OTA-02 (the three Phase 3 requirements)

### Project Context
- `.planning/PROJECT.md` — core value, constraints, out-of-scope items
- `.planning/STATE.md` — accumulated decisions, known pitfalls (esp. "OTA reliability over WiFi — Pitfall 11")

No external specs — requirements fully captured in decisions above.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tools/file_deploy.py` — `deploy_directory()`: directly callable after GitHub pull; handles exclusions, space check, integrity verification
- `tools/serial_lock.py` — `SerialLock`: wrap USB deploy calls in GitHub tool the same way Phase 2 tools do
- `mcp_server.py` — error dict and `@mcp.tool()` pattern for the two new tools

### Established Patterns
- subprocess: `subprocess.run([...], capture_output=True, text=True, timeout=N)` — use for both git and webrepl_cli
- Error returns: `{"error": "snake_case_code", "detail": "human string"}` — never raise
- Tool modules in `tools/`, registered in `mcp_server.py`

### Integration Points
- `mcp_server.py` — add `deploy_ota_wifi()` and `pull_and_deploy_github()` as `@mcp.tool()` decorators
- `tools/file_deploy.py` — `deploy_directory()` is the deploy step inside `pull_and_deploy_github()`

</code_context>

<specifics>
## Specific Ideas

- The `fallback` hint in the `wifi_unreachable` error dict is important — it lets Claude know to call `deploy_file_to_board()` without needing to infer it from context.
- `webrepl_cli.py` is a Python script distributed with MicroPython tools — the Pi needs it available (pip installable or bundled).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-wifi-advanced*
*Context gathered: 2026-03-29*
