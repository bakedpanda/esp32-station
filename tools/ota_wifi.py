"""OTA WiFi file deployment to ESP32 boards via webrepl_cli.py subprocess.

Requirements covered: OTA-01, OTA-02.

Provides:
  deploy_ota_wifi() — transfer a file to a board over WiFi using WebREPL

Prerequisites (user responsibility, D-01):
  - Board must have WebREPL enabled (webrepl_cfg.py present on board)
  - tools/vendor/webrepl_cli.py must be vendored from https://github.com/micropython/webrepl

Security notes (D-03):
  - The `password` parameter is passed directly to the subprocess call and never stored.
  - Never log the password; never write it to state files.
"""
import pathlib
import subprocess

# ── Constants ──────────────────────────────────────────────────────────────
WEBREPL_CLI = pathlib.Path(__file__).parent / "vendor" / "webrepl_cli.py"
OTA_SIZE_LIMIT = 200 * 1024         # 200KB hard limit (D-02)
WIFI_TIMEOUT_SECONDS = 30           # Claude's discretion: fast fail on unreachable board


# ── deploy_ota_wifi ────────────────────────────────────────────────────────

def deploy_ota_wifi(host: str, local_path: str, remote_path: str, password: str) -> dict:
    """Transfer a file to an ESP32 board over WiFi using WebREPL.

    Args:
        host:        Board's WiFi IP or hostname (e.g. "192.168.1.42" or "esp32.local").
                     Provided per-call; not stored anywhere (D-05).
        local_path:  Absolute path to the local file to upload.
        remote_path: Destination path on the board (e.g. "/main.py").
        password:    WebREPL password. Never stored; passed through to subprocess only (D-03).

    Returns error dicts on failure (never raises). On success (D-04):
        {"port": host, "files_written": [remote_path], "transport": "wifi"}

    On failure:
        {"error": "webrepl_cli_missing", "detail": ...}   — vendor script not found
        {"error": "ota_payload_too_large", "detail": ...} — file exceeds 200KB limit (D-02)
        {"error": "wifi_unreachable", "detail": ...,
         "fallback": "use deploy_file_to_board"}           — timeout or connection failure (D-07)
        {"error": "ota_failed", "detail": ...}            — other transfer failure
    """
    # Pre-check: webrepl_cli.py must be vendored (Pitfall 4)
    if not WEBREPL_CLI.exists():
        return {
            "error": "webrepl_cli_missing",
            "detail": (
                f"tools/vendor/webrepl_cli.py not found at {WEBREPL_CLI}. "
                "Vendor it from https://github.com/micropython/webrepl/blob/master/webrepl_cli.py"
            ),
        }

    local = pathlib.Path(local_path)

    # Size gate (D-02)
    file_size = local.stat().st_size
    if file_size > OTA_SIZE_LIMIT:
        return {
            "error": "ota_payload_too_large",
            "detail": f"File is {file_size} bytes; limit is {OTA_SIZE_LIMIT} bytes (200KB)",
        }

    # Invoke webrepl_cli.py: python3 webrepl_cli.py -p <password> <local> <host>:<remote>
    # IMPORTANT: always use timeout= to prevent indefinite hang (Pitfall 1)
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
            "detail": (
                f"WebREPL connection to {host} timed out after {WIFI_TIMEOUT_SECONDS}s"
            ),
            "fallback": "use deploy_file_to_board",
        }

    if result.returncode != 0:
        # Distinguish connection failure from other errors (Pitfall 2)
        # Check stderr for connection-related keywords
        stderr_lower = result.stderr.lower()
        if any(kw in stderr_lower for kw in ("connect", "refused", "timeout", "unreachable")):
            return {
                "error": "wifi_unreachable",
                "detail": result.stderr.strip() or f"WebREPL connection to {host} failed",
                "fallback": "use deploy_file_to_board",
            }
        return {
            "error": "ota_failed",
            "detail": result.stderr.strip() or result.stdout.strip() or "webrepl_cli.py exited non-zero",
        }

    return {
        "port": host,
        "files_written": [remote_path],
        "transport": "wifi",
    }
