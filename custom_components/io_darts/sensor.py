"""Sensors of the IO-Darts integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
        key="uptime",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda c: c.data.status.get("uptime"),
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
    async_add_entities(IoDartsSensor(entry.runtime_data, d) for d in SENSORS)


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
