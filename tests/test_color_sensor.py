"""Tests for the player color sensors."""

from datetime import timedelta

from homeassistant.core import State
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from custom_components.io_darts.const import DOMAIN

from .const import ENTRY_DATA, MATCH, MODULES, STATUS, URL, WEBHOOK_ID, routes

CURRENT = "sensor.io_darts_board_current_player_color"
NEXT = "sensor.io_darts_board_next_player_color"


async def setup(hass, aioclient_mock, match=MATCH):
    await async_process_ha_core_config(hass, {"internal_url": "http://192.168.41.10:8123"})
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True})
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    aioclient_mock.get(f"{URL}/api/modules", json=MODULES)
    aioclient_mock.post(routes("/webhook"), json={"registered": True, "changed": True})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    aioclient_mock.get(routes("/state"), json=match)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="board-123", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def push(hass, hass_client_no_auth, state, type_="state"):
    client = await hass_client_no_auth()
    resp = await client.post(
        f"/api/webhook/{WEBHOOK_ID}",
        json={"v": 1, "type": type_, "ts": "t", "tags": [], "data": {}, "state": state},
    )
    await hass.async_block_till_done()
    return resp


async def test_colors_with_rgb(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    current = hass.states.get(CURRENT)
    assert current.state == "#ef4444"
    assert current.attributes["rgb_color"] == [239, 68, 68]
    assert hass.states.get(NEXT).state == "#3b82f6"
    assert hass.states.get(NEXT).attributes["rgb_color"] == [59, 130, 246]


async def test_colors_follow_pushes(hass, aioclient_mock, hass_client_no_auth):
    await setup(hass, aioclient_mock)
    await push(hass, hass_client_no_auth, {**MATCH, "currentPlayerColor": "#3b82f6", "nextPlayerColor": "#ef4444"}, "player_changed")
    assert hass.states.get(CURRENT).state == "#3b82f6"
    assert hass.states.get(NEXT).state == "#ef4444"


async def test_colors_stay_after_match_end(hass, aioclient_mock, hass_client_no_auth):
    await setup(hass, aioclient_mock)
    ended = {**MATCH, "active": False, "currentPlayer": None, "players": [], "currentPlayerColor": None, "nextPlayerColor": None}
    await push(hass, hass_client_no_auth, ended, "match_closed")
    assert hass.states.get(CURRENT).state == "#ef4444"
    assert hass.states.get(NEXT).state == "#3b82f6"


async def test_colors_stay_available_when_hub_is_down(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/status", status=500, json={})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    assert hass.states.get(CURRENT).state == "#ef4444"


async def test_colors_restored_after_restart(hass, aioclient_mock):
    mock_restore_cache_with_extra_data(
        hass,
        (
            (State(CURRENT, "#00ff00"), {"native_value": "#00ff00", "native_unit_of_measurement": None}),
            (State(NEXT, "#0000ff"), {"native_value": "#0000ff", "native_unit_of_measurement": None}),
        ),
    )
    await setup(hass, aioclient_mock, {**MATCH, "active": False})
    assert hass.states.get(CURRENT).state == "#00ff00"
    assert hass.states.get(CURRENT).attributes["rgb_color"] == [0, 255, 0]
    assert hass.states.get(NEXT).state == "#0000ff"


async def test_unknown_before_first_color(hass, aioclient_mock):
    await setup(hass, aioclient_mock, {**MATCH, "active": False, "currentPlayerColor": None, "nextPlayerColor": None})
    assert hass.states.get(CURRENT).state == "unknown"
    assert "rgb_color" not in hass.states.get(CURRENT).attributes
