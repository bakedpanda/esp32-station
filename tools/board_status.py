"""Board status collection and health check logic with dual USB/WiFi transport.

Requirements covered: STAT-01 (board status), STAT-02 (health check).

Provides:
  get_status(port=...|host=...) — collect firmware, WiFi, memory, storage info
  check_health(port=...|host=...) — quick healthy/unresponsive/not_found probe
"""
import json

from tools.repl import exec_repl
from tools.webrepl_cmd import webrepl_exec
from serial.tools.list_ports import comports

# ── Constants ────────────────────────────────────────────────────────────

STATUS_SCRIPT = """\
import sys, gc, json
try:
    import os
except ImportError:
    import uos as os
wifi_connected = False
ip_address = ""
board = sys.platform
try:
    import network
    wlan = network.WLAN(network.STA_IF)
    wifi_connected = wlan.isconnected()
    if wifi_connected:
        ip_address = wlan.ifconfig()[0]
    try:
        board = wlan.config('dhcp_hostname')
    except Exception:
        pass
except Exception:
    pass
gc.collect()
free_memory = gc.mem_free()
stat = os.statvfs('/')
free_storage = stat[0] * stat[3]
firmware = '.'.join(str(x) for x in sys.version_info[:3])
print(json.dumps({"firmware": firmware, "wifi_connected": wifi_connected, "ip_address": ip_address, "free_memory": free_memory, "free_storage": free_storage, "board": board}))
"""

HEALTH_PING = "print(1)"
HEALTH_TIMEOUT = 5


# ── Parameter validation ─────────────────────────────────────────────────

def _validate_transport(port, host):
    """Validate that exactly one of port/host is provided.

    Returns None if valid, or an error dict if invalid.
    """
    if port and host:
        return {"error": "invalid_params", "detail": "Provide either port or host, not both"}
    if not port and not host:
        return {"error": "invalid_params", "detail": "Provide either port or host"}
    return None


# ── Public API ───────────────────────────────────────────────────────────

def get_status(port=None, host=None, password=None) -> dict:
    """Collect board status (firmware, WiFi, memory, storage) via USB or WiFi.

    Args:
        port:     Serial port for USB path (e.g. "/dev/ttyUSB0").
        host:     Board's WiFi IP/hostname for WiFi path.
        password: WebREPL password (required for WiFi path).

    Returns status dict with keys: firmware, wifi_connected, ip_address,
    free_memory, free_storage, board, transport.

    Returns error dict on failure (never raises).
    """
    err = _validate_transport(port, host)
    if err:
        return err

    if port:
        result = exec_repl(port, STATUS_SCRIPT, timeout=10)
        transport = "usb"
    else:
        if not password:
            return {"error": "invalid_params", "detail": "password required for WiFi status"}
        result = webrepl_exec(host, password, STATUS_SCRIPT, timeout=15)
        transport = "wifi"

    if "error" in result:
        return result

    try:
        data = json.loads(result["output"])
        data["transport"] = transport
        return data
    except (json.JSONDecodeError, KeyError):
        return {
            "error": "status_parse_failed",
            "detail": f"Could not parse board output: {result.get('output', '')}",
        }


def check_health(port=None, host=None, password=None) -> dict:
    """Quick health probe: healthy, unresponsive, or not_found.

    Args:
        port:     Serial port for USB path.
        host:     Board's WiFi IP/hostname for WiFi path.
        password: WebREPL password (required for WiFi path).

    Returns:
        {"status": "healthy"} — board responded to ping.
        {"status": "unresponsive", "detail": "..."} — board exists but timed out.
        {"status": "not_found", "detail": "..."} — board not detected / unreachable.

    Never raises to callers.
    """
    err = _validate_transport(port, host)
    if err:
        return err

    if port:
        # Check if port exists in system before trying REPL
        known_ports = [p.device for p in comports()]
        if port not in known_ports:
            return {"status": "not_found", "detail": f"No device at {port}"}
        result = exec_repl(port, HEALTH_PING, timeout=HEALTH_TIMEOUT)
    else:
        if not password:
            return {"error": "invalid_params", "detail": "password required for WiFi health check"}
        result = webrepl_exec(host, password, HEALTH_PING, timeout=HEALTH_TIMEOUT)

    if "error" in result:
        if "timeout" in result["error"]:
            return {"status": "unresponsive", "detail": result["detail"]}
        return {"status": "not_found", "detail": result["detail"]}

    return {"status": "healthy"}
