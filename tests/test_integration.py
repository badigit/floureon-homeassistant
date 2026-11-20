"""End-to-end Home Assistant lifecycle tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM


async def test_setup_commands_reload_and_unload(
    hass: HomeAssistant,
    entry,
    client,
    device: MagicMock,
) -> None:
    """A config entry creates a working climate entity and unloads cleanly."""
    entry.add_to_hass(hass)
    with patch(
        "custom_components.floureon.FloureonApiClient.from_config",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.hall_thermostat")
    assert state is not None
    assert state.state == HVACMode.AUTO
    assert state.attributes["current_temperature"] == 25.0
    assert state.attributes["temperature"] == 23.0
    assert device.auth.await_count == 1
    assert device.get_full_status.await_count >= 2
    device.set_time.assert_awaited_once()

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )
    device.set_mode.assert_any_await(0, 0, 1)
    device.set_temp.assert_any_await(22.5)

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: state.entity_id, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )
    device.set_power.assert_any_await(0, heating_cooling=0)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.states.get(state.entity_id).state == "unavailable"
    device.aclose.assert_awaited_once()


async def test_reload_listener(hass: HomeAssistant, entry, client) -> None:
    """Changing options reloads the entry through the registered listener."""
    entry.add_to_hass(hass)
    with patch(
        "custom_components.floureon.FloureonApiClient.from_config",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        hass.config_entries.async_update_entry(
            entry, options={**entry.options, "scan_interval": 60}
        )
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_climate_converts_native_celsius_to_fahrenheit(
    hass: HomeAssistant,
    entry,
    client,
) -> None:
    hass.config.units = US_CUSTOMARY_SYSTEM
    entry.add_to_hass(hass)
    with patch(
        "custom_components.floureon.FloureonApiClient.from_config",
        return_value=client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.hall_thermostat")
    assert state is not None
    assert state.attributes["temperature_unit"] == "°F"
    assert abs(state.attributes["current_temperature"] - 77.0) < 0.6
    assert abs(state.attributes["temperature"] - 73.4) < 0.6
    assert await hass.config_entries.async_unload(entry.entry_id)
