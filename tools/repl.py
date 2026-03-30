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
    """Capture serial output from the board using direct pyserial reads.

    Opens the port without entering raw REPL mode so the board keeps running.
    On USB CDC (ttyACM) devices the board only sends data while the port is
    open, so this function holds the connection open and collects output until
    either `timeout` seconds elapse or 500 ms of silence follows the last byte.

    On success: returns {"port": port, "output": <decoded string>}.
    On failure: returns {"error": "read_failed", "detail": <message>}.

    Never raises to callers.
    """
    try:
        ser = serial.Serial(port, baudrate=115200, timeout=0.1,
                            rtscts=False)

        deadline = time.monotonic() + timeout
        buf = bytearray()
        last_rx = time.monotonic()

        while time.monotonic() < deadline:
            n = ser.in_waiting
            if n:
                buf.extend(ser.read(n))
                last_rx = time.monotonic()
            elif buf and (time.monotonic() - last_rx) > 0.5:
                # Received data then 500 ms of silence — done
                break
            else:
                time.sleep(0.05)

        ser.close()
        return {"port": port, "output": buf.decode("utf-8", errors="replace")}
    except serial.SerialException as exc:
        return {"error": "read_failed", "detail": str(exc)}
    except Exception as exc:
        return {"error": "read_failed", "detail": str(exc)}


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
