"""ESP32 MicroPython Dev Station — MCP server entry point.

Runs on Raspberry Pi as a systemd daemon.
Transport: Streamable HTTP (not SSE — SSE is deprecated in Claude Code).
Endpoint: http://raspberrypi.local:8000/mcp

Registration on main machine:
    claude mcp add --transport http esp32-station http://raspberrypi.local:8000/mcp
"""
from mcp.server.fastmcp import FastMCP

from tools.board_detection import detect_chip, list_boards, load_board_state
from tools.file_deploy import deploy_file, deploy_directory
from tools.firmware_flash import flash_firmware
from tools.repl import exec_repl, read_serial, soft_reset, hard_reset
from tools.serial_lock import SerialLock

mcp = FastMCP("esp32-station", host="0.0.0.0", port=8000)


@mcp.tool()
def list_connected_boards() -> list[dict]:
    """List all ESP32 boards currently connected via USB.

    Returns a list of dicts with keys: port, description, vid, pid, serial_number, chip.
    The 'chip' value is the last-known chip type from state (or 'unknown' if never detected).
    Use identify_chip(port) to probe a board and update its chip type.
    """
    return list_boards()


@mcp.tool()
def identify_chip(port: str) -> dict:
    """Detect the ESP32 chip variant at the given serial port.

    Runs esptool chip_id as a subprocess. Updates board state on success.
    Returns {"port": port, "chip": chip_name} on success.
    Returns {"error": "chip_id_failed"|"chip_not_parsed", "detail": ...} on failure.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
    """
    return detect_chip(port)


@mcp.tool()
def flash_micropython(port: str, chip: str | None = None) -> dict:
    """Flash MicroPython firmware onto the board at the given serial port.

    Automatically selects the correct firmware for the chip variant.
    Firmware is cached locally (7-day TTL); network not required if cache is fresh.

    Pre-flight: runs chip detection if chip is not provided.
    Fails fast with a structured error if chip cannot be identified.

    Returns {"port": port, "chip": chip, "firmware": path} on success.
    Returns {"error": error_code, "detail": ...} on failure.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
        chip: Optional chip variant override (e.g. "ESP32-S3"). Auto-detected if None.
    """
    return flash_firmware(port, chip=chip)


@mcp.tool()
def get_board_state() -> dict:
    """Return the persisted board state from ~/.esp32-station/boards.json.

    Contains last-known chip type and detection timestamp for all previously-detected boards.
    Survives MCP server restarts (BOARD-04).

    Returns: dict keyed by port, e.g. {"/dev/ttyUSB0": {"chip": "ESP32-S3", "detected_at": 1700000000.0}}
    """
    return load_board_state()


@mcp.tool()
def deploy_file_to_board(port: str, local_path: str, remote_path: str | None = None) -> dict:
    """Deploy a single file to a connected ESP32 board via USB.

    Checks filesystem space before transfer (warns at 70%, fails at 90%).
    Verifies file integrity (size) after transfer.
    Serializes access to the port — safe to call concurrently for different ports.

    Returns {"port": port, "files_written": [remote_path]} on success.
    Returns {"error": error_code, "detail": ...} on failure.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
        local_path: Absolute or relative path to local file to deploy
        remote_path: Destination path on board (default: filename only at board root)
    """
    try:
        with SerialLock(port):
            return deploy_file(port, local_path, remote_path)
    except TimeoutError as e:
        return {"error": "serial_lock_timeout", "detail": str(e)}


@mcp.tool()
def deploy_directory_to_board(port: str, local_dir: str) -> dict:
    """Deploy a full project directory to a connected ESP32 board via USB.

    Excludes: __pycache__/, *.pyc, .git/, tests/, .planning/
    Deploys: .py files and non-Python resources (.json, .txt, etc.)
    Checks filesystem space before transfer; verifies integrity after each file.

    Returns {"port": port, "files_written": [...]} on success.
    Returns {"error": error_code, "detail": ...} on failure.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
        local_dir: Path to local project directory
    """
    try:
        with SerialLock(port):
            return deploy_directory(port, local_dir)
    except TimeoutError as e:
        return {"error": "serial_lock_timeout", "detail": str(e)}


@mcp.tool()
def exec_repl_command(port: str, command: str, timeout: int = 10) -> dict:
    """Execute a MicroPython expression or statement on a board and capture output.

    Single-command execution model — one expression or statement per call.
    Times out cleanly after specified timeout (no hanging calls).

    Returns {"port": port, "output": "..."} on success.
    Returns {"error": "repl_timeout"|"repl_failed", "detail": ...} on failure.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
        command: MicroPython expression, e.g. "print(2 + 2)" or "import uos; print(uos.listdir())"
        timeout: Seconds before giving up (default: 10)
    """
    try:
        with SerialLock(port):
            return exec_repl(port, command, timeout=timeout)
    except TimeoutError as e:
        return {"error": "serial_lock_timeout", "detail": str(e)}


@mcp.tool()
def read_board_serial(port: str) -> dict:
    """Read recent serial output from a connected ESP32 board.

    Captures buffered output without blocking indefinitely.

    Returns {"port": port, "output": "..."} on success.
    Returns {"error": error_code, "detail": ...} on failure.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
    """
    try:
        with SerialLock(port):
            return read_serial(port)
    except TimeoutError as e:
        return {"error": "serial_lock_timeout", "detail": str(e)}


@mcp.tool()
def reset_board(port: str, reset_type: str = "soft") -> dict:
    """Reset a connected ESP32 board via USB.

    soft reset: equivalent to Ctrl-D in REPL (restarts MicroPython, keeps filesystem)
    hard reset: equivalent to pressing RST button (full chip restart via machine.reset())

    Returns {"port": port, "reset": "soft"|"hard"} on success.
    Returns {"error": error_code, "detail": ...} on failure.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
        reset_type: "soft" (default) or "hard"
    """
    if reset_type not in ("soft", "hard"):
        return {"error": "invalid_reset_type", "detail": f"reset_type must be 'soft' or 'hard', got {reset_type!r}"}
    try:
        with SerialLock(port):
            if reset_type == "soft":
                return soft_reset(port)
            return hard_reset(port)
    except TimeoutError as e:
        return {"error": "serial_lock_timeout", "detail": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
