"""File deployment to ESP32 boards via mpremote subprocess.

Requirements covered: DEPLOY-01, DEPLOY-02, DEPLOY-03, DEPLOY-04.

Provides:
  deploy_file()      — copy a single .py (or any) file to a board
  deploy_directory() — copy a project directory to a board with exclusions
  check_board_space()  — pre-flight filesystem usage check
  verify_file_size() — post-transfer integrity check via os.stat on board
"""
import pathlib
import re
import subprocess

# ── Constants ──────────────────────────────────────────────────────────────
MPREMOTE_CMD = "mpremote"
SPACE_WARN_PCT = 70     # warn but proceed
SPACE_FAIL_PCT = 90     # hard fail, do not deploy

DEPLOY_EXCLUDE_DIRS = {"__pycache__", ".git", "tests", ".planning"}
DEPLOY_EXCLUDE_EXTS = {".pyc"}


# ── Space check ────────────────────────────────────────────────────────────

def check_board_space(port: str) -> dict:
    """Check filesystem usage on the board's root filesystem.

    Runs: mpremote connect <port> df
    Parses the "/" filesystem line from mpremote df output.

    mpremote df output format:
        /       : 512000 bytes total,  200000 bytes used,  312000 bytes free

    Returns:
        {"error": "board_unreachable", "detail": ...}  — if mpremote fails
        {"error": "insufficient_space", "detail": ...} — if pct >= SPACE_FAIL_PCT
        {"warning": "filesystem_70pct_full", "pct": N} — if pct >= SPACE_WARN_PCT
        {"ok": True, "pct": N}                         — otherwise
    """
    try:
        result = subprocess.run(
            [MPREMOTE_CMD, "connect", port, "df"],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return {"error": "board_unreachable", "detail": "mpremote df timed out after 15s"}
    except FileNotFoundError:
        return {"error": "board_unreachable", "detail": f"'{MPREMOTE_CMD}' not found — is mpremote installed?"}

    if result.returncode != 0:
        return {"error": "board_unreachable", "detail": result.stderr.strip()}

    # Parse "/ : NNN bytes total, NNN bytes used, NNN bytes free"
    total_bytes = None
    used_bytes = None
    for line in result.stdout.splitlines():
        # Match lines that start with "/" (the root filesystem)
        stripped = line.strip()
        if not stripped.startswith("/"):
            continue
        m = re.search(r'(\d+)\s+bytes total,\s*(\d+)\s+bytes used', stripped)
        if m:
            total_bytes = int(m.group(1))
            used_bytes = int(m.group(2))
            break

    if total_bytes is None or total_bytes == 0:
        # Cannot parse — treat as unknown, allow deploy to proceed
        return {"ok": True, "pct": 0}

    pct = int(used_bytes / total_bytes * 100)

    if pct >= SPACE_FAIL_PCT:
        return {
            "error": "insufficient_space",
            "detail": f"Filesystem {pct}% full (limit {SPACE_FAIL_PCT}%)",
        }
    if pct >= SPACE_WARN_PCT:
        return {"warning": "filesystem_70pct_full", "pct": pct}

    return {"ok": True, "pct": pct}


# ── Integrity check ────────────────────────────────────────────────────────

def verify_file_size(port: str, remote_path: str, local_size: int) -> dict:
    """Verify the file on the board has the expected byte count.

    Runs: mpremote connect <port> exec "import os; print(os.stat('<remote_path>')[6])"

    Returns:
        {"error": "file_integrity_failed", "detail": ...} — size mismatch
        {"ok": True}                                       — sizes match
    """
    exec_cmd = f"import os; print(os.stat('{remote_path}')[6])"
    try:
        result = subprocess.run(
            [MPREMOTE_CMD, "connect", port, "exec", exec_cmd],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return {"error": "file_integrity_failed", "detail": "mpremote exec timed out after 10s"}
    except FileNotFoundError:
        return {"error": "file_integrity_failed", "detail": f"'{MPREMOTE_CMD}' not found"}

    if result.returncode != 0:
        return {
            "error": "file_integrity_failed",
            "detail": f"Could not stat remote file: {result.stderr.strip()}",
        }

    try:
        remote_size = int(result.stdout.strip())
    except ValueError:
        return {
            "error": "file_integrity_failed",
            "detail": f"Could not parse remote file size from: {result.stdout.strip()!r}",
        }

    if remote_size != local_size:
        return {
            "error": "file_integrity_failed",
            "detail": f"Expected {local_size} bytes, got {remote_size}",
        }

    return {"ok": True}


# ── deploy_file ────────────────────────────────────────────────────────────

def deploy_file(port: str, local_path: str, remote_path: str | None = None) -> dict:
    """Deploy a single file to the board.

    Args:
        port:        Serial port the board is connected to (e.g. "/dev/ttyUSB0").
        local_path:  Absolute or relative path to the local file.
        remote_path: Destination path on the board. Defaults to the filename
                     placed in the board root (e.g. "boot.py").

    Returns error dicts on failure (never raises). On success:
        {"port": port, "files_written": [remote_path]}
        with optional "warning" key if filesystem is 70-89% full.
    """
    local = pathlib.Path(local_path)
    if remote_path is None:
        remote_path = local.name

    # Pre-flight space check
    space_result = check_board_space(port)
    if "error" in space_result:
        return space_result

    # Copy file
    try:
        cp_result = subprocess.run(
            [MPREMOTE_CMD, "connect", port, "cp", str(local), f":{remote_path}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"error": "deploy_failed", "detail": "mpremote cp timed out after 30s"}
    except FileNotFoundError:
        return {"error": "deploy_failed", "detail": f"'{MPREMOTE_CMD}' not found"}

    if cp_result.returncode != 0:
        return {"error": "deploy_failed", "detail": cp_result.stderr.strip()}

    # Integrity check
    integrity = verify_file_size(port, remote_path, local.stat().st_size)
    if "error" in integrity:
        return integrity

    # Build success response
    response: dict = {"port": port, "files_written": [remote_path]}
    if "warning" in space_result:
        response["warning"] = space_result["warning"]
    return response


# ── deploy_directory ───────────────────────────────────────────────────────

def deploy_directory(port: str, local_dir: str) -> dict:
    """Deploy a project directory to the board, applying exclusion rules.

    Recursively collects all files under local_dir, skipping:
    - Any file whose path contains a component in DEPLOY_EXCLUDE_DIRS
    - Any file whose extension is in DEPLOY_EXCLUDE_EXTS

    Performs one pre-flight space check before the first file. If space is
    insufficient, returns immediately without deploying any files.

    Returns error dicts on failure (never raises). On success:
        {"port": port, "files_written": [list of remote paths]}
        with optional "warning" key if filesystem is 70-89% full.
    """
    base = pathlib.Path(local_dir)

    # Collect eligible files
    files_to_deploy = []
    for f in base.rglob("*"):
        if not f.is_file():
            continue
        # Check if any path component is in the exclusion set
        relative = f.relative_to(base)
        parts = set(relative.parts[:-1])  # directory parts only
        if parts & DEPLOY_EXCLUDE_DIRS:
            continue
        # Also check the direct parent (for files like .git/config)
        if any(part in DEPLOY_EXCLUDE_DIRS for part in relative.parts):
            continue
        # Check extension
        if f.suffix in DEPLOY_EXCLUDE_EXTS:
            continue
        files_to_deploy.append(f)

    if not files_to_deploy:
        return {"port": port, "files_written": []}

    # Pre-flight space check (once)
    space_result = check_board_space(port)
    if "error" in space_result:
        return space_result

    files_written = []

    for local_file in files_to_deploy:
        relative = local_file.relative_to(base)
        remote_path = str(relative)  # e.g. "lib/utils.py"

        # Copy file
        try:
            cp_result = subprocess.run(
                [MPREMOTE_CMD, "connect", port, "cp", str(local_file), f":{remote_path}"],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return {
                "error": "deploy_failed",
                "file": remote_path,
                "detail": "mpremote cp timed out after 30s",
            }
        except FileNotFoundError:
            return {
                "error": "deploy_failed",
                "file": remote_path,
                "detail": f"'{MPREMOTE_CMD}' not found",
            }

        if cp_result.returncode != 0:
            return {
                "error": "deploy_failed",
                "file": remote_path,
                "detail": cp_result.stderr.strip(),
            }

        # Integrity check
        integrity = verify_file_size(port, remote_path, local_file.stat().st_size)
        if "error" in integrity:
            return {"error": integrity["error"], "file": remote_path, "detail": integrity["detail"]}

        files_written.append(remote_path)

    response: dict = {"port": port, "files_written": files_written}
    if "warning" in space_result:
        response["warning"] = space_result["warning"]
    return response
