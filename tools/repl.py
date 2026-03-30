"""REPL command execution and board reset via mpremote subprocess and pyserial.

Requirements covered: REPL-01, REPL-02, REPL-03, BOARD-03, REL-01, REL-02.
"""
import os
import subprocess
import sys
import time

import serial

# ── Constants ──────────────────────────────────────────────────────────────
MPREMOTE_CMD = os.path.join(os.path.dirname(sys.executable), "mpremote")
REPL_TIMEOUT_SECONDS = 10   # default; configurable via parameter
READ_SERIAL_TIMEOUT = 5     # shorter timeout for passive read


# ── REPL execution ─────────────────────────────────────────────────────────

def exec_repl(port: str, command: str, timeout: int = REPL_TIMEOUT_SECONDS) -> dict:
    """Execute a MicroPython expression on the board via mpremote exec.

    On success: returns {"port": port, "output": <stripped stdout>}.
    On timeout: returns {"error": "repl_timeout", "detail": "command timed out after Ns"}.
    On failure: returns {"error": "repl_failed", "detail": <stderr or stdout>}.

    Never raises to callers.
    """
    try:
        result = subprocess.run(
            [MPREMOTE_CMD, "connect", port, "exec", command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"error": "repl_timeout", "detail": f"command timed out after {timeout}s"}

    if result.returncode != 0:
        return {"error": "repl_failed", "detail": result.stderr.strip() or result.stdout.strip()}

    return {"port": port, "output": result.stdout.strip()}


# ── Serial read ────────────────────────────────────────────────────────────

def read_serial(port: str, timeout: int = READ_SERIAL_TIMEOUT) -> dict:
    """Capture recent serial output from the board via mpremote.

    Uses mpremote exec with an empty command to capture any buffered output
    without sending a real command to the board.

    On success: returns {"port": port, "output": <stdout>} (newlines preserved).
    On timeout: returns {"error": "read_timeout", "detail": "serial read timed out after Ns"}.
    On failure: returns {"error": "read_failed", "detail": <stderr>}.

    Never raises to callers.
    """
    try:
        result = subprocess.run(
            [MPREMOTE_CMD, "connect", port, "exec", ""],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"error": "read_timeout", "detail": f"serial read timed out after {timeout}s"}

    if result.returncode != 0:
        return {"error": "read_failed", "detail": result.stderr.strip()}

    return {"port": port, "output": result.stdout}


# ── Board reset ────────────────────────────────────────────────────────────

def soft_reset(port: str) -> dict:
    """Perform a MicroPython soft reset (equivalent to Ctrl-D at the REPL).

    Soft reset reboots MicroPython but keeps USB connection alive.
    The subprocess may exit non-zero because the board resets mid-execution;
    non-zero exit with empty stderr is treated as success.

    On success: returns {"port": port, "reset": "soft"}.
    On failure (non-zero with stderr): returns {"error": "soft_reset_failed", "detail": ...}.

    Never raises to callers.
    """
    try:
        result = subprocess.run(
            [MPREMOTE_CMD, "connect", port, "exec", "import machine; machine.soft_reset()"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {"error": "soft_reset_failed", "detail": "soft reset timed out after 10s"}

    # Board disconnects after reset — non-zero exit is expected; treat empty stderr as success
    if result.returncode != 0 and result.stderr.strip():
        return {"error": "soft_reset_failed", "detail": result.stderr.strip()}

    return {"port": port, "reset": "soft"}


def hard_reset(port: str) -> dict:
    """Perform a hardware reset via DTR/RTS signal (equivalent to pressing RST button).

    Opens the serial port with pyserial, pulses RTS to toggle the EN pin,
    causing the ESP32 to reset. This works regardless of MicroPython state.

    On success: returns {"port": port, "reset": "hard"}.
    On failure: returns {"error": "hard_reset_failed", "detail": ...,
                         "fallback": "Unplug the board from USB, wait 3 seconds, then plug it back in"}.

    Never raises to callers.
    """
    try:
        ser = serial.Serial(port, baudrate=115200)
        ser.setRTS(True)    # EN -> LOW (hold chip in reset)
        time.sleep(0.1)     # 100ms hold
        ser.setRTS(False)   # EN -> HIGH (chip starts booting)
        time.sleep(0.05)    # 50ms settle
        ser.close()
        return {"port": port, "reset": "hard"}
    except Exception as exc:
        return {
            "error": "hard_reset_failed",
            "detail": str(exc),
            "fallback": "Unplug the board from USB, wait 3 seconds, then plug it back in",
        }
