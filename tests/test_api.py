"""Tests for the protocol-facing client."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from custom_components.floureon.api import (
    FloureonApiClient,
    FloureonAuthenticationError,
    FloureonStatus,
    UnsupportedDeviceError,
)
from custom_components.floureon.const import SUPPORTED_DEVICE_TYPE

from .conftest import HOST, MAC, RAW_STATUS


def test_status_normalises_protocol_data() -> None:
    """Numbers, flags and missing fields keep truthful meanings."""
    raw = dict(RAW_STATUS, external_temp="NaN", svh="40", fre=None)
    status = FloureonStatus.from_api(raw)
    assert status.power is True
    assert status.external_temp is None
    assert status.max_temp == 40
    assert status.anti_freeze is None


def test_status_tolerates_partial_payload() -> None:
    """A partial packet does not crash every entity property."""
    status = FloureonStatus.from_api({"power": 0})
    assert status.power is False
    assert status.room_temp is None
    assert status.loop_mode is None


def test_discover_authenticates_supported_device(device: MagicMock) -> None:
    """Discovery validates Broadlink's device type and preserves timeout."""
    with patch("custom_components.floureon.api.broadlink.hello", return_value=device):
        client = FloureonApiClient.discover(HOST, 7)
    assert client.mac == MAC
    assert client.host == HOST
    assert device.timeout == 7


def test_discover_rejects_other_broadlink_device(device: MagicMock) -> None:
    """A smart plug at the entered address is not accepted as a thermostat."""
    device.devtype = 0x2711
    with (
        patch("custom_components.floureon.api.broadlink.hello", return_value=device),
        pytest.raises(UnsupportedDeviceError),
    ):
        FloureonApiClient.discover(HOST, 3)


def test_from_config_recreates_without_discovery(device: MagicMock) -> None:
    """Restart uses saved identity and avoids UDP discovery."""
    with patch(
        "custom_components.floureon.api.broadlink.gendevice", return_value=device
    ) as factory:
        client = FloureonApiClient.from_config(
            host=HOST, mac=MAC, dev_type=SUPPORTED_DEVICE_TYPE, timeout=4
        )
    factory.assert_called_once_with(
        SUPPORTED_DEVICE_TYPE,
        (HOST, 80),
        bytes.fromhex(MAC),
        name="Floureon Thermostat",
    )
    assert client.device.timeout == 4


def test_read_and_all_commands(client: FloureonApiClient, device: MagicMock) -> None:
    """Client maps every entity action to the Broadlink protocol."""
    assert client.read_status().target_temp == 23
    client.authenticate()
    client.set_time(datetime(2026, 8, 31, 12, 34, 56, tzinfo=UTC))
    client.set_manual_temperature(22.5, 2, 1)
    client.set_hvac_mode(power=1, mode=1, schedule=2, sensor=1, cooling=True)
    client.set_hvac_mode(power=0, mode=0, schedule=0, sensor=0, cooling=False)
    client.set_switch_state(power=0, temperature=None, schedule=0, sensor=0)
    client.set_switch_state(power=1, temperature=20, schedule=0, sensor=0)
    client.set_preset_temperature(10, 0, 0)
    client.set_preset_temperature(18, 1, 1, cooling=True)

    device.auth.assert_called_once()
    device.set_time.assert_called_once_with(12, 34, 56, 1)
    device.set_mode.assert_any_call(0, 2, 1)
    device.set_temp.assert_any_call(22.5)
    device.set_power.assert_any_call(1, heating_cooling=1)
    device.set_power.assert_any_call(0)


def test_authentication_false_is_an_error(client, device) -> None:
    """A false result cannot be mistaken for a successful setup."""
    device.auth.return_value = False
    with pytest.raises(FloureonAuthenticationError):
        client.authenticate()


def test_invalid_numbers_are_ignored() -> None:
    """Malformed protocol fields do not poison an entire snapshot."""
    status = FloureonStatus.from_api({"room_temp": object(), "loop_mode": True})
    assert status.room_temp is None
    assert status.loop_mode is None
