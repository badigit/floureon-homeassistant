"""Floureon thermostat integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_TIMEOUT, CONF_TYPE, Platform
from homeassistant.core import HomeAssistant

from .api import FloureonApiClient
from .coordinator import FloureonConfigEntry, FloureonDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: FloureonConfigEntry) -> bool:
    """Set up a thermostat from a config entry."""
    client = FloureonApiClient.from_config(
        host=entry.data[CONF_HOST],
        mac=entry.data[CONF_MAC],
        dev_type=entry.data[CONF_TYPE],
        timeout=entry.data[CONF_TIMEOUT],
    )
    coordinator = FloureonDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_authenticate()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_set_time()
    return True


async def async_reload_entry(hass: HomeAssistant, entry: FloureonConfigEntry) -> None:
    """Reload an entry after its options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: FloureonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
