"""Tests for the trigger_intent service."""

import pytest
import voluptuous as vol
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.io_darts.const import DOMAIN

from .const import ENTRY_DATA, MATCH, MODULES, STATUS, URL, routes


async def setup(hass, aioclient_mock):
    await async_process_ha_core_config(hass, {"internal_url": "http://192.168.41.10:8123"})
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True})
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    aioclient_mock.get(f"{URL}/api/modules", json=MODULES)
    aioclient_mock.post(routes("/webhook"), json={"registered": True, "changed": True})
    aioclient_mock.get(routes("/state"), json=MATCH)
    aioclient_mock.post(routes("/intent"), json={"emitted": "homeassistant.trigger_3"})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    entry = MockConfigEntry(domain=DOMAIN, unique_id="board-123", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_trigger_intent(hass, aioclient_mock):
    await setup(hass, aioclient_mock)
    await hass.services.async_call(DOMAIN, "trigger_intent", {"slot": 3, "data": "party"}, blocking=True)
    call = [c for c in aioclient_mock.mock_calls if str(c[1]) == routes("/intent")][0]
    assert call[2] == {"slot": 3, "data": "party"}


@pytest.mark.parametrize("data", [{"slot": 0}, {"slot": 6}, {"slot": 1, "data": "x" * 201}])
async def test_trigger_intent_validation(hass, aioclient_mock, data):
    await setup(hass, aioclient_mock)
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(DOMAIN, "trigger_intent", data, blocking=True)


async def test_trigger_intent_without_hub(hass):
    assert await async_setup_component(hass, DOMAIN, {})
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "trigger_intent", {"slot": 1}, blocking=True)
