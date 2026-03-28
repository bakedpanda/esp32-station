"""Shared fixtures for all Phase 1 tests."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_serial_ports():
    """Return a list of mock serial port objects with ESP32-compatible VIDs."""
    port1 = MagicMock()
    port1.device = "/dev/ttyUSB0"
    port1.description = "USB-SERIAL CH340"
    port1.vid = 0x1A86
    port1.pid = 0x7523
    port1.serial_number = "ABC123"

    port2 = MagicMock()
    port2.device = "/dev/ttyUSB1"
    port2.description = "CP2102 USB to UART Bridge"
    port2.vid = 0x10C4
    port2.pid = 0xEA60
    port2.serial_number = "DEF456"

    return [port1, port2]


@pytest.fixture
def non_esp32_port():
    """A serial port with a non-ESP32 VID (should be filtered out)."""
    port = MagicMock()
    port.device = "/dev/ttyACM0"
    port.description = "Arduino Uno"
    port.vid = 0x2341  # Arduino VID
    port.pid = 0x0043
    port.serial_number = "ARDUINO"
    return port


@pytest.fixture
def mock_esptool_success():
    """Mock subprocess.run returning successful chip_id output."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = (
        "esptool.py v5.2.0\n"
        "Serial port /dev/ttyUSB0\n"
        "Connecting...\n"
        "Chip is ESP32-S3 (QFN56) (revision v0.1)\n"
        "Features: WiFi, BLE\n"
        "Crystal is 40MHz\n"
        "MAC: aa:bb:cc:dd:ee:ff\n"
    )
    result.stderr = ""
    return result


@pytest.fixture
def mock_esptool_failure():
    """Mock subprocess.run returning non-zero exit code."""
    result = MagicMock()
    result.returncode = 1
    result.stdout = ""
    result.stderr = "A fatal error occurred: Failed to connect to ESP32: Timed out"
    return result


@pytest.fixture
def mock_esptool_no_chip_line():
    """Mock subprocess.run with stdout that has no 'Chip is' line."""
    result = MagicMock()
    result.returncode = 0
    result.stdout = "esptool.py v5.2.0\nSome output without chip line\n"
    result.stderr = ""
    return result
