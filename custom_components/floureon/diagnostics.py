"""Diagnostics support for Floureon."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from .coordinator import FloureonConfigEntry

REDACT_CONFIG = {CONF_HOST, CONF_MAC, "unique_id"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FloureonConfigEntry
) -> dict[str, Any]:
    """Return a privacy-safe device snapshot."""
    coordinator = entry.runtime_data
    return {
        "config_entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "last_update_success": coordinator.last_update_success,
        "status": asdict(coordinator.data),
        "model": coordinator.client.model,
        "manufacturer": coordinator.client.manufacturer,
    }
