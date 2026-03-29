"""Tests for REPL command execution module: REPL-01, REPL-02, REPL-03, BOARD-03."""
import subprocess
import pytest
from unittest.mock import patch, MagicMock


PORT = "/dev/ttyUSB0"


# ── exec_repl tests ────────────────────────────────────────────────────────

def test_exec_repl_success():
    """REPL-01: exec_repl returns port and stripped output on success."""
    run_result = MagicMock(returncode=0, stdout="42\n", stderr="")
    with patch("subprocess.run", return_value=run_result):
        from tools.repl import exec_repl
        result = exec_repl(PORT, "print(42)")
    assert result["port"] == PORT
    assert result["output"] == "42"
    assert "error" not in result


def test_exec_repl_strips_whitespace():
    """REPL-01: exec_repl strips leading/trailing whitespace from output."""
    run_result = MagicMock(returncode=0, stdout="  hello  \n", stderr="")
    with patch("subprocess.run", return_value=run_result):
        from tools.repl import exec_repl
        result = exec_repl(PORT, "print('  hello  ')")
    assert result["output"] == "hello"
    assert "error" not in result


def test_exec_repl_timeout():
    """REPL-03: exec_repl returns error dict when subprocess times out."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="mpremote", timeout=10)):
        from tools.repl import exec_repl
        result = exec_repl(PORT, "while True: pass")
    assert result["error"] == "repl_timeout"
    assert "10s" in result["detail"]
    assert "port" not in result


def test_exec_repl_subprocess_failure():
    """REPL-01: exec_repl returns error dict when subprocess exits non-zero."""
    run_result = MagicMock(returncode=1, stdout="", stderr="NameError: name 'x' not defined")
    with patch("subprocess.run", return_value=run_result):
        from tools.repl import exec_repl
        result = exec_repl(PORT, "print(x)")
    assert result["error"] == "repl_failed"
    assert "NameError" in result["detail"]
    assert "port" not in result


# ── read_serial tests ──────────────────────────────────────────────────────

def test_read_serial_success():
    """REPL-02: read_serial returns port and output on success."""
    run_result = MagicMock(returncode=0, stdout="line1\nline2\n", stderr="")
    with patch("subprocess.run", return_value=run_result):
        from tools.repl import read_serial
        result = read_serial(PORT)
    assert result["port"] == PORT
    assert "line1" in result["output"]
    assert "line2" in result["output"]
    assert "error" not in result


# ── soft_reset tests ───────────────────────────────────────────────────────

def test_soft_reset_success():
    """BOARD-03: soft_reset returns reset=soft on success (returncode=0)."""
    run_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=run_result):
        from tools.repl import soft_reset
        result = soft_reset(PORT)
    assert result["port"] == PORT
    assert result["reset"] == "soft"
    assert "error" not in result


# ── hard_reset tests ───────────────────────────────────────────────────────

def test_hard_reset_success():
    """BOARD-03: hard_reset returns reset=hard on success (returncode=0)."""
    run_result = MagicMock(returncode=0, stdout="", stderr="")
    with patch("subprocess.run", return_value=run_result):
        from tools.repl import hard_reset
        result = hard_reset(PORT)
    assert result["port"] == PORT
    assert result["reset"] == "hard"
    assert "error" not in result


def test_hard_reset_failure():
    """BOARD-03: hard_reset returns error dict when subprocess fails with stderr."""
    run_result = MagicMock(returncode=1, stdout="", stderr="Could not connect to board")
    with patch("subprocess.run", return_value=run_result):
        from tools.repl import hard_reset
        result = hard_reset(PORT)
    assert "error" in result
    assert result["error"] == "hard_reset_failed"
    assert "Could not connect" in result["detail"]
