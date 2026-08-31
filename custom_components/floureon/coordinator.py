"""Data coordinator for the Floureon integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any, TypeVar

from broadlink.exceptions import AuthenticationError, BroadlinkException
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryNotReady,
    HomeAssistantError,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FloureonApiClient, FloureonAuthenticationError, FloureonStatus
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

type FloureonConfigEntry = ConfigEntry["FloureonDataUpdateCoordinator"]
_T = TypeVar("_T")


class FloureonDataUpdateCoordinator(DataUpdateCoordinator[FloureonStatus]):
    """Serialise access to one blocking UDP thermostat."""

    config_entry: FloureonConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: FloureonConfigEntry,
        client: FloureonApiClient,
    ) -> None:
        self.client = client
        self._command_lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
            always_update=False,
        )

    async def _async_executor(self, call: Callable[[], _T]) -> _T:
        """Run a blocking Broadlink operation outside the event loop."""
        return await self.hass.async_add_executor_job(call)

    async def async_authenticate(self) -> None:
        """Authenticate during setup and classify failures."""
        try:
            await self._async_executor(self.client.authenticate)
        except (
            AuthenticationError,
            FloureonAuthenticationError,
            BroadlinkException,
            OSError,
        ) as err:
            raise ConfigEntryNotReady(f"Cannot connect to thermostat: {err}") from err

    async def _async_update_data(self) -> FloureonStatus:
        """Fetch the latest snapshot."""
        try:
            async with self._command_lock:
                return await self._async_executor(
                    lambda: self._call_with_reauthentication(self.client.read_status)
                )
        except (
            FloureonAuthenticationError,
            BroadlinkException,
            OSError,
            ValueError,
            TypeError,
        ) as err:
            raise UpdateFailed(f"Error communicating with thermostat: {err}") from err

    async def async_command(self, call: Callable[[], Any]) -> None:
        """Execute a command, then refresh the shared snapshot."""
        try:
            async with self._command_lock:
                await self._async_executor(
                    lambda: self._call_with_reauthentication(call)
                )
        except (
            FloureonAuthenticationError,
            BroadlinkException,
            OSError,
            ValueError,
            TypeError,
        ) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={"error": str(err)},
            ) from err
        await self.async_request_refresh()

    def _call_with_reauthentication(self, call: Callable[[], _T]) -> _T:
        """Retry one operation after renewing Broadlink's session key."""
        try:
            return call()
        except AuthenticationError:
            self.client.authenticate()
            return call()

    async def async_set_time(self) -> None:
        """Best-effort clock synchronisation after setup."""
        try:
            await self.async_command(self.client.set_time)
        except HomeAssistantError as err:
            _LOGGER.debug("Could not set thermostat time: %s", err)
