"""Tests for setup, polling and unload."""

from datetime import timedelta

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.io_darts.const import DOMAIN

from .const import ENTRY_DATA, MATCH, MODULES, STATUS, URL, WEBHOOK_ID, routes

HA_URL = "http://192.168.41.10:8123"


@pytest.fixture
async def ha_url(hass):
    await async_process_ha_core_config(hass, {"internal_url": HA_URL})


def mock_hub(aioclient_mock, changed=True, state=MATCH):
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True}, cookies={"autodarts_session": "sid"})
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    aioclient_mock.get(f"{URL}/api/modules", json=MODULES)
    aioclient_mock.post(routes("/webhook"), json={"registered": True, "changed": changed})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    aioclient_mock.get(routes("/state"), json=state)


async def setup_entry(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="board-123", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def calls(aioclient_mock, method, url):
    return [c for c in aioclient_mock.mock_calls if c[0] == method and str(c[1]) == url]


async def test_setup_registers_webhook_and_device(hass, aioclient_mock, ha_url):
    mock_hub(aioclient_mock)
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED
    posted = calls(aioclient_mock, "POST", routes("/webhook"))
    assert posted[0][2] == {"url": f"{HA_URL}/api/webhook/{WEBHOOK_ID}"}
    assert entry.runtime_data.match == MATCH
    device = dr.async_get(hass).async_get_device_by_identifier((DOMAIN, "board-123"), entry.entry_id)
    assert device.name == "IO-Darts Board"
    assert device.sw_version == "1.2.0"
    assert entry.runtime_data.device_id == device.id


async def test_setup_fetches_state_even_if_webhook_is_unchanged(hass, aioclient_mock, ha_url):
    mock_hub(aioclient_mock, changed=False)
    entry = await setup_entry(hass)
    assert entry.runtime_data.match == MATCH


async def poll(hass):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=31))
    await hass.async_block_till_done()


async def test_reregisters_on_every_poll_without_refetching_unchanged_state(hass, aioclient_mock, ha_url):
    mock_hub(aioclient_mock, changed=False)
    await setup_entry(hass)
    aioclient_mock.clear_requests()
    mock_hub(aioclient_mock, changed=False)
    await poll(hass)
    assert len(calls(aioclient_mock, "POST", routes("/webhook"))) == 1
    assert calls(aioclient_mock, "GET", routes("/state")) == []
    assert calls(aioclient_mock, "GET", routes("/webhook")) == []


async def test_refetches_state_when_the_registration_changed(hass, aioclient_mock, ha_url):
    """The module restarted or someone re-pointed the webhook: our URL wins again."""
    mock_hub(aioclient_mock, changed=False)
    entry = await setup_entry(hass)
    aioclient_mock.clear_requests()
    newer = {**MATCH, "round": 7}
    mock_hub(aioclient_mock, changed=True, state=newer)
    await poll(hass)
    posted = calls(aioclient_mock, "POST", routes("/webhook"))
    assert posted[0][2] == {"url": f"{HA_URL}/api/webhook/{WEBHOOK_ID}"}
    assert len(calls(aioclient_mock, "GET", routes("/state"))) == 1
    assert entry.runtime_data.match == newer


async def test_module_missing_creates_issue(hass, aioclient_mock, ha_url):
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True})
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    aioclient_mock.get(f"{URL}/api/modules", json=MODULES)
    aioclient_mock.post(routes("/webhook"), status=404, json={})
    aioclient_mock.delete(routes("/webhook"), status=404, json={})
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.LOADED
    assert ir.async_get(hass).async_get_issue(DOMAIN, "module_missing") is not None


async def test_hub_down_retries_setup(hass, aioclient_mock, ha_url):
    aioclient_mock.post(f"{URL}/api/auth/login", status=500, json={})
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_wrong_password_starts_reauth(hass, aioclient_mock, ha_url):
    aioclient_mock.post(f"{URL}/api/auth/login", status=401, json={})
    entry = await setup_entry(hass)
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert any(f["context"]["source"] == "reauth" for f in hass.config_entries.flow.async_progress())


async def test_unload_unregisters(hass, aioclient_mock, ha_url):
    mock_hub(aioclient_mock)
    entry = await setup_entry(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert len(calls(aioclient_mock, "DELETE", routes("/webhook"))) == 1
