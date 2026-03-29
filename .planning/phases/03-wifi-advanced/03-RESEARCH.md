# Phase 3: WiFi & Advanced - Research

**Researched:** 2026-03-29
**Domain:** MicroPython WebREPL file transfer, Git subprocess automation, MCP tool integration
**Confidence:** MEDIUM-HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**OTA Transport**
- D-01: Use WebREPL as the OTA mechanism — MicroPython's built-in WebSocket file transfer. Requires `webrepl_cli.py` script on the Pi and `webrepl_cfg.py` on the board (pre-configured by user).
- D-02: Hard limit of 200KB per OTA transfer. Fail fast with `{"error": "ota_payload_too_large", "detail": "..."}` if payload exceeds this.
- D-03: WebREPL password passed as a per-call parameter — never stored on Pi. No credential persistence.
- D-04: OTA success response matches deploy_file pattern: `{"port": ..., "files_written": [...], "transport": "wifi"}` — consistent with existing USB deploy tools.

**Board WiFi Addressing**
- D-05: Board's WiFi address (IP or hostname) is provided by the caller as a `host` parameter per-call. No auto-discovery, no persistence in board state.

**OTA Fallback**
- D-06: Two separate tools — `deploy_ota_wifi()` and the existing `deploy_file_to_board()`. No automatic fallback inside the OTA tool. Claude decides when to call which.
- D-07: When the board is unreachable over WiFi, `deploy_ota_wifi()` returns `{"error": "wifi_unreachable", "detail": "...", "fallback": "use deploy_file_to_board"}` — the `fallback` hint tells Claude exactly what to do next.
- D-08: WiFi unreachability is detected by connection timeout only — no ICMP ping pre-check. Attempt WebREPL connect; return `wifi_unreachable` if it doesn't complete within the timeout.

**GitHub Integration**
- D-09: Pi pulls from GitHub using `git` subprocess (`git clone` or `git pull` in a temp/work directory). Follows existing subprocess pattern from Phase 1/2.
- D-10: Optional `token` parameter for private repos — passed via URL embedding (`https://token@github.com/...`). Token is never stored by the tool.
- D-11: `repo_url` and `branch` (default `main`) provided per-call. No stored per-board repo config.
- D-12: After pulling, deploy to board via USB using existing `deploy_directory()` — not via WiFi. GitHub tool is a USB-deploy wrapper with a git pull prefix.

**Patterns (carried from Phase 2)**
- D-13: Error dict pattern: `{"error": "snake_case_code", "detail": "human string"}` — never raise exceptions to callers.
- D-14: New tools follow thin `@mcp.tool()` wrapper in `mcp_server.py` + module in `tools/`.

### Claude's Discretion
- Exact WebREPL timeout value for `wifi_unreachable` detection
- Temp directory location for GitHub clones on Pi
- `git clone` vs `git pull` logic (first-time vs subsequent runs)
- Whether to clean up temp dir after deploy or keep as cache

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEPLOY-05 | Claude can pull the latest code from a GitHub repo and deploy it to the board | Git subprocess pattern established; `deploy_directory()` reuse verified |
| OTA-01 | Claude can push a code update to a board over WiFi (WebREPL or equivalent) | `webrepl_cli.py` invocation syntax documented; subprocess integration pattern clear |
| OTA-02 | OTA falls back to USB if WiFi is unavailable | Two-tool pattern with `fallback` hint in error dict fully specified in D-06/D-07 |
</phase_requirements>

---

## Summary

Phase 3 adds two new MCP tools to the existing FastMCP server: `deploy_ota_wifi()` (OTA-01, OTA-02) and `pull_and_deploy_github()` (DEPLOY-05). Both follow established Phase 2 patterns exactly — thin `@mcp.tool()` wrappers in `mcp_server.py` with logic in `tools/` modules, subprocess calls, and structured error dicts.

The core technical challenge is `webrepl_cli.py`, a standalone Python script from the MicroPython project that must be obtained and placed on the Pi. It has no built-in socket timeout, which means the subprocess call MUST use `subprocess.run(..., timeout=N)` to prevent indefinite hangs. The script exits with code 0 on success and code 1 on error; subprocess `returncode` is the reliable success check.

For GitHub integration, `git` is already installed (v2.53.0 confirmed). The standard `subprocess.run(['git', 'clone', ...])` pattern applies directly. The key decision (D-12) that GitHub deploys via USB (not WiFi) means `deploy_directory()` from Phase 2 is called after the clone — no new deploy mechanism needed.

**Primary recommendation:** Implement `tools/ota_wifi.py` (wrapping `webrepl_cli.py` subprocess) and `tools/github_deploy.py` (wrapping `git` + calling `deploy_directory`), then register both in `mcp_server.py` as `@mcp.tool()` decorators.

---

## Standard Stack

### Core (all already in project)
| Library/Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| subprocess (stdlib) | Python 3.14 | Run webrepl_cli.py and git as child processes | Established project pattern from Phase 1/2 |
| pathlib (stdlib) | Python 3.14 | Temp dir paths, file size checks | Already used in `tools/file_deploy.py` |
| tempfile (stdlib) | Python 3.14 | Create temp dirs for git clones | stdlib; no external dep needed |
| git | 2.53.0 (system) | Clone/pull GitHub repos | Pre-installed on Pi; confirmed available |

### New Dependency
| Library/Tool | Version | Purpose | How to Obtain |
|---------|---------|---------|--------------|
| webrepl_cli.py | latest (pinned commit) | WebREPL file upload to ESP32 | Manual download from micropython/webrepl GitHub; vendor into project as `tools/vendor/webrepl_cli.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| webrepl_cli.py subprocess | websockets library + raw WS protocol | Would require implementing WebREPL binary protocol; webrepl_cli.py is the reference implementation |
| subprocess git | gitpython library | gitpython's timeout support is known-broken; subprocess git is simpler and matches project pattern |
| tempfile.mkdtemp | hardcoded /tmp path | mkdtemp is portable; avoids race conditions in concurrent calls |

**Installation note:** `webrepl_cli.py` is NOT pip-installable from an official package. It must be vendored. The PyPI `webrepl` package is a third-party fork with different APIs — do not use it.

---

## Architecture Patterns

### Recommended Project Structure (additions only)
```
tools/
├── ota_wifi.py          # deploy_ota_wifi() — new
├── github_deploy.py     # pull_and_deploy_github() — new
└── vendor/
    └── webrepl_cli.py   # vendored from micropython/webrepl
mcp_server.py            # add two @mcp.tool() registrations
tests/
├── test_ota_wifi.py     # new
└── test_github_deploy.py # new
```

### Pattern 1: WebREPL OTA Tool Structure
**What:** Thin MCP wrapper that size-checks the file, then runs `webrepl_cli.py` as a subprocess with explicit timeout.
**When to use:** WiFi path; board must have WebREPL pre-configured.
**Example:**
```python
# tools/ota_wifi.py
import subprocess
import pathlib

WEBREPL_CLI = pathlib.Path(__file__).parent / "vendor" / "webrepl_cli.py"
OTA_SIZE_LIMIT = 200 * 1024   # 200KB (D-02)
WIFI_TIMEOUT_SECONDS = 30     # discretion: 30s covers slow WiFi; fast fail on unreachable


def deploy_ota_wifi(host: str, local_path: str, remote_path: str, password: str) -> dict:
    local = pathlib.Path(local_path)

    # Size gate (D-02)
    if local.stat().st_size > OTA_SIZE_LIMIT:
        return {
            "error": "ota_payload_too_large",
            "detail": f"File is {local.stat().st_size} bytes; limit is {OTA_SIZE_LIMIT}",
        }

    # Invoke webrepl_cli.py: python3 webrepl_cli.py -p <password> <local> <host>:<remote>
    try:
        result = subprocess.run(
            ["python3", str(WEBREPL_CLI), "-p", password, str(local), f"{host}:{remote_path}"],
            capture_output=True,
            text=True,
            timeout=WIFI_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "error": "wifi_unreachable",
            "detail": f"WebREPL connection to {host} timed out after {WIFI_TIMEOUT_SECONDS}s",
            "fallback": "use deploy_file_to_board",
        }

    if result.returncode != 0:
        # Distinguish connection failure from other errors
        stderr_lower = result.stderr.lower()
        if "connect" in stderr_lower or "refused" in stderr_lower or "timeout" in stderr_lower:
            return {
                "error": "wifi_unreachable",
                "detail": result.stderr.strip(),
                "fallback": "use deploy_file_to_board",
            }
        return {"error": "ota_failed", "detail": result.stderr.strip() or result.stdout.strip()}

    return {
        "port": host,
        "files_written": [remote_path],
        "transport": "wifi",
    }
```

### Pattern 2: GitHub Deploy Tool Structure
**What:** git clone/pull into temp dir, then call existing `deploy_directory()`.
**When to use:** User wants to deploy latest code from a GitHub repository to a board via USB.
**Example:**
```python
# tools/github_deploy.py
import subprocess
import tempfile
import pathlib
from tools.file_deploy import deploy_directory

GIT_TIMEOUT_SECONDS = 60   # network clone can be slow; 60s is generous for small projects


def pull_and_deploy_github(
    port: str, repo_url: str, branch: str = "main", token: str | None = None
) -> dict:
    # Embed token in URL for private repos (D-10)
    if token:
        if repo_url.startswith("https://"):
            repo_url = repo_url.replace("https://", f"https://{token}@", 1)

    with tempfile.TemporaryDirectory(prefix="esp32-github-") as tmpdir:
        repo_dir = pathlib.Path(tmpdir) / "repo"

        # git clone --branch <branch> --depth 1 <url> <dir>
        try:
            result = subprocess.run(
                ["git", "clone", "--branch", branch, "--depth", "1", repo_url, str(repo_dir)],
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {
                "error": "git_clone_timeout",
                "detail": f"git clone timed out after {GIT_TIMEOUT_SECONDS}s",
            }
        except FileNotFoundError:
            return {"error": "git_not_found", "detail": "'git' not found on system PATH"}

        if result.returncode != 0:
            # Sanitize: remove embedded token from error output before returning
            safe_detail = result.stderr.replace(token, "***") if token else result.stderr
            return {"error": "git_clone_failed", "detail": safe_detail.strip()}

        # Reuse existing deploy_directory (D-12) — SerialLock is applied in mcp_server.py
        deploy_result = deploy_directory(port, str(repo_dir))

    return deploy_result
```

### Pattern 3: MCP Registration (mcp_server.py additions)
```python
# In mcp_server.py — following existing @mcp.tool() pattern
from tools.ota_wifi import deploy_ota_wifi as _deploy_ota_wifi
from tools.github_deploy import pull_and_deploy_github as _pull_and_deploy_github

@mcp.tool()
def deploy_ota_wifi(host: str, local_path: str, remote_path: str, password: str) -> dict:
    """Deploy a file to an ESP32 over WiFi using WebREPL.
    ...
    """
    return _deploy_ota_wifi(host, local_path, remote_path, password)


@mcp.tool()
def pull_and_deploy_github(
    port: str, repo_url: str, branch: str = "main", token: str | None = None
) -> dict:
    """Pull latest code from a GitHub repo and deploy it to a board via USB.
    ...
    """
    try:
        with SerialLock(port):
            return _pull_and_deploy_github(port, repo_url, branch, token)
    except TimeoutError as e:
        return {"error": "serial_lock_timeout", "detail": str(e)}
```

### Anti-Patterns to Avoid
- **Storing the WebREPL password:** Never persist in state files, logs, or env vars. Pass through call only (D-03).
- **Storing the GitHub token:** Never log the raw URL with embedded token. Sanitize before returning error messages.
- **Using the PyPI `webrepl` package:** It is a third-party fork, not the official MicroPython client. Its API differs from `webrepl_cli.py`.
- **Calling webrepl_cli.py without subprocess timeout:** The script has no internal socket timeout. Without `timeout=N` in `subprocess.run`, it can hang indefinitely if the board is unreachable.
- **Using `git pull` instead of `git clone --depth 1`:** The tool has no persistent work dir (each call uses a fresh temp dir), so `git pull` cannot be used. `git clone --depth 1` is correct and faster.
- **Applying SerialLock in the module function:** SerialLock must be applied in `mcp_server.py` wrapper, not inside `tools/` — same pattern as Phase 2.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WebREPL binary WebSocket protocol | Custom WS client | `webrepl_cli.py` (vendored) | Protocol has binary framing, auth handshake, chunked transfer — non-trivial to implement correctly |
| Git repo fetching | Custom HTTP download | `git` subprocess | Handles auth, branching, LFS, redirects; single well-tested tool |
| Directory deployment | Custom file copy loop | Existing `deploy_directory()` | Already handles exclusions, space checks, integrity verification |
| Timeout enforcement | Thread-based watchdog | `subprocess.run(..., timeout=N)` | stdlib raises `subprocess.TimeoutExpired` cleanly; no threads needed |

**Key insight:** Both new tools are thin orchestration shells. The hard work (WebREPL protocol, git, deploy logic) is done by existing tools. This phase is about wiring, not building.

---

## Common Pitfalls

### Pitfall 1: webrepl_cli.py Hangs Without Timeout
**What goes wrong:** `webrepl_cli.py` uses raw socket reads with no timeout set. If the board is unreachable or WiFi drops mid-transfer, the subprocess hangs forever.
**Why it happens:** The script predates robust timeout handling; socket default is blocking.
**How to avoid:** Always pass `timeout=WIFI_TIMEOUT_SECONDS` to `subprocess.run`. Catch `subprocess.TimeoutExpired` and return the `wifi_unreachable` error dict with `"fallback"` key.
**Warning signs:** MCP tool call never returns; server process appears blocked.

### Pitfall 2: webrepl_cli.py returncode Ambiguity
**What goes wrong:** The script calls `sys.exit(1)` for argument errors, not just connection failures. A returncode of 1 can mean "wrong arguments" or "board refused connection."
**Why it happens:** Minimal error handling in the script; no error codes, only exit status.
**How to avoid:** Parse stderr content to distinguish `wifi_unreachable` (connection error) from `ota_failed` (other errors). Check for keywords: "connect", "refused", "timeout" in stderr.
**Warning signs:** Tool returns `ota_failed` for clearly-reachable board; stderr contains argument usage text.

### Pitfall 3: Token Leaked in Error Output
**What goes wrong:** `git clone https://token@github.com/...` fails; the subprocess captures stderr which contains the full URL with token. Returning this raw in the error dict leaks the credential.
**Why it happens:** git includes the URL in error messages when clone fails.
**How to avoid:** If `token` parameter is set, run `detail.replace(token, "***")` before returning error dict.
**Warning signs:** Error response contains token string verbatim.

### Pitfall 4: webrepl_cli.py Not Found at Runtime
**What goes wrong:** Tool fails with `FileNotFoundError` or `python3: can't open file` because `webrepl_cli.py` was not vendored into the project.
**Why it happens:** `webrepl_cli.py` is not pip-installable; it must be manually placed on the Pi.
**How to avoid:** Vendor the script at `tools/vendor/webrepl_cli.py`. Reference it via `pathlib.Path(__file__).parent / "vendor" / "webrepl_cli.py"` so path is always absolute relative to the module. Add a pre-check: if path does not exist, return `{"error": "webrepl_cli_missing", "detail": "..."}` early.
**Warning signs:** `FileNotFoundError` in subprocess call; script was not added to git.

### Pitfall 5: PyPI `webrepl` Package (Wrong Package)
**What goes wrong:** Developer runs `pip install webrepl`, gets a third-party package with a different Python API, tries to call `webrepl_cli.py` CLI syntax through it — fails.
**Why it happens:** Name collision on PyPI.
**How to avoid:** Do NOT `pip install webrepl`. Vendor `webrepl_cli.py` directly from `https://github.com/micropython/webrepl/blob/master/webrepl_cli.py`. Document this clearly in requirements.txt comments.
**Warning signs:** `import webrepl` works but CLI invocation syntax fails; wrong API.

### Pitfall 6: git clone Depth and Branch Name Mismatch
**What goes wrong:** `git clone --branch main` fails if the repo's default branch is `master` or a custom name, or if `main` doesn't exist.
**Why it happens:** GitHub default branch name varies per repo.
**How to avoid:** Catch non-zero returncode from git clone; return `{"error": "git_clone_failed", "detail": ...}` with sanitized message. The `branch` parameter (default `"main"`) is caller-controlled — document that the caller must know the correct branch.
**Warning signs:** returncode 128 from git; stderr "Remote branch main not found".

### Pitfall 7: OTA Transfer Fails Partway (Partial File)
**What goes wrong:** WiFi drops mid-transfer. The board has a partially-written file at the remote path. The board may boot the corrupt file next restart.
**Why it happens:** WebREPL PUT is not atomic; it writes incrementally.
**How to avoid:** WebREPL protocol has a response after transfer completes — `webrepl_cli.py` exit code 0 means the server acknowledged completion. A non-zero exit or timeout means incomplete. Document in tool description that a failed OTA may leave a corrupt file; recommend re-deploying via USB if OTA fails.
**Warning signs:** returncode non-zero after partial upload; board behaves erratically after interrupted OTA.

---

## Code Examples

### Verified: webrepl_cli.py Upload Invocation
```bash
# Source: https://techoverflow.net/2020/02/22/how-to-upload-files-to-micropython-using-webrepl-using-webrepl_cli-py/
# and https://github.com/micropython/webrepl (official repo README)
python3 webrepl_cli.py -p <password> <local_file> <host>:<remote_path>

# Example:
python3 webrepl_cli.py -p mypassword main.py 192.168.1.42:/main.py
python3 webrepl_cli.py -p mypassword main.py esp32-board.local:/main.py
```

Host format: bare IP or hostname (not `ws://` prefix — that's WebREPL web client syntax, not CLI syntax). Default port is 8266; non-default port is `host:port` before the colon of the remote path.

### Verified: subprocess git clone with timeout
```python
# Source: stdlib subprocess docs; established project pattern
result = subprocess.run(
    ["git", "clone", "--branch", branch, "--depth", "1", repo_url, str(repo_dir)],
    capture_output=True,
    text=True,
    timeout=60,
)
```

### Verified: tempfile.TemporaryDirectory context manager
```python
# Source: Python 3 stdlib docs
# Auto-cleans on context exit — preferred over mkdtemp for this use case
with tempfile.TemporaryDirectory(prefix="esp32-github-") as tmpdir:
    repo_dir = pathlib.Path(tmpdir) / "repo"
    # ... clone into repo_dir ...
    result = deploy_directory(port, str(repo_dir))
# tmpdir removed automatically here
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| git | DEPLOY-05 (github clone) | Yes | 2.53.0 | None needed |
| python3 | OTA-01 (run webrepl_cli.py) | Yes | 3.14.3 | None needed |
| webrepl_cli.py | OTA-01 | Not yet | — | Must be vendored from micropython/webrepl |
| pytest (venv) | Test suite | Not installed | — | Run `pip install -r requirements.txt` in venv |

**Missing dependencies with no fallback:**
- `webrepl_cli.py` must be downloaded from `https://github.com/micropython/webrepl` and placed at `tools/vendor/webrepl_cli.py`. This is a Wave 0 task.

**Missing dependencies with fallback:**
- `pytest` is not installed in the venv (`venv/lib/python3.14/site-packages/` is empty). Wave 0 must run `pip install -r requirements.txt` inside the venv. Until then, tests cannot run.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (configured in `pytest.ini`) |
| Config file | `/mnt/anton/Claude/ESP32-server/pytest.ini` (testpaths = tests, asyncio_mode = auto) |
| Quick run command | `venv/bin/pytest tests/test_ota_wifi.py tests/test_github_deploy.py -x` |
| Full suite command | `venv/bin/pytest tests/ -x` |

Note: `venv/bin/pytest` does not yet exist — Wave 0 must install dependencies.

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OTA-01 | deploy_ota_wifi success path (mocked subprocess) | unit | `venv/bin/pytest tests/test_ota_wifi.py::test_deploy_ota_wifi_success -x` | No — Wave 0 |
| OTA-01 | payload too large returns ota_payload_too_large | unit | `venv/bin/pytest tests/test_ota_wifi.py::test_deploy_ota_wifi_too_large -x` | No — Wave 0 |
| OTA-02 | timeout returns wifi_unreachable with fallback hint | unit | `venv/bin/pytest tests/test_ota_wifi.py::test_deploy_ota_wifi_timeout -x` | No — Wave 0 |
| OTA-02 | connection error returns wifi_unreachable with fallback hint | unit | `venv/bin/pytest tests/test_ota_wifi.py::test_deploy_ota_wifi_connection_error -x` | No — Wave 0 |
| DEPLOY-05 | pull_and_deploy_github success path (mocked git + deploy) | unit | `venv/bin/pytest tests/test_github_deploy.py::test_pull_and_deploy_success -x` | No — Wave 0 |
| DEPLOY-05 | git clone timeout returns git_clone_timeout | unit | `venv/bin/pytest tests/test_github_deploy.py::test_git_clone_timeout -x` | No — Wave 0 |
| DEPLOY-05 | private repo token sanitized in error output | unit | `venv/bin/pytest tests/test_github_deploy.py::test_token_not_leaked -x` | No — Wave 0 |
| DEPLOY-05 | webrepl_cli_missing returns structured error | unit | `venv/bin/pytest tests/test_ota_wifi.py::test_webrepl_cli_missing -x` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `venv/bin/pytest tests/test_ota_wifi.py tests/test_github_deploy.py -x`
- **Per wave merge:** `venv/bin/pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_ota_wifi.py` — covers OTA-01, OTA-02
- [ ] `tests/test_github_deploy.py` — covers DEPLOY-05
- [ ] Install dependencies: `cd /mnt/anton/Claude/ESP32-server && python3 -m venv venv && venv/bin/pip install -r requirements.txt`
- [ ] Vendor webrepl_cli.py: `mkdir -p tools/vendor && curl -o tools/vendor/webrepl_cli.py https://raw.githubusercontent.com/micropython/webrepl/master/webrepl_cli.py`

---

## Open Questions

1. **webrepl_cli.py behavior when `webrepl_cfg.py` is missing on board**
   - What we know: WebREPL must be pre-configured on the board by the user (D-01 explicitly scopes this out)
   - What's unclear: Exact error message from webrepl_cli.py when board has WebREPL disabled; whether returncode is 1 or it hangs
   - Recommendation: Add a note in the tool docstring that the board must have WebREPL enabled. The `wifi_unreachable` or `ota_failed` error will surface naturally; no special handling needed since board configuration is user responsibility.

2. **Optimal WebREPL timeout value**
   - What we know: webrepl_cli.py has no internal timeout; timeout is Claude's discretion
   - What's unclear: What value balances "fast fail for unreachable board" vs "slow WiFi networks"
   - Recommendation: Use 30 seconds. A reachable board on LAN will connect in < 2 seconds; 30s is a comfortable margin for slow WiFi while failing fast enough to be usable.

3. **Git clone cache vs fresh clone per call**
   - What we know: Decisions leave this to Claude's discretion
   - What's unclear: Whether keeping a persistent clone directory improves UX (faster subsequent deploys) or introduces stale state risk
   - Recommendation: Use `tempfile.TemporaryDirectory` (fresh clone per call). Avoids stale state, merge conflicts, and dirty working tree issues. For the small repos typical in ESP32 projects with `--depth 1`, clone time is under 5 seconds. Cache optimization belongs in v2.

---

## Sources

### Primary (HIGH confidence)
- Official `webrepl_cli.py` source: https://github.com/micropython/webrepl/blob/master/webrepl_cli.py — invocation syntax, argument format, exit behavior
- Python stdlib subprocess docs — `subprocess.run` timeout, `TimeoutExpired`, `capture_output`
- Python stdlib tempfile docs — `TemporaryDirectory` context manager

### Secondary (MEDIUM confidence)
- TechOverflow tutorial (2020): https://techoverflow.net/2020/02/22/how-to-upload-files-to-micropython-using-webrepl-using-webrepl_cli-py/ — command-line invocation example verified against source
- GitHub Issue micropython/webrepl#7 — freeze behavior with no timeout confirmed; no internal timeout exists

### Tertiary (LOW confidence, needs validation)
- WebSearch finding: PyPI `webrepl` package is third-party fork — verify before recommending avoidance (confirmed by README inspection; avoid it)
- Community reports of webrepl_cli.py `sys.exit(1)` for both argument errors and connection failures — verify by inspecting script directly

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — webrepl_cli.py source code read directly; git and subprocess are stdlib/system tools
- Architecture patterns: HIGH — follows established Phase 2 patterns exactly; no novel patterns needed
- Pitfalls: MEDIUM-HIGH — timeout hang confirmed via GitHub issue; token leak is standard security practice; others are inferred from source code behavior

**Research date:** 2026-03-29
**Valid until:** 2026-07-01 (WebREPL CLI is stable; git is stable; MicroPython protocol unlikely to change)
