"""Per-port serial locking via file-based mutex (fcntl.flock).

Requirements covered: MCP-04 (concurrent access serialization).

Provides:
  port_to_slug(port) — convert "/dev/ttyUSB0" to "dev_ttyUSB0" for use in lock filenames
  SerialLock         — context manager that holds an exclusive fcntl lock on a per-port lock file
"""
import fcntl
import pathlib
import time

# ── Constants ──────────────────────────────────────────────────────────────
LOCK_DIR = pathlib.Path.home() / ".esp32-station" / "locks"
LOCK_TIMEOUT_SECONDS = 30   # wait up to 30s for lock, then fail


# ── Helpers ────────────────────────────────────────────────────────────────

def port_to_slug(port: str) -> str:
    """Convert a serial port path to a filesystem-safe slug.

    Replaces all "/" with "_", then strips any leading "_".

    Examples:
        "/dev/ttyUSB0"  -> "dev_ttyUSB0"
        "/dev/ttyACM1"  -> "dev_ttyACM1"
    """
    return port.replace("/", "_").lstrip("_")


# ── SerialLock context manager ─────────────────────────────────────────────

class SerialLock:
    """Exclusive per-port file lock using fcntl.flock.

    Acquires an exclusive lock on LOCK_DIR/<port_slug>.lock.
    Blocks (polling) until the lock is available or timeout elapses.
    Releases and removes the lock file on context exit.

    Usage:
        with SerialLock("/dev/ttyUSB0"):
            # exclusive access to the board on /dev/ttyUSB0
            ...

    Raises:
        TimeoutError: if the lock cannot be acquired within `timeout` seconds.
    """

    def __init__(self, port: str, timeout: int = LOCK_TIMEOUT_SECONDS):
        self.port = port
        self.timeout = timeout
        self._lock_path = LOCK_DIR / f"{port_to_slug(port)}.lock"
        self._lock_file = None

    def __enter__(self):
        LOCK_DIR.mkdir(parents=True, exist_ok=True)
        self._lock_file = open(self._lock_path, "w")
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(self._lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    self._lock_file.close()
                    raise TimeoutError(
                        f"Could not acquire serial lock for {self.port} "
                        f"after {self.timeout}s — another operation is in progress"
                    )
                time.sleep(0.1)

    def __exit__(self, *args):
        if self._lock_file:
            fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            self._lock_file.close()
            try:
                self._lock_path.unlink()
            except FileNotFoundError:
                pass
