"""Tests for sensors and binary sensors."""

from datetime import timedelta

from homeassistant.core_config import async_process_ha_core_config
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.io_darts.const import DOMAIN

from .const import ENTRY_DATA, MATCH, MODULES, STATUS, URL, WEBHOOK_ID, routes


async def setup(hass, aioclient_mock):
    await async_process_ha_core_config(hass, {"internal_url": "http://192.168.41.10:8123"})
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True})
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    aioclient_mock.get(f"{URL}/api/modules", json=MODULES)
    aioclient_mock.post(routes("/webhook"), json={"registered": True, "changed": True})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    aioclient_mock.get(routes("/state"), json=MATCH)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="board-123", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_match_sensors(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    assert hass.states.get("sensor.io_darts_board_current_player").state == "Bob"
    players = hass.states.get("sensor.io_darts_board_current_player").attributes["players"]
    assert players[0] == {"name": "Alice", "score": 301, "legs_won": 1, "sets_won": 0}
    assert hass.states.get("sensor.io_darts_board_current_score").state == "241"
    assert hass.states.get("sensor.io_darts_board_last_throw").state == "T20"
    assert hass.states.get("sensor.io_darts_board_last_turn").state == "100"
    assert hass.states.get("sensor.io_darts_board_game_variant").state == "X01"
    assert hass.states.get("sensor.io_darts_board_round").state == "3"
    assert hass.states.get("binary_sensor.io_darts_board_match_active").state == "on"


async def test_hub_sensors(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    assert hass.states.get("binary_sensor.io_darts_board_autodarts_connected").state == "on"
    assert hass.states.get("binary_sensor.io_darts_board_hub_reachable").state == "on"
    assert hass.states.get("sensor.io_darts_board_hub_version").state == "1.2.0"
    assert hass.states.get("sensor.io_darts_board_hub_uptime").state == "3600"
    assert hass.states.get("sensor.io_darts_board_running_modules").state == "2"


async def test_push_updates_sensors(hass, aioclient_mock, hass_client_no_auth):
    await setup(hass, aioclient_mock)
    client = await hass_client_no_auth()
    state = {**MATCH, "lastThrow": "D16", "currentPlayer": MATCH["players"][0]}
    await client.post(
        f"/api/webhook/{WEBHOOK_ID}",
        json={"v": 1, "type": "throw", "ts": "t", "tags": ["double"], "data": {}, "state": state},
    )
    await hass.async_block_till_done()
    assert hass.states.get("sensor.io_darts_board_last_throw").state == "D16"
    assert hass.states.get("sensor.io_darts_board_current_player").state == "Alice"


async def test_hub_down(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{URL}/api/status", status=500, json={})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.io_darts_board_hub_reachable").state == "off"
    assert hass.states.get("sensor.io_darts_board_current_player").state == "unavailable"
