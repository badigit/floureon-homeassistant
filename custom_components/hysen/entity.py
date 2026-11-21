"""Shared entity support for Floureon."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FloureonDataUpdateCoordinator


class FloureonEntity(CoordinatorEntity[FloureonDataUpdateCoordinator]):
    """Base entity tied to one thermostat coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FloureonDataUpdateCoordinator) -> None:
        super().__init__(coordinator)
        client = coordinator.client
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, client.mac)},
            name=coordinator.config_entry.title,
            manufacturer=client.manufacturer,
            model=client.model,
        )
        self._attr_unique_id = client.mac
        self._attr_name = None
