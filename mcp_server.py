"""ESP32 MicroPython Dev Station — MCP server entry point.

Runs on Raspberry Pi as a systemd daemon.
Transport: Streamable HTTP (not SSE — SSE is deprecated in Claude Code).
Endpoint: http://raspberrypi.local:8000/mcp

Registration on main machine:
    claude mcp add --transport http esp32-station http://raspberrypi.local:8000/mcp
"""
from mcp.server.fastmcp import FastMCP

from tools.board_detection import detect_chip, list_boards, load_board_state
from tools.firmware_flash import flash_firmware

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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
