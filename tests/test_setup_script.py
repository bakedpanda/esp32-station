"""Tests for setup.sh structure and content — covers SETUP-01."""
import os
import pathlib
import pytest

SETUP_SH = pathlib.Path("setup.sh")


def read_setup():
    return SETUP_SH.read_text()


def test_setup_sh_exists():
    assert SETUP_SH.exists(), "setup.sh not found in project root"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_setup_sh_executable():
    assert os.access(SETUP_SH, os.X_OK), "setup.sh is not executable"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_shebang_and_strict_mode():
    content = read_setup()
    assert "#!/usr/bin/env bash" in content, "setup.sh missing bash shebang"
    assert "set -euo pipefail" in content, "setup.sh missing strict mode (set -euo pipefail)"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_idempotency_clone_check():
    content = read_setup()
    assert "[ -d" in content, "setup.sh missing directory check for idempotent clone"
    assert ".git" in content, "setup.sh missing .git check for idempotent clone"
    assert "git pull" in content, "setup.sh missing 'git pull' for existing repo"
    assert "git clone" in content, "setup.sh missing 'git clone' for fresh install"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_idempotency_venv_check():
    content = read_setup()
    assert "[ ! -f" in content, "setup.sh missing file existence check for idempotent venv"
    assert "venv/bin/python3" in content, "setup.sh missing venv/bin/python3 reference"
    assert "python3 -m venv" in content, "setup.sh missing 'python3 -m venv' venv creation"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_idempotency_dialout_check():
    content = read_setup()
    assert "groups" in content, "setup.sh missing 'groups' command for dialout check"
    assert "dialout" in content, "setup.sh missing 'dialout' group reference"
    assert "usermod -aG dialout" in content, "setup.sh missing 'usermod -aG dialout' command"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_idempotency_service_check():
    content = read_setup()
    assert "systemctl restart" in content, (
        "setup.sh must use 'systemctl restart' (not 'start') so re-runs don't fail "
        "when service is already running"
    )


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_credential_prompt_ssid():
    content = read_setup()
    assert "read -rp" in content, "setup.sh missing 'read -rp' prompt for SSID"
    assert "WIFI_SSID" in content, "setup.sh missing WIFI_SSID variable"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_credential_prompt_password_silent():
    content = read_setup()
    assert "read -rsp" in content, "setup.sh missing 'read -rsp' silent prompt for password"
    assert "WIFI_PASSWORD" in content, "setup.sh missing WIFI_PASSWORD variable"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_credential_prompt_webrepl_silent():
    content = read_setup()
    assert "read -rsp" in content, "setup.sh missing 'read -rsp' silent prompt"
    assert "WEBREPL_PASSWORD" in content, "setup.sh missing WEBREPL_PASSWORD variable"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_credentials_file_path():
    content = read_setup()
    assert "/etc/esp32-station/wifi.json" in content, (
        "setup.sh credentials file path must be '/etc/esp32-station/wifi.json' "
        "(must match CREDENTIALS_PATH in tools/credentials.py)"
    )


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_credentials_file_keys():
    content = read_setup()
    assert '"ssid"' in content, "setup.sh missing \"ssid\" key in credentials JSON"
    assert '"password"' in content, "setup.sh missing \"password\" key in credentials JSON"
    assert '"webrepl_password"' in content, (
        "setup.sh missing \"webrepl_password\" key in credentials JSON"
    )


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_credentials_file_permissions():
    content = read_setup()
    assert "chmod 600" in content, "setup.sh missing 'chmod 600' for credentials file"
    assert "/etc/esp32-station/wifi.json" in content, (
        "setup.sh missing credentials file path for chmod 600"
    )


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_venv_pip_not_global():
    content = read_setup()
    assert "venv/bin/pip" in content, (
        "setup.sh must use 'venv/bin/pip' (never bare 'pip install' which installs globally)"
    )


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_service_file_patched_not_copied_raw():
    content = read_setup()
    assert "sed" in content, "setup.sh missing 'sed' for patching service file user"
    assert "User=esp32" in content, (
        "setup.sh missing 'User=esp32' sed substitution target "
        "(raw cp without sed would leave wrong user in service file)"
    )


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_endpoint_print():
    content = read_setup()
    assert "http://" in content, "setup.sh missing printed endpoint URL (http://)"
    assert ":8000/mcp" in content, "setup.sh missing ':8000/mcp' in printed endpoint URL"


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_mcp_add_command_printed():
    content = read_setup()
    assert "claude mcp add --transport http" in content, (
        "setup.sh must print the 'claude mcp add --transport http' command for the user to run"
    )


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_python3_venv_check():
    content = read_setup()
    assert "python3 -c" in content, "setup.sh missing 'python3 -c' for venv availability check"
    assert "import venv" in content, (
        "setup.sh missing 'import venv' check to ensure python3-venv package is installed"
    )


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_existing_credentials_overwrite_guard():
    content = read_setup()
    assert "/etc/esp32-station/wifi.json" in content, (
        "setup.sh missing credentials file path in overwrite guard"
    )
    assert "verwrite" in content, (
        "setup.sh missing overwrite prompt/guard for existing credentials file (Pitfall 5: "
        "idempotent guard — check for 'Overwrite' or 'overwrite')"
    )


@pytest.mark.skipif(not SETUP_SH.exists(), reason="setup.sh not yet created")
def test_dialout_relogin_notice():
    content = read_setup()
    assert any(word in content for word in ("log out", "logout")), (
        "setup.sh must tell the user to log out (and back in) for dialout group to take effect"
    )
    assert "dialout" in content, "setup.sh missing 'dialout' in re-login notice context"
