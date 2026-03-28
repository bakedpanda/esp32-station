# Domain Pitfalls: ESP32 MicroPython Dev Station

**Domain:** ESP32 MicroPython tooling on Raspberry Pi with MCP server integration
**Researched:** 2026-03-28
**Scope:** Hardware detection, flashing, file deployment, OTA updates, MCP server concurrency, Pi infrastructure

---

## Hardware & USB Connectivity

### Pitfall 1: Serial Port Permission Denied (`/dev/ttyUSB*`)

**What goes wrong:**
- `esptool` or `rshell` fails with "Permission denied" when accessing `/dev/ttyUSB0` or `/dev/ttyACM*`
- Issue appears randomly after Pi reboot or when unplugging/replugging boards
- Same tooling works as one user but not another (e.g., `root` works, service user fails)

**Why it happens:**
- Linux udev rules not installed or not reloaded after plugin
- Serial port device owned by `root:dialout`, service running as unprivileged user
- udev rules for USB VID/PID don't match the ESP32 variant being used
- systemd service running without `dialout` group membership

**Consequences:**
- Automation completely fails even when hardware is physically present
- Flashing pipeline stalls on first step with no clear error message
- Intermittent failures after reboots make debugging difficult

**Prevention:**
- **At Pi setup time:** Install udev rules that grant non-root access to ESP32 USB devices:
  ```bash
  # Add to /etc/udev/rules.d/99-esp32.rules
  SUBSYSTEMS=="usb", ATTRS{idVendor}=="1a86", ATTRS{idProduct}=="7523", MODE="0666"
  SUBSYSTEMS=="usb", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", MODE="0666"
  SUBSYSTEMS=="usb", ATTRS{idVendor}=="239a", ATTRS{idProduct}=="004d", MODE="0666"
  # Reload: udevadm control --reload-rules && udevadm trigger
  ```
- **For systemd service:** Add service user to `dialout` group: `usermod -a -G dialout serviceuser`
- **Before each deployment:** Verify device exists: `ls -la /dev/ttyUSB* /dev/ttyACM*` before calling tools
- **Test early:** Flash a test board as the service user in isolation to catch permission issues in development, not production

**Detection:**
- Log check: `"Permission denied"` in esptool or rshell output
- Symptom: Works from CLI as root, fails as service user
- `strace` shows `open(/dev/ttyUSB0)` returning EACCES

**Phase:** Phase 1 (Infrastructure setup) — must be solved before any flashing works

---

### Pitfall 2: Unstable USB Connection / Disconnection During Transfer

**What goes wrong:**
- Board disconnects mid-flash or mid-file-transfer, leaving it in bootloader or corrupted state
- More likely with longer cables, powered hubs, or under-powered USB ports on Pi
- Appears as sudden EOF in serial communication, partial writes to SPIFFS

**Why it happens:**
- Cheap USB cables or hubs don't maintain proper voltage under load
- Raspberry Pi has limited USB power budget (max ~500mA per port without powered hub)
- No retry logic in flashing pipeline — single disconnection = full abort
- esptool/ampy have no automatic reconnection

**Consequences:**
- Bricked boards requiring manual reflash via UART programmer
- Partial filesystem writes corrupt the SPIFFS partition
- User loses trust in automated deployment

**Prevention:**
- **Hardware:** Use short, high-quality USB cables; add powered USB hub if running multiple boards
- **Monitoring:** Detect disconnection in real-time — check device node exists before every read/write
- **Graceful abort:** If device disappears, immediately fail with clear message rather than timeout
- **Retry at higher level:** File deployment, not flash protocol itself (flashing is all-or-nothing)
- **Testing:** Test with intentional cable unplugs during transfers in development

**Detection:**
- Unexpected EOF from serial port
- Device node `/dev/ttyUSB*` disappears mid-operation
- esptool/rshell timeout errors, not permission errors

**Phase:** Phase 2 (Flashing pipeline) — implement detection and graceful error reporting

---

### Pitfall 3: esptool Chip Detection / Chip ID Mismatches

**What goes wrong:**
- esptool auto-detects ESP32 variant wrong (classic vs S2 vs S3 vs C3 vs C6)
- Flashing proceeds with wrong firmware, resulting in non-functional board
- Variant detection fails entirely with "Unable to read chip ID"

**Why it happens:**
- Different ESP32 variants report different chip IDs via UART, but esptool can misinterpret under noise
- USB-UART bridges (CH340, CP2102) have varying quality — some don't properly pull reset/GPIO0 signals
- DTR/RTS handshake not working correctly, leaving board in wrong mode for chip detection
- Firmware URLs are variant-specific; wrong variant = wrong binary pulled

**Consequences:**
- Silent failure — board appears to flash successfully but doesn't run properly
- Requires manual intervention to recover (determine correct variant, reflash)
- Undermines user confidence in automation

**Prevention:**
- **Explicit variant specification:** Never rely on auto-detection. Require or strongly hint at variant in config.
  ```yaml
  esp32_config:
    chip_type: "esp32s3"  # explicit, not auto-detected
    firmware_url: "https://micropython.org/download/esp32-generic-s3/..."
  ```
- **Validation before flash:** Read chip ID, compare against config, abort if mismatch
- **Multiple attempts with reset:** If chip detection fails, try cycling reset/GPIO0 pins and retry
- **Firmware registry:** Maintain local mapping of chip type → correct firmware binary URL
- **Test with all variants:** In development, test flashing logic with at least one board of each supported variant

**Detection:**
- Log chip ID detection step and the detected variant vs. configured variant
- Post-flash validation: Try to query a unique identifier from MicroPython after flash (e.g., machine.ChipID())
- Symptoms: Board responsive but code doesn't run as expected

**Phase:** Phase 1 (Infrastructure) — must detect and prevent before Phase 2 (Flashing)

---

## Flashing & Firmware Management

### Pitfall 4: Firmware Download Failures / Wrong Firmware URL Format

**What goes wrong:**
- MicroPython firmware download from internet fails (network outage, wrong URL, renamed release)
- Script tries to download firmware, gets HTTP 404 or invalid binary
- No cached firmware available, so deployment is completely blocked

**Why it happens:**
- MicroPython release URLs change between versions
- Different chip variants have different firmware binaries with specific naming conventions
- Release archives are reorganized on server (rarely, but happens)
- Network connectivity on Pi is intermittent or blocked by ISP

**Consequences:**
- Deployment stalls waiting for download
- User has to manually download and cache firmware
- Affects the "no user intervention" design goal

**Prevention:**
- **Firmware registry:** Maintain a local, versioned list of known good firmware URLs:
  ```python
  FIRMWARE_CATALOG = {
    "esp32-generic": "https://micropython.org/resources/...-idf4.4.x.bin",
    "esp32-generic-s3": "https://micropython.org/resources/...-s3.bin",
    # ...
  }
  ```
- **Caching:** Download once, cache locally on Pi; skip re-download if binary already exists and matches checksum
- **Fallback URLs:** Store backup download sources in case primary is unavailable
- **Checksum validation:** Verify downloaded binary against known-good SHA256 before flashing
- **Graceful degradation:** If download fails, check cache; if cache exists, use it (with warning)

**Detection:**
- HTTP error code from download attempt
- Binary size mismatch or invalid magic bytes (MicroPython binaries start with specific header)
- SHA256 checksum mismatch

**Phase:** Phase 2 (Flashing) — implement with Phase 1 infrastructure decision

---

### Pitfall 5: Partial Flashing / Resume Logic

**What goes wrong:**
- Flash operation interrupted mid-way (network timeout, user ctrl-c, board disconnected)
- Board left in inconsistent state — partially written firmware
- Attempting to resume/retry makes it worse or leaves board bootloader-only

**Why it happens:**
- esptool writes firmware in chunks; if one chunk fails, board bootloader may be corrupted
- No transactional semantics — can't "undo" partial write
- User may retry immediately before board stabilizes

**Consequences:**
- Board requires UART programmer or manual reflash via voltage manipulation
- User loses confidence in automation

**Prevention:**
- **All-or-nothing:** Accept that flashing cannot be resumed safely — if interrupted, user must manual-restore
- **Pre-flight checks:** Before flashing, verify board is responsive and chip is detected correctly
- **No retry loop:** Don't auto-retry flashing; fail with clear instruction to user
- **Backup firmware:** Keep previous known-good firmware cached; offer "rollback to last working version" as recovery option
- **Timeout strategy:** Set adequate timeout in esptool (e.g., 30s) to catch hang before user gets impatient

**Detection:**
- Flashing operation timeout or sudden disconnection
- Post-flash validation fails (board doesn't respond to REPL ping)

**Phase:** Phase 2 (Flashing) — design error handling and validation

---

### Pitfall 6: Multiple Flash Attempts in Quick Succession

**What goes wrong:**
- User/automation triggers two flash operations on the same board within seconds
- Both attempt to reset the board and send firmware simultaneously
- Collision results in corrupted state or hang

**Why it happens:**
- No locking mechanism prevents concurrent access to board
- systemd timer or MCP call could trigger flash while previous operation still in progress
- User nervously clicks "flash again" because first attempt seemed slow

**Consequences:**
- Board needs manual recovery
- Undermines reliability promises

**Prevention:**
- **Global lock per device:** Before any board operation, acquire exclusive lock on that `/dev/ttyUSB*` device
  ```python
  with FileLock(f"/var/run/esp32_{serial_port}.lock"):
      # flash operation here
  ```
- **Timeout on lock:** If lock can't be acquired in N seconds, report board in use and fail gracefully
- **Explicit device tracking:** Keep state file of currently-active operations per device
- **MCP server enforce:** Validate in MCP tool handlers that device is not already locked

**Detection:**
- Multiple processes trying to open `/dev/ttyUSB*`
- Unusual error patterns from esptool (e.g., "chip id mismatch" after successful reset)

**Phase:** Phase 3 (MCP server) — must enforce at server level, not tool level

---

## File Deployment & Filesystem Management

### Pitfall 7: SPIFFS / LittleFS Filesystem Full or Corrupted

**What goes wrong:**
- Attempting to upload project files fails with "filesystem full" even though space appears available
- Previously uploaded files become corrupted and won't load
- Board responds to REPL but file operations fail silently

**Why it happens:**
- MicroPython firmware reserves blocks for wear leveling; user thinks 4MB filesystem is fully usable, but only 2.5MB safe
- Multiple tool attempts to write same file leave orphaned blocks
- Power loss or sudden disconnection during file write leaves SPIFFS metadata inconsistent
- Large files uploaded in small chunks; if connection drops mid-write, partial file blocks filesystem

**Consequences:**
- Deployment fails even though code is ready
- User must manually erase filesystem (`import os; os.remove()`) or reflash entirely
- Project files mysteriously disappear or become corrupted

**Prevention:**
- **Filesystem planning:** Calculate safe available space (usually 60-70% of total) and enforce limit
  ```python
  SAFE_FILESYSTEM_USAGE = 0.6  # 60% of total
  available = statvfs()[4] * statvfs()[2]  # Free blocks * block size
  safe_available = total_size * SAFE_FILESYSTEM_USAGE
  ```
- **Pre-deployment check:** Query board filesystem before upload:
  ```python
  import os
  stat = os.statvfs('/flash')
  free_bytes = stat[2] * stat[3]  # blocks * block size
  ```
- **Atomic writes:** Use temporary filenames during upload, rename on completion
  ```python
  # Upload as main_py.tmp, rename to main.py only after successful transfer
  ```
- **Filesystem format on reflash:** Always include step to format SPIFFS when flashing new firmware
- **Incremental uploads:** Split large files into chunks with checksums; verify each chunk before next
- **Recovery plan:** Document manual recovery: "If filesystem corrupted, reflash firmware with erase flag"

**Detection:**
- File upload fails with "ENOSPC" or similar
- `os.listdir()` returns fewer files than expected
- Board runs but file operations timeout

**Phase:** Phase 2 (File Deployment) — implement pre-flight checks before any upload

---

### Pitfall 8: Tool Incompatibility: esptool vs ampy vs mpremote vs rshell

**What goes wrong:**
- User uploads file with `rshell` but then tries to use `mpremote` to manage it
- Version mismatch between tools causes protocol errors
- Different tools have different behavior for same operation (e.g., "put" semantics differ)
- One tool works, another fails on identical operation

**Why it happens:**
- MicroPython ecosystem has multiple competing tools, each with own implementation
- `ampy` is legacy but still widely used
- `mpremote` is newer but has bugs in older MicroPython versions
- `rshell` is most robust but has different command syntax
- Each tool implements WebREPL/serial protocol slightly differently

**Consequences:**
- Automation brittle if tool changes
- Different tools have different failure modes — hard to debug
- Recovery involves manual investigation of which tool works

**Prevention:**
- **Pick one tool for automation:** Use `rshell` exclusively (most reliable, best error messages) or `mpremote` (official, if newer MicroPython)
  - For this project: recommend `rshell` for file operations, `mpremote` only if Python 3.11+
- **Version pin:** Specify exact tool version in Pi setup (e.g., `rshell==0.0.30`)
- **Capability matrix:** Document which operations use which tool
  ```
  Flashing: esptool
  File upload: rshell
  REPL: mpremote or picocom
  ```
- **Isolation:** Don't mix tools on same board in same session
- **Testing:** Test chosen tool combination with all MicroPython versions supported

**Detection:**
- Protocol error or timeout when using different tool than expected
- File appears uploaded but can't be imported

**Phase:** Phase 1 (Tooling decision) — decide on single tool for file deployment early

---

### Pitfall 9: Encoding Issues in File Upload (UTF-8, Line Endings)

**What goes wrong:**
- File uploads successfully but contains wrong line endings on board (CRLF becomes LF or vice versa)
- Non-ASCII characters in comments or strings get mangled
- Python code fails to parse due to encoding declaration mismatch

**Why it happens:**
- Serial protocol can transform line endings (Windows-style CRLF ↔ Unix LF)
- USB-UART bridge may not preserve byte-for-byte fidelity
- Tools like rshell try to be "helpful" and normalize line endings
- User edits file on Windows (CRLF), uploads to Pi/Linux environment

**Consequences:**
- Code doesn't parse: `SyntaxError: inconsistent use of tabs and spaces`
- Unicode strings display incorrectly
- Impossible to debug without inspecting binary on board

**Prevention:**
- **Binary upload mode:** Use tools' binary flag (`rshell -c "put main.py"` or `mpremote put main.py`)
  - Ensure tool is NOT doing line-ending conversion
- **Enforce UTF-8:** Use UTF-8 encoding exclusively; no conversions
- **Pre-upload validation:** Read file locally, verify it's valid Python and valid UTF-8 before sending
- **Post-upload verification:** Download file back and compare checksums
- **Line ending normalization:** Normalize all project files to LF (Unix style) before upload
  ```bash
  dos2unix *.py  # or: sed -i 's/\r$//' *.py
  ```

**Detection:**
- File uploads but code fails with `SyntaxError` when imported
- `os.path.getsize()` on board doesn't match expected size
- `xxd` / `od` comparison shows different bytes than uploaded

**Phase:** Phase 2 (File Deployment) — implement validation pipeline

---

## OTA Updates & WiFi Connectivity

### Pitfall 10: WebREPL Password Not Set / Default Credentials Bypassed

**What goes wrong:**
- WebREPL enabled but password not set (defaults to empty or "micropython")
- OTA script connects to WebREPL without password validation
- Anyone on network can access board's REPL and filesystem

**Why it happens:**
- First-time MicroPython flash doesn't set WebREPL password
- OTA script hardcodes default password
- User manually enables WebREPL via REPL but forgets password setup step

**Consequences:**
- Security risk on shared network (not critical for LAN-only, but bad hygiene)
- If password not enforced in automation, hard to audit who changed what

**Prevention:**
- **Mandatory password:** On first flashing, generate strong random password, store in config, require it for all WebREPL access
- **Validation in automation:** Before any WebREPL operation, verify password is non-default
  ```python
  if not config.get("webrepl_password"):
      raise ValueError("WebREPL password not configured")
  ```
- **Documentation:** Mark WebREPL password as critical infrastructure component, same as SSH key
- **Per-board tracking:** Log which board has which password in Pi config, verify on connect

**Detection:**
- WebREPL accepts connection without password
- Default password successfully connects

**Phase:** Phase 3 (OTA updates) — enforce before first WebREPL use

---

### Pitfall 11: WebREPL Timeout / Connection Drops During Large File Transfer

**What goes wrong:**
- OTA update starts transferring large file (>500KB) over WebREPL
- Midway through, WiFi momentarily drops or TCP connection times out
- Board left in partial state (new code half-written, old code partially overwritten)

**Why it happens:**
- WebREPL is not designed for large file transfers (it's intended for interactive REPL, not bulk data)
- No framing or chunking — one dropped packet = corrupted write
- WiFi dropout on 2.4GHz (especially in dense networks) is common
- No application-layer ACK for file chunks
- TCP timeout defaults may be too aggressive

**Consequences:**
- Board fails to boot (corrupted boot.py)
- Project code in undefined state
- Requires USB re-flash to recover

**Prevention:**
- **File size limits:** Document max safe OTA file size; chunk larger transfers manually
  - For WebREPL: limit single update to <200KB
  - Larger projects: break into multiple files or use USB deployment instead
- **Resumable transfers:** If supported by tool, enable checkpoint/resume capability
- **Stability check before OTA:** Verify WiFi signal strength and board responsiveness before initiating OTA
  ```python
  rssi = network_status()
  if rssi < -70:  # poor signal
      raise ValueError("WiFi signal too weak for OTA")
  ```
- **Checksum validation:** After each chunk, compute checksum on board, compare with sender
- **Timeout tuning:** Set adequate timeout for transfer (longer for large files)
- **Watchdog reset:** Use board watchdog to force reboot if transfer stalls for too long
- **Fallback to USB:** If OTA fails, gracefully suggest USB deployment as alternative

**Detection:**
- WebREPL connection timeout mid-transfer
- File size mismatch on board after transfer
- Board becomes unresponsive (watchdog triggered)

**Phase:** Phase 3 (OTA updates) — plan for partial failure and recovery

---

### Pitfall 12: WiFi Configuration Lost After Firmware Flash

**What goes wrong:**
- Flash new MicroPython firmware to update code
- Board loses WiFi credentials (SSID, PSK, static IP)
- Board is now offline and unreachable; USB re-connection required to reconfigure WiFi

**Why it happens:**
- Firmware flash with "erase_flash" erases all SPIFFS including saved WiFi config
- User doesn't realize flashing wipes filesystem
- Recovery requires connecting USB again (defeats OTA purpose)

**Consequences:**
- OTA updates are one-way — can't deploy new code to board after initial flash without USB
- Board becomes inaccessible for period of time
- User has to manually reconfigure WiFi each time firmware updates

**Prevention:**
- **Never erase SPIFFS during normal firmware updates:** Only erase during initial flash/recovery
  ```bash
  esptool.py write_flash --erase-all  # only in recovery mode
  esptool.py write_flash 0x1000 firmware.bin  # normal update, preserves SPIFFS
  ```
- **Separate configuration storage:** Store WiFi config in NVRAM/NVS (partition that survives flash) if available
- **Configuration recovery:** Document step to reconfigure WiFi, provide simple REPL snippet
  ```python
  # Save WiFi config to NVRAM after successful connect
  import json, nvs
  nvs.save_wifi_config({"ssid": "...", "psk": "..."})
  ```
- **Validation:** After flash, verify board is still WiFi-connected before declaring success
- **Pre-flash backup:** Optional: download existing WiFi config before flashing, offer to restore after

**Detection:**
- Board disappears from network after firmware flash
- REPL shows WiFi not connected after flash

**Phase:** Phase 2 (Flashing) — implement with firmware update logic

---

## MCP Server & Concurrency

### Pitfall 13: Concurrent MCP Tool Calls to Same Board

**What goes wrong:**
- Claude/user calls two MCP tools on same board simultaneously:
  - Tool A: "get REPL output"
  - Tool B: "run Python command"
- Both try to acquire serial port simultaneously
- Output gets interleaved, commands collide, board state becomes inconsistent

**Why it happens:**
- MCP server runs multiple threads/coroutines
- No locking mechanism prevents concurrent access to `/dev/ttyUSB*`
- Tools naively open serial port without checking if already held
- Error handling doesn't gracefully reject second call

**Consequences:**
- Garbled output from REPL
- Commands don't execute as expected
- Board enters undefined state
- User loses confidence in automation

**Prevention:**
- **Per-board lock:** Create exclusive lock per USB device before any operation
  ```python
  async def with_board_lock(board_id, timeout=10):
      lock = locks.get(board_id)
      acquired = await asyncio.wait_for(lock.acquire(), timeout=timeout)
      if not acquired:
          raise ValueError(f"Board {board_id} already in use")
      try:
          yield
      finally:
          lock.release()
  ```
- **Queue operations:** If operation arrives while board locked, queue it (don't reject immediately)
- **Tool documentation:** In MCP schema, document which tools are mutually exclusive
- **Timeout handling:** If lock held for >30s, log warning and consider timeout
- **Testing:** Spawn two concurrent threads calling different tools on same board; verify no collision

**Detection:**
- Log entry: "Attempting to acquire lock on /dev/ttyUSB0, already held"
- Garbled REPL output containing interleaved commands and responses
- Board state inconsistent with commands sent

**Phase:** Phase 3 (MCP server) — implement locking before any REPL tools

---

### Pitfall 14: MCP Tool Timeout / Hanging Operations

**What goes wrong:**
- MCP tool call (e.g., "list files") times out, blocking Claude
- Board is unresponsive (WiFi disconnected, stuck in loop), but tool doesn't detect it
- Tool waits indefinitely for response that never comes
- Claude gets stuck, timeout occurs at MCP protocol level

**Why it happens:**
- Serial REPL has no connection timeout — waits forever if board doesn't respond
- WiFi board may have intermittent connectivity
- Board code stuck in infinite loop or blocking I/O
- Tool doesn't distinguish between "slow board" and "dead board"

**Consequences:**
- MCP server appears hung
- Claude times out, user thinks automation is broken
- Resource leak if connections not cleaned up properly

**Prevention:**
- **Set serial timeout:** Configure serial port with short timeout (e.g., 2s) to catch unresponsive boards
  ```python
  ser = serial.Serial(port, timeout=2)  # read times out after 2s
  ```
- **Explicit timeout per operation:** Wrap all board operations in timeout handler
  ```python
  async def run_repl_command(cmd, timeout=5):
      try:
          result = await asyncio.wait_for(send_and_wait(cmd), timeout=timeout)
          return result
      except asyncio.TimeoutError:
          raise ValueError(f"Board unresponsive (command: {cmd})")
  ```
- **Health check:** Before main operation, send simple REPL ping (e.g., `print("ok")`) to verify board is alive
- **Progressive timeouts:** Start with short timeout (2s), increase for known slow operations
- **Resource cleanup:** Ensure serial connections are closed even if timeout occurs
  ```python
  finally:
      ser.close()  # always close
  ```

**Detection:**
- REPL ping times out
- Serial read returns empty string after timeout
- MCP protocol-level timeout at 30s default

**Phase:** Phase 3 (MCP server) — implement in tool layer

---

### Pitfall 15: MCP Error Handling & Error Message Propagation

**What goes wrong:**
- Tool fails (e.g., flashing error), but returns generic "Error" to Claude
- Claude can't determine root cause (permission issue? board disconnected? firmware invalid?)
- User left guessing what went wrong, can't self-recover

**Why it happens:**
- Tools catch broad exceptions and re-wrap them generically
- Stack traces suppressed to keep MCP protocol clean
- No structured error codes — only free-form strings
- Python exception details lost in transit

**Consequences:**
- Poor debugging experience
- User doesn't know whether to retry, check hardware, or ask for help
- Undermines trust in automation

**Prevention:**
- **Structured error responses:** Define error codes for common failure modes
  ```python
  class ToolError(Exception):
      code: str  # "board_not_found", "permission_denied", "timeout", etc.
      message: str
      details: dict  # additional context
  ```
- **Specific exception handling:** Catch known exceptions separately and translate to codes
  ```python
  try:
      ser = serial.Serial(port)
  except PermissionError:
      raise ToolError(code="permission_denied",
                      message=f"Cannot access {port}",
                      details={"port": port, "user": getuser()})
  except FileNotFoundError:
      raise ToolError(code="board_not_found", ...)
  ```
- **Actionable messages:** Include suggestion for recovery
  ```
  "Board not found at /dev/ttyUSB0. Try: ls /dev/ttyUSB*"
  ```
- **Logging:** Log full exception + stack trace on Pi for debugging, send only structured error to Claude
- **Testing:** Test error paths explicitly (simulate permission error, disconnection, timeout)

**Detection:**
- User sees generic error and can't proceed
- Tool failure log on Pi has details, but MCP response doesn't expose them

**Phase:** Phase 3 (MCP server) — design error handling schema before implementation

---

## Serial REPL Streaming

### Pitfall 16: REPL Output Buffering & Incomplete Reads

**What goes wrong:**
- Send command to REPL, expect output
- Get partial output or no output, even though board executed command
- Next read picks up previously buffered output, causing timing issues

**Why it happens:**
- USB-UART bridge buffers data; data arrives in chunks, not line-by-line
- REPL doesn't flush output after command execution
- Tool reads exactly N bytes, but output is longer, so truncates
- Board echoes input (REPL convention), confusing output detection

**Consequences:**
- Output parsing fails (incomplete lines)
- Tool thinks command failed when it succeeded
- State inconsistency (command ran, tool thinks it didn't)

**Prevention:**
- **Use MicroPython markers:** Add unique markers around command/output to delimit cleanly
  ```python
  # Send: print("\x04MARKER_START\x04"); cmd; print("\x04MARKER_END\x04")
  # Look for markers in output
  ```
- **Read until timeout:** Read all available data until no data arrives for N ms (serial timeout)
  ```python
  output = ""
  while True:
      chunk = ser.read(1024)
      if not chunk:
          break  # timeout, no more data
      output += chunk.decode('utf-8')
  ```
- **Echo suppression:** Disable UART echo in MicroPython to avoid confusion
  ```python
  import esp
  esp.osdebug(None)  # disable OS debug output
  ```
- **Flush before read:** Send explicit flush command before reading (e.g., `sys.stdout.flush()`)

**Detection:**
- Output ends mid-line or is missing
- Next command's output contains fragments of previous command
- Garbled/corrupted output with partial Unicode sequences

**Phase:** Phase 3 (REPL streaming) — implement robust read loop

---

### Pitfall 17: Line Ending Confusion (LF vs CRLF in REPL)

**What goes wrong:**
- Send command with Unix line ending (LF), board expects Windows style (CRLF)
- Command doesn't execute, waits for more input
- Or vice versa: board sends CRLF, tool expects LF, output parsing fails

**Why it happens:**
- UART defaults vary by tool and platform
- MicroPython REPL raw mode vs normal mode have different line ending requirements
- USB-UART bridges may transform line endings
- Platform differences (Pi/Linux = LF, Windows = CRLF)

**Consequences:**
- Commands hang waiting for proper line ending
- Output parsing fails to detect line boundaries
- Tool appears unresponsive

**Prevention:**
- **Normalize to LF:** Standardize on Unix line endings (LF, `\n`) throughout
  ```python
  command = cmd.rstrip() + "\n"  # always Unix-style
  ser.write(command.encode('utf-8'))
  ```
- **Raw REPL mode:** Use MicroPython's raw REPL mode (starts with `Ctrl-A`) which handles line endings consistently
- **Test with both:** Verify command execution with LF and CRLF in development
- **Documentation:** Document expected line ending in REPL tool interface

**Detection:**
- REPL waits for input (prints `>>>`/`...`) after command sent
- Output garbled at line boundaries

**Phase:** Phase 3 (REPL streaming) — standardize in REPL tool

---

### Pitfall 18: Blocking Reads in REPL Loop

**What goes wrong:**
- Tool sends command to REPL, calls `ser.read()` without timeout
- Board is unresponsive or board output is incomplete
- Tool blocks indefinitely, freezing entire MCP server
- All other operations stall

**Why it happens:**
- Naive serial read with no timeout parameter
- Assumption that board will always respond within time
- No non-blocking I/O — thread/coroutine blocks waiting for data

**Consequences:**
- MCP server hangs
- All other clients/tools waiting for response
- User can't cancel operation, must restart server

**Prevention:**
- **Always set timeout:** Configure serial port with timeout on open
  ```python
  ser = serial.Serial(port, timeout=2)
  ```
- **Use select/non-blocking:** Use `select()` on Unix to avoid blocking forever
  ```python
  import select
  rlist, _, _ = select.select([ser], [], [], timeout=2)
  if rlist:
      data = ser.read(1024)
  else:
      raise TimeoutError()
  ```
- **Async/await:** In MCP server, use async wrappers to prevent thread blocking
  ```python
  async def read_with_timeout(ser, timeout=2):
      # Run blocking read in thread executor with timeout
      loop = asyncio.get_event_loop()
      return await asyncio.wait_for(
          loop.run_in_executor(None, lambda: ser.read(1024)),
          timeout=timeout
      )
  ```
- **Thread isolation:** Run serial I/O in dedicated thread, signal main via event
- **Testing:** Simulate board unresponsiveness (physically disconnect), verify tool times out cleanly

**Detection:**
- MCP server stops responding to other requests
- Process becomes hard to kill (stuck in blocking syscall)
- Serial read call never returns

**Phase:** Phase 3 (REPL streaming) — implement async wrappers

---

## Raspberry Pi Infrastructure

### Pitfall 19: systemd Service Fails Silently / Doesn't Start on Boot

**What goes wrong:**
- Pi reboots, MCP server service is configured but doesn't start
- User assumes server is running, Claude tries to use it, connection refused
- Service crashed but no notification sent

**Why it happens:**
- systemd unit file syntax error (not validated until service starts)
- Service depends on resource that's not available at startup (network not ready, etc.)
- Working directory doesn't exist
- Environment variables not set
- File permissions prevent service user from accessing files

**Consequences:**
- Entire automation unavailable after reboot
- User doesn't realize until trying to use it
- Difficult to debug remotely

**Prevention:**
- **Validate systemd unit before deploying:** Run `systemd-analyze` and `journalctl` checks
  ```bash
  sudo systemd-analyze verify /etc/systemd/system/esp32-mcp.service
  sudo systemctl start esp32-mcp && sleep 2 && systemctl status esp32-mcp
  ```
- **Explicit dependencies:** Document what service depends on, use `After=` and `Requires=`
  ```ini
  [Unit]
  After=network-online.target
  Wants=network-online.target
  ```
- **User/Group setup:** Ensure service user exists, has dialout group membership
  ```bash
  useradd -G dialout esp32-server
  ```
- **Working directory validation:** Verify directory exists and is readable by service user
  ```bash
  mkdir -p /opt/esp32-server
  chown esp32-server:esp32-server /opt/esp32-server
  chmod 750 /opt/esp32-server
  ```
- **Startup test:** Include "verify service is running" step in deployment script
  ```bash
  sleep 3 && systemctl is-active esp32-mcp || (journalctl -u esp32-mcp -n 20 && exit 1)
  ```
- **Health check endpoint:** MCP server exposes simple health endpoint; test it post-startup

**Detection:**
- `systemctl status esp32-mcp` shows "inactive" or "failed"
- `journalctl -u esp32-mcp` shows error like "FileNotFoundError" or "PermissionError"
- Service crashes immediately after start

**Phase:** Phase 4 (Pi Infrastructure) — implement health checks and monitoring

---

### Pitfall 20: Port Conflict / Service Binding to Wrong Interface

**What goes wrong:**
- MCP server configured to listen on localhost (127.0.0.1:5000)
- Main machine on LAN can't connect (expected: 192.168.x.x:5000)
- Or: MCP service listens on 0.0.0.0:5000 but firewall blocks it
- Or: Port 5000 already in use by another service

**Why it happens:**
- Default binding in code is localhost (for security when testing)
- Configuration mismatch between documentation and actual behavior
- Port already used by another service (Node, Python dev server, etc.)
- Firewall rule blocks inbound traffic

**Consequences:**
- Claude can't connect to MCP server over LAN
- Entire automation unavailable despite service running

**Prevention:**
- **Explicit configuration:** Document and require binding address + port in config
  ```yaml
  mcp_server:
    host: "0.0.0.0"  # listen on all interfaces
    port: 5000
  ```
- **Validate binding at startup:** Attempt to bind, fail loudly if port in use
  ```python
  try:
      server.bind((host, port))
  except OSError as e:
      raise ValueError(f"Cannot bind to {host}:{port}: {e}")
  ```
- **Port conflict detection:** Check if port already in use before starting
  ```bash
  lsof -i :5000 || echo "Port 5000 is free"
  ```
- **Firewall verification:** Document any required firewall rules; test connectivity from main machine
  ```bash
  nmap -p 5000 192.168.x.x  # from main machine
  ```
- **Startup logging:** Log binding address and port on startup
  ```
  "MCP server listening on 0.0.0.0:5000"
  ```

**Detection:**
- Service is running but `curl http://192.168.x.x:5000/health` times out
- `netstat -tlnp | grep 5000` shows nothing or wrong interface

**Phase:** Phase 4 (Pi Infrastructure) — validate at service startup

---

### Pitfall 21: Network Latency & Timeout Expectations

**What goes wrong:**
- Tool works when Pi and main machine are on 5GHz WiFi with low latency (10ms)
- Switch to slower network or WiFi congestion, latency jumps to 100-200ms
- Timeouts set too aggressively (5s) now fail on slow network
- MCP protocol timeout (default 30s) is too short for slow board operations

**Why it happens:**
- Timeouts set based on fast network conditions
- No distinction between network latency and board responsiveness
- MCP protocol has hard timeout limit
- WiFi interference or distance increases latency unpredictably

**Consequences:**
- Operations fail on slower networks that work fine on fast networks
- Unreliable automation
- User thinks it's broken when it's just slow

**Prevention:**
- **Progressive timeouts:** Distinguish network vs. board latency
  - Network ping: 10ms timeout (quick detect)
  - REPL command: 5s timeout (includes network + board processing)
  - File transfer: 30s timeout (includes multiple round-trips)
  - Firmware flash: 120s timeout (large data transfer)
- **Adaptive timeout:** Measure network latency at startup, adjust timeouts accordingly
  ```python
  latency = measure_ping_latency()
  repl_timeout = max(5, latency * 2) + 2  # 2x network latency + 2s buffer
  ```
- **Timeout documentation:** Document expected latency for each operation
- **Testing:** Test operations on slow network (simulate with `tc qdisc` on Pi)
- **Graceful degradation:** If operation slow but succeeding, don't fail — just log slow warning

**Detection:**
- Tool works on fast network, fails on slow network
- Timeout errors increase when WiFi is congested
- Large file transfers fail due to timeout

**Phase:** Phase 4 (Pi Infrastructure) — implement adaptive timeouts

---

### Pitfall 22: Disk Space Exhaustion on Pi

**What goes wrong:**
- Pi's `/` filesystem fills up (firmware cache, logs, old files)
- MCP server can't write to disk, crashes
- Service stops, automation unavailable

**Why it happens:**
- Firmware cache grows unbounded (each downloaded firmware is 1-3MB)
- Log files accumulate (journalctl, custom logs)
- Temporary files not cleaned up
- Pi has limited storage (typical 16-32GB SD card)

**Consequences:**
- Service crash
- Can't write new logs or cache files
- Requires manual cleanup to recover

**Prevention:**
- **Firmware cache limit:** Keep only last N firmware versions locally
  ```python
  CACHE_LIMIT = 5  # Keep last 5 versions
  cache_files = sorted(glob.glob(f"{CACHE_DIR}/*.bin"),
                       key=os.path.getctime)
  for f in cache_files[:-CACHE_LIMIT]:
      os.remove(f)
  ```
- **Log rotation:** Configure systemd journal to limit size
  ```ini
  [Journal]
  RuntimeMaxUse=100M
  SystemMaxUse=500M
  ```
- **Temporary file cleanup:** Delete temp files after operations
  ```python
  import tempfile
  temp_dir = tempfile.mkdtemp()
  try:
      # use temp_dir
  finally:
      shutil.rmtree(temp_dir)
  ```
- **Disk monitoring:** Check free space at startup, warn if <500MB
  ```python
  import shutil
  stat = shutil.disk_usage("/")
  if stat.free < 500 * 1024 * 1024:  # 500MB
      logging.warning(f"Low disk space: {stat.free / 1024 / 1024:.0f}MB free")
  ```

**Detection:**
- Service crashes with "No space left on device"
- `df -h` shows `/` at >95% capacity
- `journalctl` shows journal write failures

**Phase:** Phase 4 (Pi Infrastructure) — implement housekeeping

---

## Prevention Checklist

**Critical issues to address before going live:**

- [ ] **USB Permissions**: udev rules installed, service user in dialout group, test as service user
- [ ] **Serial Timeout**: Set serial port timeout to 2s, prevent blocking reads
- [ ] **Device Locking**: Exclusive lock per `/dev/ttyUSB*` before any operation
- [ ] **Chip Detection**: Explicit chip type config, validation before flashing, multi-retry on detect fail
- [ ] **Firmware Registry**: Catalog of known-good URLs per chip variant, local caching with checksums
- [ ] **File System Pre-check**: Query available space before upload, enforce 60% safe utilization
- [ ] **Tool Selection**: Single tool (rshell or mpremote) for file operations, version pinned
- [ ] **WebREPL Password**: Mandatory non-default password, stored in Pi config
- [ ] **Concurrent Access**: MCP server enforces per-board locking, rejects simultaneous operations
- [ ] **Error Codes**: Structured error responses with actionable messages (not generic "Error")
- [ ] **REPL Robustness**: Markers for command/output delimit, flush before read, raw REPL mode
- [ ] **systemd Service**: Unit file validated, dependencies explicit, startup health check
- [ ] **Port Binding**: Explicit config for listen address, startup validation, firewall verification
- [ ] **Disk Management**: Firmware cache rotation, log limits, disk space monitoring
- [ ] **WiFi Persistence**: Never erase SPIFFS during normal firmware update, validate post-flash

---

## Sources

**Knowledge from domain expertise and common patterns in ESP32/MicroPython tooling:**

- esptool documentation and GitHub issues
- MicroPython official documentation and forums
- Raspberry Pi hardware and software best practices
- systemd service management documentation
- Python serial port and asyncio patterns
- MCP (Model Context Protocol) server design patterns

*Note: This research is based on established patterns in ESP32/MicroPython community, official documentation cross-references, and known pitfalls documented in tool repositories and forums. No single URL source covers all domains — findings synthesized from documentation and real-world experience.*
