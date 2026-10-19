"""Webhook that receives pushes from the hub module."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import voluptuous as vol
from aiohttp import web
from homeassistant.core import HomeAssistant

from .const import EVENT_NAME, PUSH_TYPES, TAGS

if TYPE_CHECKING:
    from .coordinator import IoDartsCoordinator

MAX_STRING = 200
MAX_PLAYERS = 16

_SCALAR = vol.Any(None, bool, int, float, vol.All(str, vol.Length(max=MAX_STRING)))
_OPT_STR = vol.Any(None, vol.All(str, vol.Length(max=MAX_STRING)))
_OPT_NUM = vol.Any(None, int, float)

PLAYER_SCHEMA = vol.Schema(
    {
        vol.Required("index"): int,
        vol.Required("name"): vol.All(str, vol.Length(max=MAX_STRING)),
        vol.Required("score"): _OPT_NUM,
        vol.Required("legsWon"): int,
        vol.Required("setsWon"): int,
    },
    extra=vol.REMOVE_EXTRA,
)

STATE_SCHEMA = vol.Schema(
    {
        vol.Required("active"): bool,
        vol.Required("matchId"): _OPT_STR,
        vol.Required("variant"): _OPT_STR,
        vol.Required("mode"): vol.Any(None, vol.In(["x01", "cricket", "tactics", "other"])),
        vol.Required("round"): _OPT_NUM,
        vol.Required("currentPlayer"): vol.Any(None, PLAYER_SCHEMA),
        vol.Required("players"): vol.All([PLAYER_SCHEMA], vol.Length(max=MAX_PLAYERS)),
        vol.Required("lastThrow"): _OPT_STR,
        vol.Required("lastTurnPoints"): _OPT_NUM,
        vol.Required("winnerName"): _OPT_STR,
    },
    extra=vol.REMOVE_EXTRA,
)

PUSH_SCHEMA = vol.Schema(
    {
        vol.Required("v"): 1,
        vol.Required("type"): vol.In(PUSH_TYPES),
        vol.Required("ts"): vol.All(str, vol.Length(max=40)),
        vol.Required("tags"): vol.All([vol.In(TAGS)], vol.Length(max=len(TAGS))),
        vol.Required("data"): vol.All({vol.All(str, vol.Length(max=40)): _SCALAR}, vol.Length(max=20)),
        vol.Required("state"): STATE_SCHEMA,
    },
    extra=vol.REMOVE_EXTRA,
)


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
