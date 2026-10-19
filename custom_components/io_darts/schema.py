"""Schemas for match data from the hub module (webhook pushes and polled state).

Limits must match src/MatchTracker.ts (MAX_STRING, MAX_PLAYERS) in the hub module.
"""

from __future__ import annotations

import re

import voluptuous as vol

from .const import PUSH_TYPES, TAGS

MAX_STRING = 200
MAX_PLAYERS = 16

_SCALAR = vol.Any(None, bool, int, float, vol.All(str, vol.Length(max=MAX_STRING)))
_OPT_STR = vol.Any(None, vol.All(str, vol.Length(max=MAX_STRING)))
_OPT_NUM = vol.Any(None, int, float)

# No ^...$ anchors: Python's re `$` also matches just before a trailing "\n", which would
# let e.g. "#ef4444\n" through. fullmatch() (used below and in sensor.py) requires the
# whole string to match instead.
HEX_COLOR = re.compile(r"#[0-9a-f]{6}")


def _hex_color(value: object) -> str:
    if not isinstance(value, str) or not HEX_COLOR.fullmatch(value):
        raise vol.Invalid("not a valid #rrggbb hex color")
    return value


# Color fields are optional with a default of None so that payloads from older hub
# module versions (which don't send them yet) still validate.
_OPT_COLOR = vol.Any(None, _hex_color)

PLAYER_SCHEMA = vol.Schema(
    {
        vol.Required("index"): int,
        vol.Required("name"): vol.All(str, vol.Length(max=MAX_STRING)),
        vol.Required("score"): _OPT_NUM,
        vol.Required("legsWon"): int,
        vol.Required("setsWon"): int,
        vol.Optional("color", default=None): _OPT_COLOR,
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
        vol.Optional("currentPlayerColor", default=None): _OPT_COLOR,
        vol.Optional("nextPlayerColor", default=None): _OPT_COLOR,
    },
    extra=vol.REMOVE_EXTRA,
)

PUSH_SCHEMA = vol.Schema(
    {
        vol.Required("v"): 1,
        vol.Required("type"): vol.In(PUSH_TYPES),
        vol.Required("ts"): vol.All(str, vol.Length(max=40)),
        vol.Required("tags"): vol.All([vol.In(TAGS)], vol.Length(max=len(TAGS))),
        vol.Required("data"): vol.All(
            {
                vol.All(str, vol.Length(max=40)): _SCALAR,
                # player_changed carries these; they must be a valid hex color or None,
                # not just any scalar.
                vol.Optional("playerColor"): _OPT_COLOR,
                vol.Optional("nextPlayerColor"): _OPT_COLOR,
            },
            vol.Length(max=20),
        ),
        vol.Required("state"): STATE_SCHEMA,
    },
    extra=vol.REMOVE_EXTRA,
)
