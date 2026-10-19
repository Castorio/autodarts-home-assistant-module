"""Tests for module switches and buttons."""

import pytest
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.io_darts.const import DOMAIN

from .const import ENTRY_DATA, MATCH, MODULES, STATUS, URL, routes


async def setup(hass, aioclient_mock, modules=MODULES):
    await async_process_ha_core_config(hass, {"internal_url": "http://192.168.41.10:8123"})
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True})
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    aioclient_mock.get(f"{URL}/api/modules", json=modules)
    aioclient_mock.post(routes("/webhook"), json={"registered": True, "changed": True})
    aioclient_mock.get(routes("/state"), json=MATCH)
    aioclient_mock.post(f"{URL}/api/modules/wled/stop", json={"success": True})
    aioclient_mock.post(f"{URL}/api/modules/darts-caller/start", json={"success": True})
    aioclient_mock.post(f"{URL}/api/modules/wled/restart", json={"success": True})
    aioclient_mock.post(f"{URL}/api/autodarts/connect", json={"success": True})
    aioclient_mock.post(f"{URL}/api/autodarts/disconnect", status=500, json={"success": False})
    aioclient_mock.post(f"{URL}/api/settings/restart", json={"success": True})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    entry = MockConfigEntry(domain=DOMAIN, unique_id="board-123", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def posted(aioclient_mock, path):
    return [c for c in aioclient_mock.mock_calls if c[0] == "POST" and str(c[1]) == f"{URL}{path}"]


async def test_module_switches(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    assert hass.states.get("switch.io_darts_board_wled_lighting_controller").state == "on"
    assert hass.states.get("switch.io_darts_board_darts_caller").state == "off"
    assert hass.states.get("switch.io_darts_board_home_assistant") is None

    await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.io_darts_board_wled_lighting_controller"}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.io_darts_board_darts_caller"}, blocking=True)
    assert len(posted(aioclient_mock, "/api/modules/wled/stop")) == 1
    assert len(posted(aioclient_mock, "/api/modules/darts-caller/start")) == 1


async def test_buttons(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    for entity_id in [
        "button.io_darts_board_connect_autodarts",
        "button.io_darts_board_restart_hub",
        "button.io_darts_board_restart_wled_lighting_controller",
    ]:
        await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    assert len(posted(aioclient_mock, "/api/autodarts/connect")) == 1
    assert len(posted(aioclient_mock, "/api/settings/restart")) == 1
    assert len(posted(aioclient_mock, "/api/modules/wled/restart")) == 1
    assert hass.states.get("button.io_darts_board_restart_home_assistant") is None


async def test_hub_error_is_raised(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("button", "press", {"entity_id": "button.io_darts_board_disconnect_autodarts"}, blocking=True)


async def test_malicious_module_id_raises_hassistanterror_not_crash(hass, aioclient_mock):
    """A hub reporting a module id that fails module_action's safe-path-segment regex
    must not make it onto the wire, and must not crash the entity with a raw
    ValueError: it should surface as a normal HomeAssistantError instead."""
    malicious = [{"id": "../etc/passwd", "name": "Evil", "status": "running", "version": "", "description": "", "events": []}]
    await setup(hass, aioclient_mock, modules=malicious)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("switch", "turn_off", {"entity_id": "switch.io_darts_board_evil"}, blocking=True)
    assert not posted(aioclient_mock, "/api/modules/../etc/passwd/stop")
