"""Firmware download, caching (7-day TTL), and flashing via esptool.

Requirements covered: FLASH-01, FLASH-02, FLASH-03, FLASH-04, FLASH-05.
"""
import os
import pathlib
import subprocess
import sys
import time

import requests

from tools.board_detection import detect_chip

# ── Constants ──────────────────────────────────────────────────────────────
# CRITICAL: v5 command is "esptool", NOT "esptool.py"
# Use venv-relative path so the correct esptool is found when running under systemd
ESPTOOL_CMD = os.path.join(os.path.dirname(sys.executable), "esptool")
FLASH_BAUD = 460800      # Higher baud for actual flashing (faster transfer)
DETECT_BAUD = 115200     # Standard baud for chip_id detection

FIRMWARE_DIR = pathlib.Path.home() / ".esp32-station" / "firmware"
FIRMWARE_TTL_SECONDS = 7 * 24 * 3600  # 7 days

# Hardcoded URLs for MicroPython v1.27.0 (reliable for offline scenarios).
# Update these when a new MicroPython release is needed.
FIRMWARE_URLS: dict[str, str] = {
    "ESP32":    "https://micropython.org/resources/firmware/ESP32_GENERIC-20251209-v1.27.0.bin",
    "ESP32-S2": "https://micropython.org/resources/firmware/ESP32_GENERIC_S2-20251209-v1.27.0.bin",
    "ESP32-S3": "https://micropython.org/resources/firmware/ESP32_GENERIC_S3-20251209-v1.27.0.bin",
    "ESP32-C3": "https://micropython.org/resources/firmware/ESP32_GENERIC_C3-20251209-v1.27.0.bin",
    "ESP32-C6": "https://micropython.org/resources/firmware/ESP32_GENERIC_C6-20251209-v1.27.0.bin",
}

# Write offsets differ between classic ESP32 and newer variants
WRITE_OFFSETS: dict[str, str] = {
    "ESP32": "0x1000",     # Classic ESP32 requires 0x1000 offset
}
DEFAULT_WRITE_OFFSET = "0x0"   # All other variants (S2, S3, C3, C6)


# ── Firmware cache ─────────────────────────────────────────────────────────

def get_firmware_path(chip: str) -> pathlib.Path:
    """Return local path to the firmware .bin for chip, downloading if stale or absent.

    Uses 7-day TTL: re-downloads if cached file is older than FIRMWARE_TTL_SECONDS.
    If download fails but stale file exists, returns stale file (prefer offline operation).

    Raises ValueError for unknown chip variants (not in FIRMWARE_URLS).
    """
    if chip not in FIRMWARE_URLS:
        raise ValueError(f"unsupported_chip: {chip!r}. Supported: {list(FIRMWARE_URLS)}")

    FIRMWARE_DIR.mkdir(parents=True, exist_ok=True)
    fw_path = FIRMWARE_DIR / f"{chip.replace('-', '_')}.bin"

    # Check freshness
    is_fresh = (
        fw_path.exists()
        and (time.time() - fw_path.stat().st_mtime) < FIRMWARE_TTL_SECONDS
    )
    if is_fresh:
        return fw_path

    # Download (or re-download if stale)
    url = FIRMWARE_URLS[chip]
    try:
        resp = requests.get(url, timeout=60, stream=True)
        resp.raise_for_status()
        fw_path.write_bytes(resp.content)
    except Exception:
        if fw_path.exists():
            # Use stale cache rather than fail — supports offline flashing
            return fw_path
        raise  # No cache at all: propagate

    return fw_path


# ── Flash orchestration ────────────────────────────────────────────────────

def flash_firmware(port: str, chip: str | None = None) -> dict:
    """Flash MicroPython firmware onto the board at the given serial port.

    Steps:
    1. Pre-flight: detect chip if chip=None (FLASH-05). Fail fast on error (FLASH-04).
    2. Validate chip is in FIRMWARE_URLS.
    3. Fetch/use cached firmware (FLASH-03).
    4. esptool erase_flash (clears old firmware).
    5. esptool write_flash at correct offset (FLASH-01, FLASH-02).

    Returns dict with "port" and "chip" on success, or "error" key on failure.
    """
    # Step 1: Pre-flight chip detection
    if chip is None:
        detection = detect_chip(port)
        if "error" in detection:
            return {"error": "preflight_failed", "detail": detection}
        chip = detection["chip"]

    # Step 2: Validate chip variant
    if chip not in FIRMWARE_URLS:
        return {
            "error": "unsupported_chip",
            "chip": chip,
            "supported": list(FIRMWARE_URLS),
        }

    # Step 3: Ensure firmware is cached locally
    try:
        fw_path = get_firmware_path(chip)
    except Exception as exc:
        return {"error": "firmware_download_failed", "detail": str(exc)}

    # Step 4: Erase flash
    erase = subprocess.run(
        [ESPTOOL_CMD, "--chip", chip, "--port", port, "--baud", str(DETECT_BAUD), "erase_flash"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if erase.returncode != 0:
        return {"error": "erase_failed", "detail": erase.stderr.strip()}

    # Step 5: Write firmware
    write_offset = WRITE_OFFSETS.get(chip, DEFAULT_WRITE_OFFSET)
    write = subprocess.run(
        [ESPTOOL_CMD, "--chip", chip, "--port", port, "--baud", str(FLASH_BAUD),
         "write_flash", write_offset, str(fw_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if write.returncode != 0:
        return {"error": "flash_failed", "detail": write.stderr.strip()}

    return {"port": port, "chip": chip, "firmware": str(fw_path)}
