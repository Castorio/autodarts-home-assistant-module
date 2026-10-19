"""Webhook that receives pushes from the hub module."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import voluptuous as vol
from aiohttp import web
from homeassistant.core import HomeAssistant

from .const import EVENT_NAME
from .schema import PUSH_SCHEMA

if TYPE_CHECKING:
    from .coordinator import IoDartsCoordinator


def make_webhook_handler(
    coordinator: IoDartsCoordinator,
) -> Callable[[HomeAssistant, str, web.Request], Awaitable[web.Response]]:
    """Webhook handler bound to one config entry."""

    async def handle(hass: HomeAssistant, webhook_id: str, request: web.Request) -> web.Response:
        try:
            payload = PUSH_SCHEMA(await request.json())
        except (ValueError, vol.Invalid):
            return web.Response(status=400)
        coordinator.handle_push(payload)
        if payload["type"] != "state":
            hass.bus.async_fire(
                EVENT_NAME,
                {
                    **payload["data"],
                    "device_id": coordinator.device_id,
                    "type": payload["type"],
                    "tags": payload["tags"],
                },
            )
        return web.Response(status=200)

    return handle
