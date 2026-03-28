"""Tests for firmware flash module: FLASH-01 through FLASH-05."""
import pytest
from unittest.mock import patch, MagicMock, call
import time
import pathlib


def test_flash_firmware_preflight_detects_chip(tmp_path):
    """FLASH-05: flash_firmware runs detect_chip as pre-flight before flashing."""
    detect_mock = MagicMock(return_value={"port": "/dev/ttyUSB0", "chip": "ESP32-S3"})
    fw_bin = tmp_path / "ESP32_S3.bin"
    fw_bin.write_bytes(b"fake firmware")

    with patch("tools.firmware_flash.detect_chip", detect_mock), \
         patch("tools.firmware_flash.FIRMWARE_DIR", tmp_path), \
         patch("subprocess.run") as run_mock:
        run_mock.return_value = MagicMock(returncode=0, stdout="", stderr="")
        from tools.firmware_flash import flash_firmware
        flash_firmware("/dev/ttyUSB0", chip=None)

    detect_mock.assert_called_once_with("/dev/ttyUSB0")


def test_flash_preflight_fails_fast_on_chip_error(tmp_path):
    """FLASH-04: flash_firmware returns preflight_failed error if detect_chip fails."""
    detect_mock = MagicMock(return_value={"error": "chip_id_failed", "detail": "timed out"})
    with patch("tools.firmware_flash.detect_chip", detect_mock):
        from tools.firmware_flash import flash_firmware
        result = flash_firmware("/dev/ttyUSB0", chip=None)
    assert result["error"] == "preflight_failed"


def test_flash_firmware_calls_write_flash(tmp_path, mock_esptool_success):
    """FLASH-01: flash_firmware invokes esptool write_flash subprocess."""
    fw_bin = tmp_path / "ESP32_S3.bin"
    fw_bin.write_bytes(b"fake firmware content")

    erase_result = MagicMock(returncode=0, stdout="", stderr="")
    write_result = MagicMock(returncode=0, stdout="Hash of data verified.", stderr="")

    with patch("tools.firmware_flash.FIRMWARE_DIR", tmp_path), \
         patch("subprocess.run", side_effect=[erase_result, write_result]) as run_mock:
        from tools.firmware_flash import flash_firmware
        result = flash_firmware("/dev/ttyUSB0", chip="ESP32-S3")

    calls = run_mock.call_args_list
    assert any("write_flash" in str(c) for c in calls), "esptool write_flash not called"
    assert any("erase_flash" in str(c) for c in calls), "esptool erase_flash not called"


def test_firmware_cache_used_when_fresh(tmp_path):
    """FLASH-03: get_firmware_path returns cached file without downloading if mtime < 7 days."""
    fw_bin = tmp_path / "ESP32_S3.bin"
    fw_bin.write_bytes(b"cached firmware")
    # Set mtime to 1 day ago (fresh)
    recent_mtime = time.time() - 86400
    import os
    os.utime(fw_bin, (recent_mtime, recent_mtime))

    with patch("tools.firmware_flash.FIRMWARE_DIR", tmp_path), \
         patch("requests.get") as get_mock:
        from tools.firmware_flash import get_firmware_path
        result = get_firmware_path("ESP32-S3")

    get_mock.assert_not_called()
    assert result == fw_bin


def test_firmware_downloaded_when_stale(tmp_path):
    """FLASH-03: get_firmware_path downloads when cached file is older than 7 days."""
    fw_bin = tmp_path / "ESP32_S3.bin"
    fw_bin.write_bytes(b"stale firmware")
    stale_mtime = time.time() - (8 * 86400)  # 8 days ago
    import os
    os.utime(fw_bin, (stale_mtime, stale_mtime))

    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.content = b"fresh firmware bytes"

    with patch("tools.firmware_flash.FIRMWARE_DIR", tmp_path), \
         patch("requests.get", return_value=fake_response) as get_mock:
        from tools.firmware_flash import get_firmware_path
        get_firmware_path("ESP32-S3")

    get_mock.assert_called_once()


def test_firmware_correct_url_for_chip(tmp_path):
    """FLASH-02: get_firmware_path downloads from URL matching chip variant."""
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.content = b"firmware bytes"

    with patch("tools.firmware_flash.FIRMWARE_DIR", tmp_path), \
         patch("requests.get", return_value=fake_response) as get_mock:
        from tools.firmware_flash import get_firmware_path
        get_firmware_path("ESP32-C3")

    called_url = get_mock.call_args[0][0]
    assert "C3" in called_url or "c3" in called_url.lower(), f"URL {called_url} does not reference C3"


def test_flash_unsupported_chip_returns_error(tmp_path):
    """FLASH-02 / FLASH-04: flash_firmware returns error for unknown chip variant."""
    with patch("tools.firmware_flash.FIRMWARE_DIR", tmp_path):
        from tools.firmware_flash import flash_firmware
        result = flash_firmware("/dev/ttyUSB0", chip="ESP32-BOGUS")
    assert result["error"] == "unsupported_chip"
