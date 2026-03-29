"""Tests for GitHub deploy module: DEPLOY-05.

Tests cover:
  - pull_and_deploy_github success path (mocked git clone + deploy_directory)
  - git clone timeout returns git_clone_timeout error
  - private repo token is sanitized from error output
"""
import subprocess
import pytest
from unittest.mock import patch, MagicMock


def _make_run_result(returncode=0, stdout="", stderr=""):
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def test_pull_and_deploy_success():
    """Success path: git clone exits 0, deploy_directory returns files_written list."""
    from tools.github_deploy import pull_and_deploy_github

    clone_result = _make_run_result(returncode=0)
    deploy_result = {"port": "/dev/ttyUSB0", "files_written": ["main.py", "boot.py"]}

    with patch("subprocess.run", return_value=clone_result):
        with patch("tools.github_deploy.deploy_directory", return_value=deploy_result):
            result = pull_and_deploy_github(
                port="/dev/ttyUSB0",
                repo_url="https://github.com/example/esp32-project",
                branch="main",
            )

    assert "files_written" in result
    assert isinstance(result["files_written"], list)


def test_git_clone_timeout():
    """subprocess.TimeoutExpired during git clone returns git_clone_timeout error."""
    from tools.github_deploy import pull_and_deploy_github

    with patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["git", "clone"], timeout=60),
    ):
        result = pull_and_deploy_github(
            port="/dev/ttyUSB0",
            repo_url="https://github.com/example/esp32-project",
            branch="main",
        )

    assert result["error"] == "git_clone_timeout"
    assert "60" in result["detail"] or "timeout" in result["detail"].lower()


def test_token_not_leaked():
    """Token embedded in URL must NOT appear verbatim in error detail."""
    from tools.github_deploy import pull_and_deploy_github

    secret_token = "ghp_supersecrettoken12345"
    # git clone fails and stderr contains the URL with the embedded token
    clone_result = _make_run_result(
        returncode=128,
        stderr=f"fatal: repository 'https://{secret_token}@github.com/example/private' not found",
    )

    with patch("subprocess.run", return_value=clone_result):
        result = pull_and_deploy_github(
            port="/dev/ttyUSB0",
            repo_url="https://github.com/example/private",
            branch="main",
            token=secret_token,
        )

    assert result["error"] == "git_clone_failed"
    assert secret_token not in result.get("detail", ""), \
        f"Token leaked in detail: {result.get('detail')}"
