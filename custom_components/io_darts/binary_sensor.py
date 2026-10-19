"""Binary sensors of the IO-Darts integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoDartsConfigEntry
from .entity import IoDartsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: IoDartsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities([MatchActive(c, "match_active"), AutodartsConnected(c, "autodarts_connected"), HubReachable(c, "hub_reachable")])


class MatchActive(IoDartsEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.match.get("active"))


class AutodartsConnected(IoDartsEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        return bool((self.coordinator.data.status.get("autodarts") or {}).get("connected"))


class HubReachable(IoDartsEntity, BinarySensorEntity):
    """Stays available so it can report the hub as unreachable."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.coordinator.last_update_success
