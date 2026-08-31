"""Entity behaviour beyond the service-level smoke test."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from broadlink.exceptions import NetworkTimeoutError
from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.components.climate.const import PRESET_AWAY, PRESET_NONE
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
)

from custom_components.floureon.api import FloureonAuthenticationError
from custom_components.floureon.climate import FloureonClimate
from custom_components.floureon.climate import (
    async_setup_entry as async_setup_climate_entry,
)
from custom_components.floureon.climate import (
    async_setup_platform as async_setup_climate_platform,
)
from custom_components.floureon.const import (
    CONF_ENTITY_TYPE,
    CONF_TURN_OFF_MODE,
    CONF_TURN_ON_MODE,
    ENTITY_TYPE_SWITCH,
    MIN_TEMP,
    TURN_OFF,
)
from custom_components.floureon.coordinator import FloureonDataUpdateCoordinator
from custom_components.floureon.diagnostics import async_get_config_entry_diagnostics
from custom_components.floureon.switch import FloureonSwitch
from custom_components.floureon.switch import (
    async_setup_entry as async_setup_switch_entry,
)
from custom_components.floureon.switch import (
    async_setup_platform as async_setup_switch_platform,
)


def _coordinator(hass, entry, client, status):
    coordinator = FloureonDataUpdateCoordinator(hass, entry, client)
    coordinator.data = status
    return coordinator


def test_climate_reports_modes_actions_and_limits(hass, entry, client, status) -> None:
    """Physical flags map to HA climate semantics."""
    coordinator = _coordinator(hass, entry, client, status)
    entity = FloureonClimate(coordinator)
    assert entity.hvac_mode is HVACMode.AUTO
    assert entity.hvac_action is HVACAction.HEATING
    assert entity.current_temperature == 25
    assert entity.target_temperature == 23
    assert entity.min_temp == 5
    assert entity.max_temp == 35
    assert entity.preset_mode == PRESET_NONE
    assert entity.extra_state_attributes["control_sensor"] == "external"

    coordinator.data = replace(status, power=False, active=False)
    assert entity.hvac_mode is HVACMode.OFF
    assert entity.hvac_action is HVACAction.OFF

    coordinator.data = replace(status, active=False)
    assert entity.hvac_action is HVACAction.IDLE

    coordinator.data = replace(status, auto_mode=0, temp_manual=True)
    assert entity.hvac_mode is HVACMode.HEAT


async def test_climate_all_commands(hass, entry, client, status) -> None:
    """Every exposed climate command reaches the coordinator."""
    coordinator = _coordinator(hass, entry, client, status)
    coordinator.async_command = AsyncMock()
    entity = FloureonClimate(coordinator)

    await entity.async_set_temperature(temperature=21.5)
    entity._preset_mode = PRESET_AWAY
    await entity.async_set_temperature(temperature=9)
    await entity.async_set_temperature()
    await entity.async_set_hvac_mode(HVACMode.AUTO)
    await entity.async_set_hvac_mode(HVACMode.HEAT)
    await entity.async_set_preset_mode(PRESET_AWAY)
    await entity.async_set_preset_mode(PRESET_NONE)
    await entity.async_turn_off()
    await entity.async_turn_on()
    assert coordinator.async_command.await_count == 8

    with pytest.raises(ValueError):
        await entity.async_set_hvac_mode(HVACMode.COOL)
    with pytest.raises(ValueError):
        await entity.async_set_preset_mode("party")

    coordinator.data = replace(status, target_temp=None, min_temp=None)
    entity._away_set_point = None
    await entity.async_set_preset_mode(PRESET_AWAY)
    assert coordinator.async_command.await_count == 9


def test_cooling_and_internal_sensor(hass, entry, client, status) -> None:
    """Cooling mode uses the protocol direction flag and selected sensor."""
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "use_cooling": True,
            "use_external_temp": False,
        },
    )
    coordinator = _coordinator(
        hass, entry, client, replace(status, heating_cooling=True, auto_mode=0)
    )
    entity = FloureonClimate(coordinator)
    assert HVACMode.HEAT_COOL in entity.hvac_modes
    assert entity.hvac_action is HVACAction.COOLING
    assert entity.current_temperature == 21.5


def test_switch_states_and_attributes(hass, entry, client, status) -> None:
    """Switch mode mirrors active output and keeps temperature context."""
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_ENTITY_TYPE: ENTITY_TYPE_SWITCH,
            CONF_TURN_ON_MODE: 24.5,
            CONF_TURN_OFF_MODE: MIN_TEMP,
        },
    )
    coordinator = _coordinator(hass, entry, client, status)
    entity = FloureonSwitch(coordinator)
    assert entity.is_on is True
    assert entity.extra_state_attributes["current_temperature"] == 25
    coordinator.data = replace(status, active=False)
    assert entity.is_on is False


async def test_switch_commands(hass, entry, client, status) -> None:
    """Both switch-off strategies generate one serial command."""
    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry,
        options={
            CONF_ENTITY_TYPE: ENTITY_TYPE_SWITCH,
            CONF_TURN_ON_MODE: 24.5,
            CONF_TURN_OFF_MODE: MIN_TEMP,
        },
    )
    coordinator = _coordinator(hass, entry, client, status)
    coordinator.async_command = AsyncMock()
    entity = FloureonSwitch(coordinator)
    await entity.async_turn_on()
    await entity.async_turn_off()
    assert coordinator.async_command.await_count == 2

    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_TURN_OFF_MODE: TURN_OFF}
    )
    entity = FloureonSwitch(coordinator)
    await entity.async_turn_off()
    assert coordinator.async_command.await_count == 3


async def test_coordinator_classifies_transport_errors(
    hass, entry, client, status
) -> None:
    """Polling and command failures become HA-native errors."""
    coordinator = _coordinator(hass, entry, client, status)
    client.read_status = lambda: (_ for _ in ()).throw(
        NetworkTimeoutError(-4000, "timeout", "offline")
    )
    with pytest.raises(Exception, match="Error communicating"):
        await coordinator._async_update_data()

    client.set_time = lambda: (_ for _ in ()).throw(OSError("offline"))
    with pytest.raises(HomeAssistantError):
        await coordinator.async_command(client.set_time)


async def test_coordinator_authentication_and_clock_failures(
    hass, entry, client, status
) -> None:
    """Setup retry, reauth and best-effort clock branches are distinct."""
    coordinator = _coordinator(hass, entry, client, status)
    client.authenticate = lambda: (_ for _ in ()).throw(OSError("offline"))
    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_authenticate()

    client.authenticate = lambda: (_ for _ in ()).throw(
        FloureonAuthenticationError("rejected")
    )
    with pytest.raises(ConfigEntryNotReady):
        await coordinator.async_authenticate()

    from broadlink.exceptions import AuthenticationError

    auth_error = AuthenticationError(-4000, "auth", "rejected")
    client.authenticate = MagicMock(return_value=None)
    client.read_status = MagicMock(side_effect=[auth_error, status])
    assert await coordinator._async_update_data() == status
    client.authenticate.assert_called_once()

    command = MagicMock(side_effect=[auth_error, None])
    coordinator.async_request_refresh = AsyncMock()
    await coordinator.async_command(command)
    assert command.call_count == 2
    assert client.authenticate.call_count == 2

    coordinator.async_command = AsyncMock(side_effect=HomeAssistantError("clock"))
    await coordinator.async_set_time()


async def test_legacy_platforms_and_platform_selection(
    hass, entry, client, status
) -> None:
    """YAML delegates to import and only the selected modern platform adds."""
    flow = AsyncMock()
    with patch.object(hass.config_entries.flow, "async_init", flow):
        await async_setup_climate_platform(
            hass, {"host": "192.0.2.10", "name": "Old climate"}, MagicMock()
        )
        await async_setup_switch_platform(
            hass, {"host": "192.0.2.10", "name": "Old switch"}, MagicMock()
        )
    assert flow.await_count == 2

    coordinator = _coordinator(hass, entry, client, status)
    entry.runtime_data = coordinator
    add = MagicMock()
    await async_setup_climate_entry(hass, entry, add)
    assert add.call_count == 1

    entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        entry, options={CONF_ENTITY_TYPE: ENTITY_TYPE_SWITCH}
    )
    add.reset_mock()
    await async_setup_climate_entry(hass, entry, add)
    assert add.call_count == 0
    await async_setup_switch_entry(hass, entry, add)
    assert add.call_count == 1


async def test_diagnostics_redacts_identity(hass, entry, client, status) -> None:
    """Diagnostics include state but not network identity."""
    coordinator = _coordinator(hass, entry, client, status)
    coordinator.last_update_success = True
    entry.runtime_data = coordinator
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["status"]["target_temp"] == 23
    assert diagnostics["config_entry"]["data"]["host"] == "**REDACTED**"
