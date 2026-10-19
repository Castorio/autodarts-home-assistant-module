"""Buttons for hub and module actions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IoDartsConfigEntry
from .api import HubClient, HubError
from .const import DOMAIN, MODULE_ID
from .coordinator import IoDartsCoordinator
from .entity import IoDartsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: IoDartsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    c = entry.runtime_data
    async_add_entities(
        [
            HubButton(c, "autodarts_connect", lambda client: client.autodarts("connect")),
            HubButton(c, "autodarts_disconnect", lambda client: client.autodarts("disconnect")),
            HubButton(c, "hub_restart", lambda client: client.restart_hub(), ButtonDeviceClass.RESTART),
        ]
    )
    known: set[str] = set()

    @callback
    def add_new() -> None:
        new = [m for m in c.data.modules if m["id"] != MODULE_ID and m["id"] not in known]
        known.update(m["id"] for m in new)
        async_add_entities(ModuleRestartButton(c, m["id"], m["name"]) for m in new)

    add_new()
    entry.async_on_unload(c.async_add_listener(add_new))


class HubButton(IoDartsEntity, ButtonEntity):
    def __init__(
        self,
        coordinator: IoDartsCoordinator,
        key: str,
        press: Callable[[HubClient], Awaitable[None]],
        device_class: ButtonDeviceClass | None = None,
    ) -> None:
        super().__init__(coordinator, key)
        self._press = press
        self._attr_device_class = device_class

    async def async_press(self) -> None:
        try:
            await self._press(self.coordinator.client)
        except (HubError, ValueError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="hub_error", translation_placeholders={"error": str(err)}
            ) from err


class ModuleRestartButton(HubButton):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: IoDartsCoordinator, module_id: str, name: str) -> None:
        super().__init__(
            coordinator,
            f"module_restart_{module_id}",
            lambda client: client.module_action(module_id, "restart"),
            ButtonDeviceClass.RESTART,
        )
        self._attr_translation_key = "module_restart"
        self._attr_translation_placeholders = {"module": name}
