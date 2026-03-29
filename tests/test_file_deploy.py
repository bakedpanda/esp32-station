"""Tests for file deployment module: DEPLOY-01 through DEPLOY-04.

Tests cover:
  - deploy_file success path
  - deploy_directory with exclusion filtering
  - Space check warning at 70% usage
  - Space check hard-fail at 90% usage
  - File integrity verification (pass)
  - File integrity verification (fail)
  - deploy_file pre-flight: board unreachable
"""
import pathlib
import pytest
from unittest.mock import patch, MagicMock, call


# ── Helpers ────────────────────────────────────────────────────────────────


def _make_run_result(returncode=0, stdout="", stderr=""):
    """Convenience factory for subprocess.run mock results."""
    r = MagicMock()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


DF_OUTPUT_OK = (
    "               Size      Used     Avail  Use% Mounted on\n"
    "/              512000    51200    460800   10% /\n"
)

DF_OUTPUT_WARN = (
    "               Size      Used     Avail  Use% Mounted on\n"
    "/              512000   368640    143360   72% /\n"
)

DF_OUTPUT_FULL = (
    "               Size      Used     Avail  Use% Mounted on\n"
    "/              512000   460800     51200   90% /\n"
)


# ── Test 1: deploy_file success ─────────────────────────────────────────────


def test_deploy_file_success(tmp_path):
    """deploy_file returns port and files_written on success."""
    local_file = tmp_path / "boot.py"
    local_file.write_text("# boot")
    local_size = local_file.stat().st_size

    df_result = _make_run_result(stdout=DF_OUTPUT_OK)
    cp_result = _make_run_result()
    stat_result = _make_run_result(stdout=f"{local_size}\n")

    with patch("subprocess.run", side_effect=[df_result, cp_result, stat_result]):
        from tools.file_deploy import deploy_file
        result = deploy_file("/dev/ttyUSB0", str(local_file))

    assert result["port"] == "/dev/ttyUSB0"
    assert "files_written" in result
    assert "boot.py" in result["files_written"]
    assert "error" not in result


# ── Test 2: deploy_directory excludes unwanted paths ───────────────────────


def test_deploy_directory_applies_exclusions(tmp_path):
    """deploy_directory skips __pycache__, .pyc, .git/, tests/, .planning/."""
    # Create a project structure
    project = tmp_path / "myproject"
    project.mkdir()
    (project / "main.py").write_text("# main")
    (project / "config.json").write_text('{"x": 1}')
    pycache = project / "__pycache__"
    pycache.mkdir()
    (pycache / "main.cpython-311.pyc").write_bytes(b"\x00\x00\x00\x00")
    tests_dir = project / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("# test")
    git_dir = project / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]")
    planning_dir = project / ".planning"
    planning_dir.mkdir()
    (planning_dir / "STATE.md").write_text("# state")
    (project / "stale.pyc").write_bytes(b"\x00")

    df_result = _make_run_result(stdout=DF_OUTPUT_OK)
    # For each file deployed: cp + stat
    file_size = (project / "main.py").stat().st_size
    json_size = (project / "config.json").stat().st_size
    cp_result = _make_run_result()
    stat_result_py = _make_run_result(stdout=f"{file_size}\n")
    stat_result_json = _make_run_result(stdout=f"{json_size}\n")

    deployed_args = []

    def capture_run(cmd, **kwargs):
        deployed_args.append(cmd)
        if "df" in cmd:
            return df_result
        if "cp" in cmd:
            return cp_result
        # stat call
        if "exec" in cmd:
            # return size matching whichever file
            for arg in cmd:
                if "main.py" in arg:
                    return stat_result_py
                if "config.json" in arg:
                    return stat_result_json
            return _make_run_result(stdout="6\n")
        return _make_run_result()

    with patch("subprocess.run", side_effect=capture_run):
        from tools.file_deploy import deploy_directory
        result = deploy_directory("/dev/ttyUSB0", str(project))

    assert "error" not in result, f"Unexpected error: {result}"
    # Only .py and .json files from root (not excluded dirs)
    written = result["files_written"]
    # main.py and config.json should be included
    assert any("main.py" in f for f in written)
    assert any("config.json" in f for f in written)
    # Excluded paths must NOT appear
    for f in written:
        assert "__pycache__" not in f, f"__pycache__ leaked into deploy: {f}"
        assert ".pyc" not in f, f".pyc file leaked: {f}"
        assert ".git" not in f, f".git leaked: {f}"
        assert "tests" not in f, f"tests/ leaked: {f}"
        assert ".planning" not in f, f".planning leaked: {f}"


# ── Test 3: space check warns at 70% ───────────────────────────────────────


def test_deploy_file_warns_at_70_pct(tmp_path):
    """deploy_file returns warning when filesystem is 70-89% full but still deploys."""
    local_file = tmp_path / "app.py"
    local_file.write_text("x = 1")
    local_size = local_file.stat().st_size

    df_result = _make_run_result(stdout=DF_OUTPUT_WARN)
    cp_result = _make_run_result()
    stat_result = _make_run_result(stdout=f"{local_size}\n")

    with patch("subprocess.run", side_effect=[df_result, cp_result, stat_result]):
        from tools.file_deploy import deploy_file
        result = deploy_file("/dev/ttyUSB0", str(local_file))

    assert "error" not in result, f"Should not error at 72%: {result}"
    assert result.get("warning") == "filesystem_70pct_full"
    assert "files_written" in result


# ── Test 4: space check hard-fails at 90% ─────────────────────────────────


def test_deploy_file_fails_at_90_pct(tmp_path):
    """deploy_file returns insufficient_space error when filesystem is >=90% full."""
    local_file = tmp_path / "app.py"
    local_file.write_text("x = 1")

    df_result = _make_run_result(stdout=DF_OUTPUT_FULL)

    with patch("subprocess.run", return_value=df_result):
        from tools.file_deploy import deploy_file
        result = deploy_file("/dev/ttyUSB0", str(local_file))

    assert result["error"] == "insufficient_space"
    assert "detail" in result


# ── Test 5: integrity check passes ─────────────────────────────────────────


def test_deploy_file_integrity_passes(tmp_path):
    """deploy_file succeeds when remote file size matches local size."""
    local_file = tmp_path / "main.py"
    local_file.write_text("print('hello')")
    local_size = local_file.stat().st_size

    df_result = _make_run_result(stdout=DF_OUTPUT_OK)
    cp_result = _make_run_result()
    stat_result = _make_run_result(stdout=f"{local_size}\n")

    with patch("subprocess.run", side_effect=[df_result, cp_result, stat_result]):
        from tools.file_deploy import deploy_file
        result = deploy_file("/dev/ttyUSB0", str(local_file))

    assert "error" not in result
    assert "files_written" in result
    assert "main.py" in result["files_written"]


# ── Test 6: integrity check fails ──────────────────────────────────────────


def test_deploy_file_integrity_fails(tmp_path):
    """deploy_file returns file_integrity_failed when board reports wrong size."""
    local_file = tmp_path / "main.py"
    local_file.write_text("print('hello')")
    local_size = local_file.stat().st_size
    wrong_size = local_size + 42

    df_result = _make_run_result(stdout=DF_OUTPUT_OK)
    cp_result = _make_run_result()
    stat_result = _make_run_result(stdout=f"{wrong_size}\n")

    with patch("subprocess.run", side_effect=[df_result, cp_result, stat_result]):
        from tools.file_deploy import deploy_file
        result = deploy_file("/dev/ttyUSB0", str(local_file))

    assert result["error"] == "file_integrity_failed"
    assert "detail" in result


# ── Test 7: board unreachable on pre-flight ─────────────────────────────────


def test_deploy_file_preflight_board_unreachable(tmp_path):
    """deploy_file returns board_unreachable when mpremote df fails."""
    local_file = tmp_path / "boot.py"
    local_file.write_text("# boot")

    df_result = _make_run_result(returncode=1, stderr="could not open port /dev/ttyUSB0")

    with patch("subprocess.run", return_value=df_result):
        from tools.file_deploy import deploy_file
        result = deploy_file("/dev/ttyUSB0", str(local_file))

    assert result["error"] == "board_unreachable"
    assert "detail" in result
