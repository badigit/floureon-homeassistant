"""Legacy switch-mode entity for Floureon thermostats."""

from __future__ import annotations

from functools import partial
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.climate.const import DEFAULT_MAX_TEMP, DEFAULT_MIN_TEMP
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)

from .const import (
    CONF_ENTITY_TYPE,
    CONF_TURN_OFF_MODE,
    CONF_TURN_ON_MODE,
    CONF_USE_EXTERNAL_TEMP,
    DEFAULT_ENTITY_TYPE,
    DEFAULT_TIMEOUT,
    DEFAULT_TURN_OFF_MODE,
    DEFAULT_TURN_ON_MODE,
    DEFAULT_USE_EXTERNAL_TEMP,
    DOMAIN,
    ENTITY_TYPE_SWITCH,
    MAX_TEMP,
    MIN_TEMP,
    POWER_OFF,
    POWER_ON,
    SENSOR_EXTERNAL,
    SENSOR_INTERNAL,
    TURN_OFF,
)
from .coordinator import FloureonConfigEntry, FloureonDataUpdateCoordinator
from .entity import FloureonEntity

PARALLEL_UPDATES = 1

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional(CONF_UNIQUE_ID): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=30)
        ),
        vol.Optional(
            CONF_USE_EXTERNAL_TEMP, default=DEFAULT_USE_EXTERNAL_TEMP
        ): cv.boolean,
        vol.Optional(CONF_TURN_OFF_MODE, default=DEFAULT_TURN_OFF_MODE): vol.Any(
            vol.In([MIN_TEMP, TURN_OFF]),
            vol.All(vol.Coerce(float), vol.Range(min=5, max=99)),
        ),
        vol.Optional(CONF_TURN_ON_MODE, default=DEFAULT_TURN_ON_MODE): vol.Any(
            vol.In([MAX_TEMP]),
            vol.All(vol.Coerce(float), vol.Range(min=5, max=99)),
        ),
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Import a legacy YAML switch platform."""
    data = dict(config)
    data[CONF_ENTITY_TYPE] = ENTITY_TYPE_SWITCH
    await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=data,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FloureonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up switch mode when selected in options."""
    if entry.options.get(CONF_ENTITY_TYPE, DEFAULT_ENTITY_TYPE) != ENTITY_TYPE_SWITCH:
        return
    async_add_entities([FloureonSwitch(entry.runtime_data)])


class FloureonSwitch(FloureonEntity, SwitchEntity):
    """Expose active heating as a simple on/off switch."""

    def __init__(self, coordinator: FloureonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        options = coordinator.config_entry.options
        self._use_external_temp = options.get(
            CONF_USE_EXTERNAL_TEMP, DEFAULT_USE_EXTERNAL_TEMP
        )
        self._turn_off_mode = options.get(CONF_TURN_OFF_MODE, DEFAULT_TURN_OFF_MODE)
        self._turn_on_mode = options.get(CONF_TURN_ON_MODE, DEFAULT_TURN_ON_MODE)

    @property
    def is_on(self) -> bool:
        """Return whether the thermostat is actively heating/cooling."""
        data = self.coordinator.data
        return data.power and data.active

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose temperatures relevant to switch automations."""
        data = self.coordinator.data
        return {
            "room_temperature": data.room_temp,
            "external_temperature": data.external_temp,
            "current_temperature": (
                data.external_temp if self._use_external_temp else data.room_temp
            ),
            "target_temperature": data.target_temp,
        }

    @property
    def _sensor(self) -> int:
        return SENSOR_EXTERNAL if self._use_external_temp else SENSOR_INTERNAL

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Power on and apply the configured on temperature."""
        data = self.coordinator.data
        temperature = (
            data.max_temp or DEFAULT_MAX_TEMP
            if self._turn_on_mode == MAX_TEMP
            else float(self._turn_on_mode)
        )
        await self.coordinator.async_command(
            partial(
                self.coordinator.client.set_switch_state,
                power=POWER_ON,
                temperature=temperature,
                schedule=data.loop_mode or 0,
                sensor=self._sensor,
            )
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Power off or lower the set point, matching legacy semantics."""
        data = self.coordinator.data
        if self._turn_off_mode == TURN_OFF:
            power = POWER_OFF
            temperature = None
        else:
            power = POWER_ON
            temperature = (
                data.min_temp or DEFAULT_MIN_TEMP
                if self._turn_off_mode == MIN_TEMP
                else float(self._turn_off_mode)
            )
        await self.coordinator.async_command(
            partial(
                self.coordinator.client.set_switch_state,
                power=power,
                temperature=temperature,
                schedule=data.loop_mode or 0,
                sensor=self._sensor,
            )
        )
