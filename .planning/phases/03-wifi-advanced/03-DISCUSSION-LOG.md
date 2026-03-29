# Phase 3: WiFi & Advanced - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-29
**Phase:** 03-wifi-advanced
**Areas discussed:** OTA transport protocol, Board WiFi addressing, OTA fallback behavior, GitHub integration design

---

## OTA Transport Protocol

| Option | Description | Selected |
|--------|-------------|----------|
| WebREPL | MicroPython's built-in WebSocket-based file transfer. Requires webrepl_cfg.py on board and webrepl_cli.py on Pi. Battle-tested, ≤200KB transfers are reliable. | ✓ |
| mpremote over network | No native WiFi transport — would require SSH tunnel or board-side daemon. Significantly more complex. | |
| Raw socket / HTTP PUT | Board runs tiny HTTP server (e.g. uhttpd) to receive uploads. Custom but flexible. Requires deploying server code first. | |

**User's choice:** WebREPL

### File Size Limit

| Option | Description | Selected |
|--------|-------------|----------|
| 200KB hard limit | Matches research-identified reliability threshold. Fail fast with clear error above this. | ✓ |
| No hard limit | Best effort regardless of size; rely on timeout. Less predictable. | |
| Configurable limit | Default 200KB, overridable per-call. | |

**User's choice:** 200KB hard limit

### WebREPL Authentication

| Option | Description | Selected |
|--------|-------------|----------|
| Password per-call | Caller provides WebREPL password as parameter. No stored secrets on Pi. | ✓ |
| Stored in board state | Pi persists password keyed by board IP in ~/.esp32-station/. Convenient but stores credentials. | |
| You decide | Claude picks simplest approach. | |

**User's choice:** Password per-call

### OTA Success Response

| Option | Description | Selected |
|--------|-------------|----------|
| Match deploy_file pattern | Return {port, files_written, transport: "wifi"} — consistent with USB deploy tools. | ✓ |
| Minimal ack | Just {ok: true, file: ...}. Simpler but inconsistent. | |
| You decide | Claude decides. | |

**User's choice:** Match deploy_file pattern

---

## Board WiFi Addressing

| Option | Description | Selected |
|--------|-------------|----------|
| IP/host per-call | OTA tool takes a `host` parameter. No auto-discovery. Caller knows board's address. | ✓ |
| Persisted in board state | Pi stores board IP in boards.json keyed by port. IPs change with DHCP. | |
| Auto-discovered via mDNS | Pi queries mDNS for boards advertising WebREPL. Requires mDNS setup + avahi-daemon. | |

**User's choice:** IP/host per-call

### OTA Tool Signature

| Option | Description | Selected |
|--------|-------------|----------|
| Combined: port + host | deploy_ota(port, host, remote_path, password) — port for fallback, host for WiFi. Single call. | |
| Separate tools: OTA + USB stays separate | Two distinct tools; Claude handles fallback logic by calling the right one. | ✓ |
| deploy_ota_wifi + auto fallback via board state | One OTA tool, no port param — fallback via state lookup. | |

**User's choice:** Two separate tools — Claude handles fallback

---

## OTA Fallback Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Specific error code with fallback hint | Return {error: "wifi_unreachable", fallback: "use deploy_file_to_board"} — Claude decides what to do. | ✓ |
| Auto-fallback if port provided | Automatically attempt USB on wifi_unreachable. Mixes responsibilities. | |
| Plain error, no hint | Return {error: "wifi_unreachable"} — let Claude figure out next steps. | |

**User's choice:** Specific error code with fallback hint

### Unreachability Detection

| Option | Description | Selected |
|--------|-------------|----------|
| Connection timeout only | Attempt WebREPL connect; return wifi_unreachable if doesn't complete within N seconds. | ✓ |
| Ping first, then connect | ICMP ping before WebREPL attempt. Faster failure but requires ping permission. | |
| You decide | Claude picks simplest reliable detection. | |

**User's choice:** Connection timeout only

---

## GitHub Integration Design

### Pull Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| git subprocess | Run git clone/pull as subprocess in temp dir. Follows existing subprocess pattern. Public + private repos. | ✓ |
| HTTP tarball download | Download .tar.gz via requests/urllib. No git needed. Less flexible. | |
| GitHub API | REST API to fetch file tree + blobs. Complex for large repos; rate limits. | |

**User's choice:** git subprocess

### Private Repo Support

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — token per-call | Optional `token` param. Passed via URL embedding. Never stored. | ✓ |
| Public repos only | Simpler. No auth handling. | |
| Token in config/env | Stored in ~/.esp32-station/config.json or GITHUB_TOKEN env var. Requires setup step. | |

**User's choice:** Token per-call (optional)

### Repo Configuration

| Option | Description | Selected |
|--------|-------------|----------|
| repo_url per-call | pull_and_deploy_github(port, repo_url, branch='main', ...). No state management. | ✓ |
| Configured once per board in state | Default repo/branch in boards.json. Requires setup step. | |
| Both — per-call overrides stored | Flexible but more complex. | |

**User's choice:** repo_url per-call

### Deploy Transport After Pull

| Option | Description | Selected |
|--------|-------------|----------|
| Always via USB | Pull to temp dir, then deploy_directory() via USB. Simple and reliable. | ✓ |
| Via WiFi if board has IP configured | Auto-detect transport. Mixes concerns. | |
| Caller specifies transport | transport='usb'|'wifi' parameter. Explicit but verbose. | |

**User's choice:** Always via USB

---

## Claude's Discretion

- Exact WebREPL connection timeout value
- Temp directory location for GitHub clones on Pi
- git clone vs git pull logic (first-time vs subsequent)
- Whether to keep temp dir as cache or clean up after deploy

## Deferred Ideas

None.
