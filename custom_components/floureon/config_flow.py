"""Config flow for Floureon thermostats."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from broadlink.exceptions import AuthenticationError, BroadlinkException
from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_TYPE,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv

from .api import (
    FloureonApiClient,
    FloureonAuthenticationError,
    UnsupportedDeviceError,
)
from .const import (
    CONF_ENTITY_TYPE,
    CONF_PRECISION,
    CONF_SCHEDULE,
    CONF_TURN_OFF_MODE,
    CONF_TURN_ON_MODE,
    CONF_USE_COOLING,
    CONF_USE_EXTERNAL_TEMP,
    DEFAULT_ENTITY_TYPE,
    DEFAULT_NAME,
    DEFAULT_PRECISION,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCHEDULE,
    DEFAULT_TIMEOUT,
    DEFAULT_TURN_OFF_MODE,
    DEFAULT_TURN_ON_MODE,
    DEFAULT_USE_COOLING,
    DEFAULT_USE_EXTERNAL_TEMP,
    DOMAIN,
    ENTITY_TYPE_CLIMATE,
    ENTITY_TYPE_SWITCH,
    MAX_SCAN_INTERVAL,
    MAX_TEMP,
    MIN_SCAN_INTERVAL,
    MIN_TEMP,
    TURN_OFF,
)


def _base_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST)): cv.string,
            vol.Optional(
                CONF_TIMEOUT, default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
            vol.Optional(
                CONF_ENTITY_TYPE,
                default=defaults.get(CONF_ENTITY_TYPE, DEFAULT_ENTITY_TYPE),
            ): vol.In([ENTITY_TYPE_CLIMATE, ENTITY_TYPE_SWITCH]),
        }
    )


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    schema: dict[Any, Any] = {
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
        ): vol.All(
            vol.Coerce(int),
            vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
        ),
        vol.Optional(
            CONF_ENTITY_TYPE,
            default=defaults.get(CONF_ENTITY_TYPE, DEFAULT_ENTITY_TYPE),
        ): vol.In([ENTITY_TYPE_CLIMATE, ENTITY_TYPE_SWITCH]),
        vol.Optional(
            CONF_USE_EXTERNAL_TEMP,
            default=defaults.get(CONF_USE_EXTERNAL_TEMP, DEFAULT_USE_EXTERNAL_TEMP),
        ): cv.boolean,
    }
    if defaults.get(CONF_ENTITY_TYPE, DEFAULT_ENTITY_TYPE) == ENTITY_TYPE_SWITCH:
        schema.update(
            {
                vol.Optional(
                    CONF_TURN_OFF_MODE,
                    default=defaults.get(CONF_TURN_OFF_MODE, DEFAULT_TURN_OFF_MODE),
                ): vol.Any(
                    vol.In([MIN_TEMP, TURN_OFF]),
                    vol.All(vol.Coerce(float), vol.Range(min=5, max=99)),
                ),
                vol.Optional(
                    CONF_TURN_ON_MODE,
                    default=defaults.get(CONF_TURN_ON_MODE, DEFAULT_TURN_ON_MODE),
                ): vol.Any(
                    vol.In([MAX_TEMP]),
                    vol.All(vol.Coerce(float), vol.Range(min=5, max=99)),
                ),
            }
        )
    else:
        schema.update(
            {
                vol.Optional(
                    CONF_SCHEDULE,
                    default=defaults.get(CONF_SCHEDULE, DEFAULT_SCHEDULE),
                ): vol.All(vol.Coerce(int), vol.Range(min=0, max=2)),
                vol.Optional(
                    CONF_PRECISION,
                    default=defaults.get(CONF_PRECISION, DEFAULT_PRECISION),
                ): vol.In([0.5, 1.0]),
                vol.Optional(
                    CONF_USE_COOLING,
                    default=defaults.get(CONF_USE_COOLING, DEFAULT_USE_COOLING),
                ): cv.boolean,
            }
        )
    return vol.Schema(schema)


class FloureonConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle discovery and setup."""

    VERSION = 1

    def __init__(self) -> None:
        self._client: FloureonApiClient | None = None
        self._input: dict[str, Any] = {}

    async def _async_connect(self, user_input: dict[str, Any]) -> str | None:
        """Discover, validate and authenticate a device."""
        try:
            client = await self.hass.async_add_executor_job(
                FloureonApiClient.discover,
                user_input[CONF_HOST],
                user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            )
            await self.hass.async_add_executor_job(client.authenticate)
            await self.hass.async_add_executor_job(client.read_status)
        except UnsupportedDeviceError:
            return "not_supported"
        except (AuthenticationError, FloureonAuthenticationError):
            return "invalid_auth"
        except (BroadlinkException, OSError):
            return "cannot_connect"
        except Exception:  # noqa: BLE001 - config flow must keep the form open
            return "unknown"
        self._client = client
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Set up a thermostat entered by the user."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._input = dict(user_input)
            if error := await self._async_connect(user_input):
                errors["base"] = error
            else:
                return await self._async_finish()
        return self.async_show_form(
            step_id="user", data_schema=_base_schema(user_input or {}), errors=errors
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> FlowResult:
        """Import a legacy YAML climate or switch platform."""
        self._input = dict(import_data)
        # Older releases offered 0.1 °C even though Hysen's target register
        # stores half-degrees. Do not keep offering values the device truncates.
        if self._input.get(CONF_PRECISION) == 0.1:
            self._input[CONF_PRECISION] = DEFAULT_PRECISION
        self._input.setdefault(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        self._input.setdefault(CONF_ENTITY_TYPE, DEFAULT_ENTITY_TYPE)
        if error := await self._async_connect(self._input):
            return self.async_abort(reason=error)
        return await self._async_finish()

    async def _async_finish(self) -> FlowResult:
        """Create the entry once the device has been validated."""
        assert self._client is not None
        await self.async_set_unique_id(self._client.mac)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: self._client.host,
                CONF_TIMEOUT: self._input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            }
        )
        data = {
            CONF_HOST: self._client.host,
            CONF_MAC: self._client.mac,
            CONF_TYPE: self._client.dev_type,
            CONF_TIMEOUT: self._input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
        }
        option_keys = {
            CONF_SCAN_INTERVAL,
            CONF_ENTITY_TYPE,
            CONF_USE_EXTERNAL_TEMP,
            CONF_SCHEDULE,
            CONF_PRECISION,
            CONF_USE_COOLING,
            CONF_TURN_OFF_MODE,
            CONF_TURN_ON_MODE,
        }
        option_input = {
            key: value for key, value in self._input.items() if key in option_keys
        }
        options = _options_schema(option_input)(option_input)
        title = self._input.get(CONF_NAME) or f"{DEFAULT_NAME} {self._client.mac[-6:]}"
        return self.async_create_entry(title=title, data=data, options=options)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> FloureonOptionsFlow:
        """Return the options flow."""
        return FloureonOptionsFlow()


class FloureonOptionsFlow(config_entries.OptionsFlow):
    """Edit runtime options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Show and save integration options."""
        if user_input is not None:
            # Changing climate/switch reveals its specific fields on a second
            # pass instead of silently filling hidden defaults.
            current_type = self.config_entry.options.get(
                CONF_ENTITY_TYPE, DEFAULT_ENTITY_TYPE
            )
            if user_input[CONF_ENTITY_TYPE] != current_type:
                defaults = dict(self.config_entry.options)
                defaults.update(user_input)
                return self.async_show_form(
                    step_id="init", data_schema=_options_schema(defaults)
                )
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(dict(self.config_entry.options)),
        )
