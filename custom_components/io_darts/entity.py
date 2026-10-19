"""Base entity of the IO-Darts integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IoDartsCoordinator


class IoDartsEntity(CoordinatorEntity[IoDartsCoordinator]):
    """Entity on the IO-Darts Board device."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: IoDartsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        unique_id = coordinator.config_entry.unique_id
        self._attr_unique_id = f"{unique_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, unique_id)})
