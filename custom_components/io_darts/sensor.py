"""Sensors of the IO-Darts integration."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import IoDartsConfigEntry
from .coordinator import IoDartsCoordinator
from .entity import IoDartsEntity


def _current(c: IoDartsCoordinator) -> dict[str, Any]:
    return c.match.get("currentPlayer") or {}


def _players(c: IoDartsCoordinator) -> dict[str, Any]:
    return {
        "players": [
            {"name": p["name"], "score": p["score"], "legs_won": p["legsWon"], "sets_won": p["setsWon"]}
            for p in c.match.get("players", [])
        ]
    }


def _hub_started(c: IoDartsCoordinator) -> datetime | None:
    """Start time of the hub (now - uptime), truncated to the minute so it stays stable between polls."""
    uptime = c.data.status.get("uptime")
    if isinstance(uptime, bool) or not isinstance(uptime, (int, float)) or not 0 <= uptime < 10**10:
        return None
    started = dt_util.utcnow() - timedelta(seconds=uptime)
    return started.replace(second=0, microsecond=0)


@dataclass(frozen=True, kw_only=True)
class IoDartsSensorDescription(SensorEntityDescription):
    value_fn: Callable[[IoDartsCoordinator], Any]
    attrs_fn: Callable[[IoDartsCoordinator], dict[str, Any]] | None = None


SENSORS = (
    IoDartsSensorDescription(key="current_player", value_fn=lambda c: _current(c).get("name"), attrs_fn=_players),
    IoDartsSensorDescription(key="current_score", value_fn=lambda c: _current(c).get("score")),
    IoDartsSensorDescription(key="last_throw", value_fn=lambda c: c.match.get("lastThrow")),
    IoDartsSensorDescription(key="last_turn_points", value_fn=lambda c: c.match.get("lastTurnPoints")),
    IoDartsSensorDescription(key="variant", value_fn=lambda c: c.match.get("variant")),
    IoDartsSensorDescription(key="round", value_fn=lambda c: c.match.get("round")),
    IoDartsSensorDescription(
        key="hub_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda c: c.data.status.get("version"),
    ),
    IoDartsSensorDescription(
        key="hub_started",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_hub_started,
    ),
    IoDartsSensorDescription(
        key="running_modules",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda c: (c.data.status.get("modules") or {}).get("running"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: IoDartsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        [
            *(IoDartsSensor(coordinator, d) for d in SENSORS),
            PlayerColorSensor(coordinator, "current_player_color", "currentPlayerColor"),
            PlayerColorSensor(coordinator, "next_player_color", "nextPlayerColor"),
        ]
    )


class IoDartsSensor(IoDartsEntity, SensorEntity):
    entity_description: IoDartsSensorDescription

    def __init__(self, coordinator: IoDartsCoordinator, description: IoDartsSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator)


HEX_COLOR = re.compile(r"^#[0-9a-f]{6}$")


def _rgb(value: str) -> list[int]:
    return [int(value[i : i + 2], 16) for i in (1, 3, 5)]


class PlayerColorSensor(IoDartsEntity, RestoreSensor):
    """Color of the current or next player; keeps the last color outside a match."""

    def __init__(self, coordinator: IoDartsCoordinator, key: str, field: str) -> None:
        super().__init__(coordinator, key)
        self._field = field
        self._attr_native_value: str | None = None

    @property
    def available(self) -> bool:
        """Always available, so lights keep their color while the hub is away."""
        return True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_sensor_data()
        if last is not None and isinstance(last.native_value, str) and HEX_COLOR.match(last.native_value):
            self._attr_native_value = last.native_value
        self._take_color()

    def _take_color(self) -> None:
        match = self.coordinator.match
        value = match.get(self._field)
        if match.get("active") and isinstance(value, str) and HEX_COLOR.match(value):
            self._attr_native_value = value

    @callback
    def _handle_coordinator_update(self) -> None:
        self._take_color()
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        value = self._attr_native_value
        return {"rgb_color": _rgb(value)} if isinstance(value, str) else None
