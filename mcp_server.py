"""ESP32 MicroPython Dev Station — MCP server entry point.

Runs on Raspberry Pi as a systemd daemon.
Transport: Streamable HTTP (not SSE — SSE is deprecated in Claude Code).
Endpoint: http://raspberrypi.local:8000/mcp

Registration on main machine:
    claude mcp add --transport http esp32-station http://raspberrypi.local:8000/mcp
"""
import pathlib

from mcp.server.fastmcp import FastMCP

from tools.board_detection import detect_chip, list_boards, load_board_state, save_board_state
from tools.file_deploy import deploy_file, deploy_directory
from tools.firmware_flash import flash_firmware
from tools.repl import exec_repl, read_serial, soft_reset, hard_reset
from tools.serial_lock import SerialLock
from tools.ota_wifi import deploy_ota_wifi as _deploy_ota_wifi
from tools.github_deploy import pull_and_deploy_github as _pull_and_deploy_github
from tools.board_status import get_status as _get_status, check_health as _check_health
from tools.mdns_discovery import discover_boards as _discover_boards
from tools.boot_deploy import deploy_boot_config as _deploy_boot_config

TOPOLOGY = """
IMPORTANT — understand this topology before using any tool:

- THIS SERVER runs on a Raspberry Pi (the "Pi"), not on the user's main machine.
- All tool calls execute ON THE PI. File paths, serial ports, and subprocesses are all Pi-side.
- ESP32 boards connect via USB to the PI — not to the user's machine.
- The user runs Claude Code on their MAIN MACHINE and talks to this server over the LAN.
- "local_path" in any tool always means a path on the Pi's filesystem.
- To write a file and deploy it: use write_temp_file to write it to the Pi first,
  then pass the returned path to deploy_file_to_board or deploy_ota_wifi.
- Never assume a file exists on the Pi just because the user mentions it — create it first.
- WiFi credentials are stored on the Pi at /etc/esp32-station/wifi.json and are never
  passed as tool parameters.
"""

mcp = FastMCP("esp32-station", host="0.0.0.0", port=8000, instructions=TOPOLOGY)


@mcp.tool()
def list_connected_boards() -> list[dict]:
    """List all ESP32 boards currently connected via USB.

    Returns cached chip type from previous identify_chip calls. Always call
    identify_chip(port) automatically for any board where chip is "unknown" —
    do not ask the user, just do it.

    Returns a list of dicts with keys: port, description, vid, pid, serial_number, chip.
    """
    return list_boards()


@mcp.tool()
def identify_chip(port: str) -> dict:
    """Detect the ESP32 chip variant at the given serial port.

    Runs esptool chip-id as a subprocess. Updates board state on success.
    Returns {"port": port, "chip": chip_name} on success.
    Returns {"error": "chip_id_failed"|"chip_not_parsed", "detail": ...} on failure.

    If this fails for a board on /dev/ttyACM0 (native USB, VID 0x303a):
    The board needs to be in bootloader mode for esptool to connect.
    Tell the user to hold the BOOT button and press RESET (or power cycle while
    holding BOOT), then retry identify_chip immediately.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0" or "/dev/ttyACM0"
    """
    return detect_chip(port)


@mcp.tool()
def flash_micropython(port: str, chip: str | None = None) -> dict:
    """Flash MicroPython firmware onto the board at the given serial port.

    IMPORTANT: Always performs a full erase before writing firmware.

    BOOT BUTTON GUIDANCE — follow this sequence with the user:
    1. Before calling this tool: tell the user to hold the BOOT button (labelled
       "BOOT" or "FLASH") and keep holding it. Do not call the tool until they confirm
       they are holding it.
    2. Call the tool.
    3. On success: tell the user they can release the BOOT button.
    4. On erase_failed error: tell the user to release the BOOT button, then re-hold it,
       then retry. Check saved_flash_notes in the result for any board-specific process
       that was recorded previously.
    5. On repeated failure: search the web for "[chip] ESP32 enter bootloader mode" or
       "[board description] flashing mode". Try the alternative process with the user.
       Once you find what works, call save_board_flash_notes to record it for next time.

    POST-FLASH: After a successful flash, always:
    1. Ask the user: "What would you like to call this board?" (e.g. "desk", "kitchen", "sensor1")
    2. Build the hostname as: {name}-esp32-{id} where {id} is the first 6 characters of
       the board's serial number from list_connected_boards (e.g. "desk-esp32-983dae")
    3. Call deploy_boot_config with that hostname — do not skip this step.

    Firmware is cached locally (7-day TTL); network not required if cache is fresh.
    Pre-flight chip detection runs automatically if chip is not provided.

    Returns {"port": port, "chip": chip, "firmware": path} on success.
    Returns {"error": error_code, "chip": chip, "detail": ..., "saved_flash_notes": ...} on failure.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
        chip: Optional chip variant override (e.g. "ESP32-S3"). Auto-detected if None.
    """
    result = flash_firmware(port, chip=chip)
    if result.get("error") == "erase_failed":
        # Include any previously saved board-specific notes so Claude can try them
        state = load_board_state()
        chip_key = result.get("chip", "")
        result["saved_flash_notes"] = state.get(f"flash_notes:{chip_key}", None)
        result["user_action"] = (
            "Tell the user to release the BOOT button, then re-hold it and retry. "
            "If this fails again, search for the correct bootloader process for this "
            "chip/board and try the alternative. Call save_board_flash_notes once you "
            "find what works."
        )
    return result


@mcp.tool()
def save_board_flash_notes(chip: str, notes: str) -> dict:
    """Save board-specific flash/bootloader notes for a chip variant.

    Call this after confirming a flashing process works for a particular board,
    especially when the standard BOOT-button process did not work first time.
    Notes are stored by chip type and returned in future flash failures so Claude
    can try the known-good process immediately.

    Args:
        chip: Chip variant, e.g. "ESP32", "ESP32-S3". Use the value from list_connected_boards.
        notes: Plain-text description of the working bootloader process for this board.
    """
    state = load_board_state()
    state[f"flash_notes:{chip}"] = notes
    save_board_state(state)
    return {"saved": True, "chip": chip}


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
    Automatically hard-resets the board after a successful deploy.
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
            result = deploy_file(port, local_path, remote_path)
            if "error" not in result:
                hard_reset(port)
            return result
    except TimeoutError as e:
        return {"error": "serial_lock_timeout", "detail": str(e)}


@mcp.tool()
def deploy_directory_to_board(port: str, local_dir: str) -> dict:
    """Deploy a full project directory to a connected ESP32 board via USB.

    Excludes: __pycache__/, *.pyc, .git/, tests/, .planning/
    Deploys: .py files and non-Python resources (.json, .txt, etc.)
    Checks filesystem space before transfer; verifies integrity after each file.
    Automatically hard-resets the board after a successful deploy.

    Returns {"port": port, "files_written": [...]} on success.
    Returns {"error": error_code, "detail": ...} on failure.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
        local_dir: Path to local project directory
    """
    try:
        with SerialLock(port):
            result = deploy_directory(port, local_dir)
            if "error" not in result:
                hard_reset(port)
            return result
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


@mcp.tool()
def deploy_ota_wifi(host: str, local_path: str, remote_path: str) -> dict:
    """Deploy a file to an ESP32 board over WiFi using WebREPL.

    Reads the WebREPL password from /etc/esp32-station/wifi.json automatically —
    never ask the user for the password.

    Transfers a single file from the Pi to the board using the webrepl_cli.py script.
    The board must have boot.py deployed via deploy_boot_config (WebREPL enabled).

    After a successful deploy, tell the user to reset the board to run the new code
    (press the RST button or power cycle). Cannot reset automatically over WiFi.

    No SerialLock applied — this is a WiFi operation with no serial port.
    If WiFi is unavailable, use deploy_file_to_board() instead (USB fallback).

    Returns {"port": host, "files_written": [remote_path], "transport": "wifi"} on success.
    Returns {"error": "wifi_unreachable", "detail": ..., "fallback": "use deploy_file_to_board"}
             when the board cannot be reached over WiFi.
    Returns {"error": error_code, "detail": ...} on other failures.

    Args:
        host:        Board's WiFi IP address or hostname, e.g. "192.168.1.42" or "s3-esp32-983dae.local"
        local_path:  Absolute path to local file to upload (max 200KB)
        remote_path: Destination path on board, e.g. "/main.py"
    """
    return _deploy_ota_wifi(host, local_path, remote_path)


@mcp.tool()
def pull_and_deploy_github(
    port: str, repo_url: str, branch: str = "main", token: str | None = None
) -> dict:
    """Pull the latest code from a GitHub repository and deploy it to a board via USB.

    Clones the repository (shallow, --depth 1) into a temporary directory on the Pi,
    then deploys the contents using deploy_directory() — the same pipeline as
    deploy_directory_to_board() including space checks, exclusions, and integrity checks.
    Automatically hard-resets the board after a successful deploy.

    Uses SerialLock to serialize USB access — safe to call concurrently for different ports.

    Returns {"port": port, "files_written": [...]} on success.
    Returns {"error": error_code, "detail": ...} on failure.

    Args:
        port:     Serial port path, e.g. "/dev/ttyUSB0"
        repo_url: GitHub repository URL, e.g. "https://github.com/user/esp32-project"
        branch:   Branch to deploy (default: "main")
        token:    Optional personal access token for private repos (never stored by this tool)
    """
    try:
        with SerialLock(port):
            result = _pull_and_deploy_github(port, repo_url, branch, token)
            if "error" not in result:
                hard_reset(port)
            return result
    except TimeoutError as e:
        return {"error": "serial_lock_timeout", "detail": str(e)}


@mcp.tool()
def get_board_status(port: str | None = None, host: str | None = None, password: str | None = None) -> dict:
    """Get firmware version, WiFi status, IP, free memory/storage from an ESP32 board.

    Provide port for USB or host+password for WiFi. Exactly one transport required.
    """
    if port is not None:
        try:
            with SerialLock(port):
                return _get_status(port=port)
        except TimeoutError as e:
            return {"error": "serial_lock_timeout", "detail": str(e)}
    return _get_status(host=host, password=password)


@mcp.tool()
def check_board_health(port: str | None = None, host: str | None = None, password: str | None = None) -> dict:
    """Check if a board is alive and running MicroPython.

    Returns status: 'healthy', 'unresponsive', or 'not_found'.
    Provide port for USB or host+password for WiFi.
    """
    if port is not None:
        try:
            with SerialLock(port):
                return _check_health(port=port)
        except TimeoutError as e:
            return {"error": "serial_lock_timeout", "detail": str(e)}
    return _check_health(host=host, password=password)


@mcp.tool()
def discover_boards(timeout: int = 3) -> list[dict] | dict:
    """Discover MicroPython boards on the LAN by resolving known hostnames.

    Resolves hostnames saved by deploy_boot_config as hostname.local using the
    system resolver. Returns list of {hostname, ip, port} for each board found.
    Empty list if no boards have been provisioned or none are reachable.
    """
    return _discover_boards(timeout=timeout)


@mcp.tool()
def deploy_boot_config(port: str, hostname: str | None = None) -> dict:
    """Deploy WiFi + WebREPL + hostname configuration as boot.py to an ESP32 board.

    Reads WiFi credentials from the Pi-local file (/etc/esp32-station/wifi.json).
    Credentials never appear in MCP tool calls -- they are injected server-side.

    This is a standalone provisioning step. Chain with flash_micropython (before)
    and check_board_health (after) for full provisioning. Five readiness levels:
      1. Flash only: flash_micropython
      2. Flash + WiFi: flash_micropython -> deploy_boot_config
      3. Full (WiFi): flash_micropython -> deploy_boot_config -> deploy_file_to_board
      4. WiFi config only: deploy_boot_config (board already flashed)
      5. Full (USB only): flash_micropython -> deploy_file_to_board (no WiFi)

    Always verify with check_board_health() after provisioning.

    Args:
        port: Serial port path, e.g. "/dev/ttyUSB0"
        hostname: Board hostname for mDNS discovery (default: "esp32").
                  Sets network.hostname() so board is reachable at hostname.local.
                  Ask the user for a name in the format: {name}-esp32-{id}
                  (e.g. "kitchen-esp32-a1b2"). The unique ID helps distinguish
                  multiple boards of the same type on the network.
    """
    try:
        with SerialLock(port):
            return _deploy_boot_config(port, hostname=hostname)
    except TimeoutError as e:
        return {"error": "serial_lock_timeout", "detail": str(e)}


STAGING_DIR = pathlib.Path.home() / ".esp32-station" / "staging"


@mcp.tool()
def write_temp_file(filename: str, content: str) -> dict:
    """Write content to a temporary file on the Pi for deployment to a board.

    Use this whenever you need to write code or config that will be deployed
    via deploy_file_to_board or deploy_ota_wifi. The file is written to a
    staging directory on the Pi and the Pi-side path is returned.

    Args:
        filename: Filename only, e.g. "main.py" or "config.json"
        content:  Full file content as a string

    Returns:
        {"path": "/home/esp32/.esp32-station/staging/main.py"} on success.
        {"error": "write_failed", "detail": ...} on failure.
    """
    try:
        STAGING_DIR.mkdir(parents=True, exist_ok=True)
        dest = STAGING_DIR / pathlib.Path(filename).name
        dest.write_text(content)
        return {"path": str(dest)}
    except Exception as e:
        return {"error": "write_failed", "detail": str(e)}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
