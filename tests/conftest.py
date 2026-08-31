"""Shared fixtures for Floureon tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_TIMEOUT, CONF_TYPE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.floureon.api import FloureonApiClient, FloureonStatus
from custom_components.floureon.const import (
    CONF_ENTITY_TYPE,
    DOMAIN,
    ENTITY_TYPE_CLIMATE,
    SUPPORTED_DEVICE_TYPE,
)

pytest_plugins = "pytest_homeassistant_custom_component"

HOST = "192.0.2.10"
MAC = "112233445566"

RAW_STATUS = {
    "power": 1,
    "active": 1,
    "temp_manual": 0,
    "heating_cooling": 0,
    "room_temp": 21.5,
    "external_temp": 25.0,
    "thermostat_temp": 23.0,
    "auto_mode": 1,
    "loop_mode": 0,
    "sensor": 1,
    "dif": 2,
    "svh": 35,
    "svl": 5,
    "room_temp_adj": -0.5,
    "remote_lock": 0,
    "fre": 1,
    "poweron": 1,
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from this repository."""


@pytest.fixture
def device() -> MagicMock:
    """Return a configured python-broadlink device double."""
    result = MagicMock()
    result.host = (HOST, 80)
    result.mac = bytes.fromhex(MAC)
    result.devtype = SUPPORTED_DEVICE_TYPE
    result.model = "HY02/HY03"
    result.manufacturer = "Hysen"
    result.auth.return_value = True
    result.get_full_status.return_value = dict(RAW_STATUS)
    return result


@pytest.fixture
def client(device: MagicMock) -> FloureonApiClient:
    """Return a client around the mocked device."""
    return FloureonApiClient(device)


@pytest.fixture
def status() -> FloureonStatus:
    """Return a representative physical snapshot."""
    return FloureonStatus.from_api(RAW_STATUS)


@pytest.fixture
def entry() -> MockConfigEntry:
    """Return a climate config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        title="Hall thermostat",
        data={
            CONF_HOST: HOST,
            CONF_MAC: MAC,
            CONF_TYPE: SUPPORTED_DEVICE_TYPE,
            CONF_TIMEOUT: 3,
        },
        options={CONF_ENTITY_TYPE: ENTITY_TYPE_CLIMATE},
    )


@pytest.fixture
def mock_discovery(client: FloureonApiClient):
    """Patch config-flow discovery."""
    with patch(
        "custom_components.floureon.config_flow.FloureonApiClient.discover",
        return_value=client,
    ) as mocked:
        yield mocked


@pytest.fixture
def mock_setup_entry():
    """Prevent a successful flow from talking to platform setup."""
    with patch(
        "custom_components.floureon.async_setup_entry",
        new=AsyncMock(return_value=True),
    ) as mocked:
        yield mocked


@pytest.fixture
def add_entry(hass: HomeAssistant, entry: MockConfigEntry) -> MockConfigEntry:
    """Add a representative entry to Home Assistant."""
    entry.add_to_hass(hass)
    return entry
