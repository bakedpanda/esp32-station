"""Board detection: USB enumeration, chip identification, state persistence.

Requirements covered: BOARD-01, BOARD-02, BOARD-04, FLASH-04 (fail fast), FLASH-05 (pre-flight).
"""
import json
import os
import pathlib
import subprocess
import sys
import time

import serial.tools.list_ports

# ── Constants ──────────────────────────────────────────────────────────────
# CRITICAL: v5 command is "esptool", NOT "esptool.py"
# Use venv-relative path so the correct esptool is found when running under systemd
ESPTOOL_CMD = os.path.join(os.path.dirname(sys.executable), "esptool")
BAUD = 115200

# Known USB VID/PID vendor IDs for ESP32-compatible USB-UART bridges:
# 0x1A86 = CH340 (common cheap Chinese boards)
# 0x10C4 = CP2102 (Silabs; many Adafruit/SparkFun boards)
# 0x0403 = FTDI FT232
# 0x239A = Adafruit
# 0x303A = Espressif native USB (S2/S3/C3/C6 with built-in USB)
ESP32_VIDS = {0x1A86, 0x10C4, 0x0403, 0x239A, 0x303A}

STATE_DIR = pathlib.Path.home() / ".esp32-station"
BOARDS_JSON = STATE_DIR / "boards.json"


# ── State persistence ───────────────────────────────────────────────────────

def load_board_state() -> dict:
    """Load boards.json from STATE_DIR. Creates directory if needed. Returns {} if file absent."""
    STATE_DIR.mkdir(exist_ok=True)
    if BOARDS_JSON.exists():
        try:
            return json.loads(BOARDS_JSON.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_board_state(state: dict) -> None:
    """Persist state dict to boards.json (pretty-printed JSON)."""
    STATE_DIR.mkdir(exist_ok=True)
    BOARDS_JSON.write_text(json.dumps(state, indent=2))


# ── Board enumeration ───────────────────────────────────────────────────────

def list_boards() -> list[dict]:
    """List all ESP32 boards currently connected via USB.

    Filters serial ports by known ESP32-compatible USB VIDs.
    Returns last-known chip type from boards.json cache (does not probe hardware).

    Returns: list of dicts with keys: port, description, vid, pid, serial_number, chip.
    """
    state = load_board_state()
    boards = []
    for port in serial.tools.list_ports.comports():
        if port.vid in ESP32_VIDS:
            key = port.device
            boards.append({
                "port": port.device,
                "description": port.description,
                "vid": hex(port.vid),
                "pid": hex(port.pid) if port.pid else None,
                "serial_number": port.serial_number,
                "chip": state.get(key, {}).get("chip", "unknown"),
            })
    return boards


# ── Chip detection ─────────────────────────────────────────────────────────

def detect_chip(port: str) -> dict:
    """Run esptool chip_id on the given port and return parsed chip information.

    On success: persists result to boards.json and returns {"port": port, "chip": chip_name}.
    On failure: returns {"error": "chip_id_failed"|"chip_not_parsed", "detail": ...}.

    Note: Returns error dict rather than raising so callers can treat chip detection
    as a pre-flight check (FLASH-05) without try/except at every call site.
    """
    try:
        result = subprocess.run(
            [ESPTOOL_CMD, "--chip", "auto", "--port", port, "--baud", str(BAUD), "chip-id"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"error": "chip_id_failed", "detail": "esptool timed out after 30s"}
    except FileNotFoundError:
        return {"error": "chip_id_failed", "detail": f"'{ESPTOOL_CMD}' not found — is esptool v5 installed in the venv?"}

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "esptool exited with no output"
        return {"error": "chip_id_failed", "detail": detail}

    # Parse chip type from esptool output.
    # v5 format: "Chip type:          ESP32-D0WD (revision v1.0)"
    # older format: "Chip is ESP32-S3 (revision v0.1)"
    chip = None
    for line in result.stdout.splitlines():
        if "Chip type:" in line:
            chip = line.split("Chip type:")[1].split("(")[0].strip()
            break
        if "Chip is" in line:
            chip = line.split("Chip is")[1].split("(")[0].strip()
            break

    if chip is None:
        return {"error": "chip_not_parsed", "detail": result.stdout}

    # Persist to boards.json (BOARD-04)
    state = load_board_state()
    state[port] = {"chip": chip, "detected_at": time.time()}
    save_board_state(state)

    return {"port": port, "chip": chip}
