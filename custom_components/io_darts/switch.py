"""Switches to start and stop hub modules."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoDartsConfigEntry
from .api import HubError
from .const import DOMAIN, MODULE_ID
from .coordinator import IoDartsCoordinator
from .entity import IoDartsEntity

RUNNING = {"running", "starting"}


async def async_setup_entry(
    hass: HomeAssistant, entry: IoDartsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new() -> None:
        new = [m for m in coordinator.data.modules if m["id"] != MODULE_ID and m["id"] not in known]
        known.update(m["id"] for m in new)
        async_add_entities(ModuleSwitch(coordinator, m["id"], m["name"]) for m in new)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class ModuleSwitch(IoDartsEntity, SwitchEntity):
    """On = module running."""

    def __init__(self, coordinator: IoDartsCoordinator, module_id: str, name: str) -> None:
        super().__init__(coordinator, f"module_{module_id}")
        self._attr_translation_key = None
        self._attr_name = name
        self._module_id = module_id

    def _module(self) -> dict[str, Any] | None:
        return next((m for m in self.coordinator.data.modules if m["id"] == self._module_id), None)

    @property
    def available(self) -> bool:
        return super().available and self._module() is not None

    @property
    def is_on(self) -> bool:
        module = self._module()
        return module is not None and module.get("status") in RUNNING

    async def _action(self, action: str) -> None:
        try:
            await self.coordinator.client.module_action(self._module_id, action)
        except (HubError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="hub_error", translation_placeholders={"error": str(err)}
            ) from err
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._action("start")

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._action("stop")
