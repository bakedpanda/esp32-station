"""Tests for board detection: BOARD-01, BOARD-02, BOARD-04."""
import pytest
from unittest.mock import patch, MagicMock
import json
import tempfile
import pathlib


def test_list_boards_returns_list(mock_serial_ports):
    """BOARD-01: list_boards returns a list of dicts for ESP32-VID ports."""
    with patch("serial.tools.list_ports.comports", return_value=mock_serial_ports):
        from tools.board_detection import list_boards
        result = list_boards()
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["port"] == "/dev/ttyUSB0"


def test_list_boards_filters_non_esp32(mock_serial_ports, non_esp32_port):
    """BOARD-01: list_boards excludes ports with non-ESP32 VIDs."""
    all_ports = mock_serial_ports + [non_esp32_port]
    with patch("serial.tools.list_ports.comports", return_value=all_ports):
        from tools.board_detection import list_boards
        result = list_boards()
    assert len(result) == 2
    assert all(p["port"] != "/dev/ttyACM0" for p in result)


def test_detect_chip_success(mock_esptool_success):
    """BOARD-02: detect_chip parses 'Chip is ESP32-S3' from esptool stdout."""
    with patch("subprocess.run", return_value=mock_esptool_success):
        from tools.board_detection import detect_chip
        result = detect_chip("/dev/ttyUSB0")
    assert result["chip"] == "ESP32-S3"
    assert result["port"] == "/dev/ttyUSB0"
    assert "error" not in result


def test_detect_chip_subprocess_failure(mock_esptool_failure):
    """FLASH-04: detect_chip returns error dict when esptool exits non-zero."""
    with patch("subprocess.run", return_value=mock_esptool_failure):
        from tools.board_detection import detect_chip
        result = detect_chip("/dev/ttyUSB0")
    assert "error" in result
    assert result["error"] == "chip_id_failed"


def test_detect_chip_no_chip_line(mock_esptool_no_chip_line):
    """FLASH-04: detect_chip returns error dict when stdout has no 'Chip is' line."""
    with patch("subprocess.run", return_value=mock_esptool_no_chip_line):
        from tools.board_detection import detect_chip
        result = detect_chip("/dev/ttyUSB0")
    assert "error" in result
    assert result["error"] == "chip_not_parsed"


def test_board_state_roundtrip(tmp_path):
    """BOARD-04: save_board_state then load_board_state returns identical dict."""
    state_data = {
        "/dev/ttyUSB0": {"chip": "ESP32-S3", "detected_at": 1700000000.0},
        "/dev/ttyUSB1": {"chip": "ESP32", "detected_at": 1700000001.0},
    }
    boards_json = tmp_path / "boards.json"
    with patch("tools.board_detection.BOARDS_JSON", boards_json), \
         patch("tools.board_detection.STATE_DIR", tmp_path):
        from tools.board_detection import save_board_state, load_board_state
        save_board_state(state_data)
        loaded = load_board_state()
    assert loaded == state_data


def test_detect_chip_updates_state(mock_esptool_success, tmp_path):
    """BOARD-04: detect_chip persists detected chip to boards.json."""
    boards_json = tmp_path / "boards.json"
    with patch("subprocess.run", return_value=mock_esptool_success), \
         patch("tools.board_detection.BOARDS_JSON", boards_json), \
         patch("tools.board_detection.STATE_DIR", tmp_path):
        from tools.board_detection import detect_chip
        detect_chip("/dev/ttyUSB0")
    saved = json.loads(boards_json.read_text())
    assert "/dev/ttyUSB0" in saved
    assert saved["/dev/ttyUSB0"]["chip"] == "ESP32-S3"
