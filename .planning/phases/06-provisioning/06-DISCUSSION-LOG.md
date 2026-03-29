# Phase 6: Provisioning - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 06-provisioning
**Areas discussed:** Credential storage, boot.py generation, User guidance style, Provisioning flow

---

## Credential Storage

### Credential File Format

| Option | Description | Selected |
|--------|-------------|----------|
| JSON (Recommended) | {ssid, password, webrepl_password}. Easy to parse, supports future fields. | ✓ |
| .env file | KEY=VALUE format. Needs python-dotenv. | |
| INI / configparser | [wifi] section. stdlib, no extra deps. | |

**User's choice:** JSON
**Notes:** None

### Credential File Location

| Option | Description | Selected |
|--------|-------------|----------|
| /etc/esp32-station/wifi.json (Recommended) | System config dir, outside repo. Permissions 600. | ✓ |
| ~/.esp32-station/wifi.json | User home dir. Easier for single-user Pi. | |
| You decide | Claude picks. | |

**User's choice:** /etc/esp32-station/wifi.json
**Notes:** None

### Multiple Networks

| Option | Description | Selected |
|--------|-------------|----------|
| Single network (Recommended) | One SSID + password + WebREPL password. Simpler. | |
| Multiple networks | Array of entries. Boards try each in order. | |
| You decide | Claude picks. | ✓ |

**User's choice:** You decide
**Notes:** None

### WebREPL Password Storage

| Option | Description | Selected |
|--------|-------------|----------|
| In credentials file (Recommended) | wifi.json has ssid, password, and webrepl_password. | ✓ |
| Fixed default password | Always uses a known default. Less secure. | |
| You decide | Claude picks. | |

**User's choice:** In credentials file
**Notes:** None

### Credential Module

| Option | Description | Selected |
|--------|-------------|----------|
| Shared utility (Recommended) | tools/credentials.py with load_credentials(). Reusable. | ✓ |
| Inline in tool | Read/parse JSON inside provisioning tool. Simpler. | |
| You decide | Claude picks. | |

**User's choice:** Shared utility
**Notes:** None

### Startup Validation

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy validation (Recommended) | Check only when tool needs credentials. Server starts without it. | ✓ |
| Startup validation | Server logs warning at startup if file missing. | |
| You decide | Claude picks. | |

**User's choice:** Lazy validation
**Notes:** None

### Missing Credentials Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Error with instructions (Recommended) | Return error with file path, format, example. User creates file manually. | ✓ |
| MCP tool to write credentials | set_wifi_credentials() tool. Violates SETUP-02. | |
| You decide | Claude picks within SETUP-02 constraint. | |

**User's choice:** Error with instructions
**Notes:** User asked how the file gets filled -- answered that setup.sh (Phase 7) prompts for it, and missing-file error gives manual creation instructions.

---

## boot.py Generation

### Generation Method

| Option | Description | Selected |
|--------|-------------|----------|
| Template with injection (Recommended) | templates/boot.py.tpl with placeholders. Credentials never in git. | ✓ |
| Python string builder | Generate as f-string. No template file. Harder to read. | |
| You decide | Claude picks. | |

**User's choice:** Template with injection
**Notes:** None

### boot.py Scope

| Option | Description | Selected |
|--------|-------------|----------|
| WiFi auto-connect | Connect to SSID on boot. | ✓ |
| WebREPL start | Start WebREPL daemon with password. | ✓ |
| mDNS advertisement | Advertise _webrepl._tcp via mDNS. | ✓ |
| Hostname setting | Set unique hostname per board. | ✓ |

**User's choice:** All four
**Notes:** Claude should prompt for a hostname if one isn't specified in the MicroPython code to be deployed.

### Deploy Tool

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated tool (Recommended) | New deploy_boot_config(port, hostname=None). Self-contained. | ✓ |
| Reuse deploy_file | Generate to temp file, call existing deploy_file(). | |
| You decide | Claude picks. | |

**User's choice:** Dedicated tool
**Notes:** None

### Overwrite Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Overwrite silently (Recommended) | Provisioning implies starting fresh. No confirmation. | ✓ |
| Warn and confirm | Return warning, require force flag. | |
| You decide | Claude picks. | |

**User's choice:** Overwrite silently
**Notes:** None

---

## User Guidance Style

### Delivery Method

| Option | Description | Selected |
|--------|-------------|----------|
| In tool return dict (Recommended) | user_action key with instruction and reason. Claude relays naturally. | ✓ |
| Separate guidance tool | get_provisioning_steps() returns all steps upfront. | |
| Inline in error messages | Instructions in error detail. Reactive. | |

**User's choice:** In tool return dict
**Notes:** None

### Timing

| Option | Description | Selected |
|--------|-------------|----------|
| Proactive (Recommended) | Tool returns user_action BEFORE the step. Two-step process. | ✓ |
| Embedded in flow | Attempts action, returns guidance after failure. | |
| You decide | Claude picks. | |

**User's choice:** Proactive
**Notes:** None

### Detail Level

| Option | Description | Selected |
|--------|-------------|----------|
| First-timer friendly (Recommended) | Full explanation of what, where, when. Claude can condense later. | ✓ |
| Brief / experienced | Short prompts. Assumes familiarity. | |
| You decide | Claude picks. | |

**User's choice:** First-timer friendly
**Notes:** None

---

## Provisioning Flow

### Readiness Levels

| Option | Description | Selected |
|--------|-------------|----------|
| Flash only | Erase + flash MicroPython. USB dev ready. | ✓ |
| Flash + WiFi config | Flash + deploy boot.py. Network-connected. | ✓ |
| Full provisioning | Flash + WiFi + deploy project code. Fully operational. | ✓ |
| WiFi config only | Deploy boot.py to already-flashed board. | ✓ |

**User's choice:** All four, plus "Full provisioning (USB only)" for battery/no-WiFi projects.
**Notes:** Claude should ask if WiFi should be disabled to save battery for projects that don't need it.

### Level Discovery Tool

| Option | Description | Selected |
|--------|-------------|----------|
| Claude just knows (Recommended) | No tool. Claude reads descriptions and chains. | ✓ |
| List-levels tool | get_provisioning_levels() returns static info. | |

**User's choice:** Claude just knows
**Notes:** None

### Auto-Verify

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, always (Recommended) | Claude calls health/status tools after provisioning. | ✓ |
| Optional / on request | Only if user asks. | |
| You decide | Claude picks. | |

**User's choice:** Yes, always
**Notes:** None

### Always-Erase Enforcement

| Option | Description | Selected |
|--------|-------------|----------|
| Already satisfied, just document (Recommended) | flash_firmware() already erases. Update description, add test. | ✓ |
| Add explicit enforcement | Additional check/assertion. Belt-and-suspenders. | |
| You decide | Claude picks. | |

**User's choice:** Already satisfied, just document
**Notes:** None

---

## Claude's Discretion

- Single vs multiple network support in credentials file
- boot.py template exact MicroPython code
- Exact user_action message wording
- How to condense guidance for experienced users
- mDNS service name and TXT record content

## Deferred Ideas

None -- discussion stayed within phase scope.
