"""Climate entity for Floureon thermostats."""

from __future__ import annotations

from functools import partial
from typing import Any, ClassVar

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.climate.const import PRESET_AWAY, PRESET_NONE
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_HOST,
    CONF_NAME,
    CONF_TIMEOUT,
    CONF_UNIQUE_ID,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_ENTITY_TYPE,
    CONF_PRECISION,
    CONF_SCHEDULE,
    CONF_USE_COOLING,
    CONF_USE_EXTERNAL_TEMP,
    DEFAULT_ENTITY_TYPE,
    DEFAULT_PRECISION,
    DEFAULT_SCHEDULE,
    DEFAULT_TIMEOUT,
    DEFAULT_USE_COOLING,
    DEFAULT_USE_EXTERNAL_TEMP,
    DOMAIN,
    ENTITY_TYPE_CLIMATE,
    MODE_AUTO,
    MODE_MANUAL,
    POWER_OFF,
    POWER_ON,
    SENSOR_EXTERNAL,
    SENSOR_INTERNAL,
    TEMP_MANUAL,
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
        vol.Optional(CONF_SCHEDULE, default=DEFAULT_SCHEDULE): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=2)
        ),
        vol.Optional(
            CONF_USE_EXTERNAL_TEMP, default=DEFAULT_USE_EXTERNAL_TEMP
        ): cv.boolean,
        vol.Optional(CONF_PRECISION, default=DEFAULT_PRECISION): vol.In(
            [0.1, 0.5, 1.0]
        ),
        vol.Optional(CONF_USE_COOLING, default=DEFAULT_USE_COOLING): cv.boolean,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: dict[str, Any] | None = None,
) -> None:
    """Import a legacy YAML platform into a config entry."""
    data = dict(config)
    data[CONF_ENTITY_TYPE] = ENTITY_TYPE_CLIMATE
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
    """Set up the climate entity selected in options."""
    if entry.options.get(CONF_ENTITY_TYPE, DEFAULT_ENTITY_TYPE) != ENTITY_TYPE_CLIMATE:
        return
    async_add_entities([FloureonClimate(entry.runtime_data)])


class FloureonClimate(FloureonEntity, ClimateEntity, RestoreEntity):
    """Represent a local Floureon/Hysen thermostat."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_preset_modes: ClassVar[list[str]] = [PRESET_NONE, PRESET_AWAY]

    def __init__(self, coordinator: FloureonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        options = coordinator.config_entry.options
        self._schedule = options.get(CONF_SCHEDULE, DEFAULT_SCHEDULE)
        self._use_external_temp = options.get(
            CONF_USE_EXTERNAL_TEMP, DEFAULT_USE_EXTERNAL_TEMP
        )
        self._use_cooling = options.get(CONF_USE_COOLING, DEFAULT_USE_COOLING)
        self._attr_precision = options.get(CONF_PRECISION, DEFAULT_PRECISION)
        self._attr_target_temperature_step = self._attr_precision
        self._preset_mode = PRESET_NONE
        target = coordinator.data.target_temp
        self._manual_set_point = target
        self._away_set_point = coordinator.data.min_temp

    @property
    def _sensor(self) -> int:
        return SENSOR_EXTERNAL if self._use_external_temp else SENSOR_INTERNAL

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return modes supported by the configured thermostat."""
        active = HVACMode.HEAT_COOL if self._use_cooling else HVACMode.HEAT
        return [HVACMode.AUTO, active, HVACMode.OFF]

    @property
    def hvac_mode(self) -> HVACMode:
        """Return the physical controller mode."""
        data = self.coordinator.data
        if not data.power:
            return HVACMode.OFF
        if data.auto_mode == MODE_MANUAL or data.temp_manual == TEMP_MANUAL:
            return HVACMode.HEAT_COOL if self._use_cooling else HVACMode.HEAT
        return HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction:
        """Return whether the output is active."""
        data = self.coordinator.data
        if not data.power:
            return HVACAction.OFF
        if not data.active:
            return HVACAction.IDLE
        if self._use_cooling and data.heating_cooling:
            return HVACAction.COOLING
        return HVACAction.HEATING

    @property
    def current_temperature(self) -> float | None:
        """Return the configured control sensor reading."""
        data = self.coordinator.data
        return data.external_temp if self._use_external_temp else data.room_temp

    @property
    def target_temperature(self) -> float | None:
        """Return the physical target temperature."""
        return self.coordinator.data.target_temp

    @property
    def min_temp(self) -> float:
        """Return the device-provided lower limit."""
        return self.coordinator.data.min_temp or super().min_temp

    @property
    def max_temp(self) -> float:
        """Return the device-provided upper limit."""
        return self.coordinator.data.max_temp or super().max_temp

    @property
    def preset_mode(self) -> str:
        """Return the local convenience preset."""
        return self._preset_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose useful protocol diagnostics without duplicating HA fields."""
        data = self.coordinator.data
        return {
            "away_set_point": self._away_set_point,
            "manual_set_point": self._manual_set_point,
            "room_temperature": data.room_temp,
            "external_temperature": data.external_temp,
            "hysteresis": data.hysteresis,
            "control_sensor": "external" if self._use_external_temp else "internal",
            "schedule": data.loop_mode,
        }

    async def async_added_to_hass(self) -> None:
        """Restore local away/manual set points."""
        await super().async_added_to_hass()
        if (state := await self.async_get_last_state()) is None:
            return
        self._away_set_point = state.attributes.get(
            "away_set_point", self._away_set_point
        )
        self._manual_set_point = state.attributes.get(
            "manual_set_point", self._manual_set_point
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Switch to manual mode and set a target."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        target = float(temperature)
        await self.coordinator.async_command(
            partial(
                self.coordinator.client.set_manual_temperature,
                target,
                self._schedule,
                self._sensor,
            )
        )
        if self._preset_mode == PRESET_AWAY:
            self._away_set_point = target
        else:
            self._manual_set_point = target

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set automatic, manual or off mode."""
        if hvac_mode not in self.hvac_modes:
            raise ValueError(f"Unsupported HVAC mode: {hvac_mode}")
        power = POWER_OFF if hvac_mode is HVACMode.OFF else POWER_ON
        mode = MODE_AUTO if hvac_mode is HVACMode.AUTO else MODE_MANUAL
        cooling = self._use_cooling and hvac_mode is not HVACMode.OFF
        await self.coordinator.async_command(
            partial(
                self.coordinator.client.set_hvac_mode,
                power=power,
                mode=mode,
                schedule=self._schedule,
                sensor=self._sensor,
                cooling=cooling,
            )
        )
        if hvac_mode in (HVACMode.AUTO, HVACMode.OFF):
            self._preset_mode = PRESET_NONE

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Apply the remembered away or manual target."""
        if preset_mode not in self.preset_modes:
            raise ValueError(f"Unsupported preset: {preset_mode}")
        target = (
            self._away_set_point
            if preset_mode == PRESET_AWAY
            else self._manual_set_point
        )
        if target is None:
            target = self.coordinator.data.target_temp or self.min_temp
        self._preset_mode = preset_mode
        await self.coordinator.async_command(
            partial(
                self.coordinator.client.set_preset_temperature,
                float(target),
                self._schedule,
                self._sensor,
                cooling=self._use_cooling,
            )
        )

    async def async_turn_on(self) -> None:
        """Restore automatic operation."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        """Turn the thermostat off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
