"""GitHub repository pull and deploy to ESP32 boards via USB.

Requirements covered: DEPLOY-05.

Provides:
  pull_and_deploy_github() — git clone a repo into a temp dir, then deploy via USB

Design notes (D-09 through D-12):
  - Uses git subprocess (not gitpython — gitpython timeout support is known-broken)
  - Clones with --depth 1 into a TemporaryDirectory; no persistent work dir
  - Deploys via existing deploy_directory() from file_deploy.py (reuses all space checks,
    exclusion rules, and integrity verification)
  - SerialLock must be applied in mcp_server.py, not here (same pattern as Phase 2 tools)

Security notes (D-10):
  - The `token` parameter is embedded into the URL only for the git clone call
  - Token is never stored to disk, state files, or module-level variables
  - Any error message containing the URL is sanitized before returning
"""
import pathlib
import subprocess
import tempfile

from tools.file_deploy import deploy_directory

# ── Constants ──────────────────────────────────────────────────────────────
GIT_TIMEOUT_SECONDS = 60   # generous for small repos on slow connections


# ── pull_and_deploy_github ─────────────────────────────────────────────────

def pull_and_deploy_github(
    port: str,
    repo_url: str,
    branch: str = "main",
    token: str | None = None,
) -> dict:
    """Pull the latest code from a GitHub repository and deploy it to a board via USB.

    Args:
        port:     Serial port the board is connected to (e.g. "/dev/ttyUSB0").
        repo_url: GitHub repository URL, e.g. "https://github.com/user/esp32-project".
        branch:   Branch to deploy (default: "main"). Caller must know the correct branch name.
        token:    Optional personal access token for private repos (D-10).
                  Embedded in URL for the clone call only; never stored.

    Returns the deploy_directory() result dict on success:
        {"port": port, "files_written": [...]}

    Returns error dicts on failure (never raises):
        {"error": "git_clone_timeout", "detail": ...}
        {"error": "git_clone_failed",  "detail": ...}  — token sanitized from detail
        {"error": "git_not_found",     "detail": ...}
        Any error dict returned by deploy_directory() is passed through unchanged.
    """
    # Embed token in URL for private repos (D-10)
    clone_url = repo_url
    if token:
        if clone_url.startswith("https://"):
            clone_url = clone_url.replace("https://", f"https://{token}@", 1)

    with tempfile.TemporaryDirectory(prefix="esp32-github-") as tmpdir:
        repo_dir = pathlib.Path(tmpdir) / "repo"

        try:
            result = subprocess.run(
                ["git", "clone", "--branch", branch, "--depth", "1", clone_url, str(repo_dir)],
                capture_output=True,
                text=True,
                timeout=GIT_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return {
                "error": "git_clone_timeout",
                "detail": f"git clone timed out after {GIT_TIMEOUT_SECONDS}s",
            }
        except FileNotFoundError:
            return {
                "error": "git_not_found",
                "detail": "'git' not found on system PATH",
            }

        if result.returncode != 0:
            # Sanitize token from error output before returning (Pitfall 3)
            raw_detail = result.stderr.strip() or result.stdout.strip()
            safe_detail = raw_detail.replace(token, "***") if token else raw_detail
            return {"error": "git_clone_failed", "detail": safe_detail}

        # Reuse existing deploy_directory (D-12) — SerialLock applied in mcp_server.py
        return deploy_directory(port, str(repo_dir))
