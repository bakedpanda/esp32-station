"""Tests for mDNS discovery of MicroPython boards."""
import pytest
from unittest.mock import patch, MagicMock, call


def _make_service_info(ip="192.168.1.100", port=8266, server="esp32-abc.local."):
    """Create a mock ServiceInfo object."""
    info = MagicMock()
    info.parsed_addresses.return_value = [ip]
    info.port = port
    info.server = server
    return info


def _patch_browser_with_callbacks(service_infos):
    """Return a side_effect for ServiceBrowser that triggers add_service for each info."""
    def browser_init(zc, service_type, listener):
        for i, info in enumerate(service_infos):
            name = f"board-{i}._webrepl._tcp.local."
            listener.add_service(zc, service_type, name)
        return MagicMock()
    return browser_init


@patch("tools.mdns_discovery.time.sleep")
@patch("tools.mdns_discovery.ServiceBrowser")
@patch("tools.mdns_discovery.Zeroconf")
def test_discover_boards_found(mock_zc_class, mock_browser_class, mock_sleep):
    from tools.mdns_discovery import discover_boards

    mock_zc = MagicMock()
    mock_zc_class.return_value = mock_zc

    info = _make_service_info(ip="192.168.1.100", port=8266, server="esp32-abc.local.")
    mock_zc.get_service_info.return_value = info

    mock_browser_class.side_effect = _patch_browser_with_callbacks([info])

    result = discover_boards()

    assert result == [{"hostname": "esp32-abc.local", "ip": "192.168.1.100", "port": 8266}]
    mock_zc.close.assert_called_once()


@patch("tools.mdns_discovery.time.sleep")
@patch("tools.mdns_discovery.ServiceBrowser")
@patch("tools.mdns_discovery.Zeroconf")
def test_discover_boards_multiple(mock_zc_class, mock_browser_class, mock_sleep):
    from tools.mdns_discovery import discover_boards

    mock_zc = MagicMock()
    mock_zc_class.return_value = mock_zc

    info1 = _make_service_info(ip="192.168.1.100", port=8266, server="esp32-abc.local.")
    info2 = _make_service_info(ip="192.168.1.101", port=8266, server="esp32-xyz.local.")

    # get_service_info returns different infos for different names
    def get_info(type_, name):
        if "board-0" in name:
            return info1
        return info2
    mock_zc.get_service_info.side_effect = get_info

    mock_browser_class.side_effect = _patch_browser_with_callbacks([info1, info2])

    result = discover_boards()

    assert len(result) == 2
    assert {"hostname": "esp32-abc.local", "ip": "192.168.1.100", "port": 8266} in result
    assert {"hostname": "esp32-xyz.local", "ip": "192.168.1.101", "port": 8266} in result


@patch("tools.mdns_discovery.time.sleep")
@patch("tools.mdns_discovery.ServiceBrowser")
@patch("tools.mdns_discovery.Zeroconf")
def test_discover_boards_empty(mock_zc_class, mock_browser_class, mock_sleep):
    from tools.mdns_discovery import discover_boards

    mock_zc = MagicMock()
    mock_zc_class.return_value = mock_zc

    # ServiceBrowser never calls listener
    mock_browser_class.side_effect = lambda zc, stype, listener: MagicMock()

    result = discover_boards()

    assert result == []
    mock_zc.close.assert_called_once()


@patch("tools.mdns_discovery.time.sleep")
@patch("tools.mdns_discovery.ServiceBrowser")
@patch("tools.mdns_discovery.Zeroconf")
def test_discover_boards_error(mock_zc_class, mock_browser_class, mock_sleep):
    from tools.mdns_discovery import discover_boards

    mock_zc_class.side_effect = OSError("Network unreachable")

    result = discover_boards()

    assert isinstance(result, dict)
    assert result["error"] == "mdns_failed"
    assert "Network unreachable" in result["detail"]


@patch("tools.mdns_discovery.time.sleep")
@patch("tools.mdns_discovery.ServiceBrowser")
@patch("tools.mdns_discovery.Zeroconf")
def test_discover_boards_custom_timeout(mock_zc_class, mock_browser_class, mock_sleep):
    from tools.mdns_discovery import discover_boards

    mock_zc = MagicMock()
    mock_zc_class.return_value = mock_zc
    mock_browser_class.side_effect = lambda zc, stype, listener: MagicMock()

    discover_boards(timeout=5)

    mock_sleep.assert_called_with(5)


@patch("tools.mdns_discovery.time.sleep")
@patch("tools.mdns_discovery.ServiceBrowser")
@patch("tools.mdns_discovery.Zeroconf")
def test_discover_boards_default_timeout(mock_zc_class, mock_browser_class, mock_sleep):
    from tools.mdns_discovery import discover_boards

    mock_zc = MagicMock()
    mock_zc_class.return_value = mock_zc
    mock_browser_class.side_effect = lambda zc, stype, listener: MagicMock()

    discover_boards()

    mock_sleep.assert_called_with(3)
