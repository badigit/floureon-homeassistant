"""Constants for the Floureon integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "floureon"
MANUFACTURER: Final = "Hysen"
MODEL: Final = "HY02/HY03"
DEFAULT_NAME: Final = "Floureon Thermostat"
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
MAX_SCAN_INTERVAL: Final = 3600
DEFAULT_TIMEOUT: Final = 3

CONF_ENTITY_TYPE: Final = "entity_type"
CONF_PRECISION: Final = "precision"
CONF_SCHEDULE: Final = "schedule"
CONF_TURN_OFF_MODE: Final = "turn_off_mode"
CONF_TURN_ON_MODE: Final = "turn_on_mode"
CONF_USE_COOLING: Final = "use_cooling"
CONF_USE_EXTERNAL_TEMP: Final = "use_external_temp"

ENTITY_TYPE_CLIMATE: Final = Platform.CLIMATE
ENTITY_TYPE_SWITCH: Final = Platform.SWITCH
DEFAULT_ENTITY_TYPE: Final = ENTITY_TYPE_CLIMATE
DEFAULT_PRECISION: Final = 0.5
DEFAULT_SCHEDULE: Final = 0
DEFAULT_USE_COOLING: Final = False
DEFAULT_USE_EXTERNAL_TEMP: Final = True

TURN_OFF: Final = "turn_off"
MIN_TEMP: Final = "min_temp"
MAX_TEMP: Final = "max_temp"
DEFAULT_TURN_OFF_MODE: Final = MIN_TEMP
DEFAULT_TURN_ON_MODE: Final = MAX_TEMP

POWER_ON: Final = 1
POWER_OFF: Final = 0
ACTIVE: Final = 1
IDLE: Final = 0
MODE_MANUAL: Final = 0
MODE_AUTO: Final = 1
SENSOR_INTERNAL: Final = 0
SENSOR_EXTERNAL: Final = 1
TEMP_AUTO: Final = 0
TEMP_MANUAL: Final = 1
SUPPORTED_DEVICE_TYPE: Final = 0x4EAD
