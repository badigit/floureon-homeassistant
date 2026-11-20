from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

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
    raw = dict(RAW_STATUS, external_temp="NaN", svh="40", fre=None)
    status = FloureonStatus.from_api(raw)
    assert status.power is True
    assert status.external_temp is None
    assert status.max_temp == 40
    assert status.anti_freeze is None


def test_status_tolerates_partial_payload() -> None:
    status = FloureonStatus.from_api({"power": 0})
    assert status.power is False
    assert status.room_temp is None
    assert status.loop_mode is None


async def test_discover_supported_device(device: MagicMock) -> None:
    with patch(
        "custom_components.floureon.api.broadlink_async.hello",
        new_callable=AsyncMock,
        return_value=device,
    ) as discovery:
        client = await FloureonApiClient.discover(HOST, 7)
    discovery.assert_awaited_once_with(HOST, timeout=7)
    assert client.mac == MAC
    assert client.host == HOST
    assert device.timeout == 7


async def test_discover_rejects_other_broadlink_device(device: MagicMock) -> None:
    device.devtype = 0x2711
    with (
        patch(
            "custom_components.floureon.api.broadlink_async.hello",
            new_callable=AsyncMock,
            return_value=device,
        ),
        pytest.raises(UnsupportedDeviceError),
    ):
        await FloureonApiClient.discover(HOST, 3)


def test_from_config_recreates_without_discovery(device: MagicMock) -> None:
    with patch(
        "custom_components.floureon.api.broadlink_async.gendevice",
        return_value=device,
    ) as factory:
        client = FloureonApiClient.from_config(
            host=HOST, mac=MAC, dev_type=SUPPORTED_DEVICE_TYPE, timeout=4
        )
    factory.assert_called_once_with(
        SUPPORTED_DEVICE_TYPE,
        (HOST, 80),
        bytes.fromhex(MAC),
        name="Hysen Thermostat (Broadlink)",
    )
    assert client.device.timeout == 4


async def test_read_and_all_commands(
    client: FloureonApiClient, device: MagicMock
) -> None:
    assert (await client.read_status()).target_temp == 23
    await client.authenticate()
    await client.set_time(datetime(2026, 8, 31, 12, 34, 56, tzinfo=UTC))
    await client.set_manual_temperature(22.5, 2, 1)
    await client.set_hvac_mode(power=1, mode=1, schedule=2, sensor=1, cooling=True)
    await client.set_hvac_mode(power=0, mode=0, schedule=0, sensor=0, cooling=False)
    await client.set_switch_state(power=0, temperature=None, schedule=0, sensor=0)
    await client.set_switch_state(power=1, temperature=20, schedule=0, sensor=0)
    await client.set_preset_temperature(10, 0, 0)
    await client.set_preset_temperature(18, 1, 1, cooling=True)
    await client.close()

    device.auth.assert_awaited_once()
    device.set_time.assert_awaited_once_with(12, 34, 56, 1)
    device.set_mode.assert_any_await(0, 2, 1)
    device.set_temp.assert_any_await(22.5)
    device.set_power.assert_any_await(1, heating_cooling=1)
    device.set_power.assert_any_await(0)
    device.aclose.assert_awaited_once()


async def test_authentication_false_is_an_error(client, device) -> None:
    device.auth.return_value = False
    with pytest.raises(FloureonAuthenticationError):
        await client.authenticate()


def test_invalid_numbers_are_ignored() -> None:
    status = FloureonStatus.from_api({"room_temp": object(), "loop_mode": True})
    assert status.room_temp is None
    assert status.loop_mode is None
