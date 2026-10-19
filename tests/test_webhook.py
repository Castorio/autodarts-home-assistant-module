"""Tests for the webhook push."""

from homeassistant.core_config import async_process_ha_core_config
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.io_darts.const import DOMAIN, EVENT_NAME

from .const import ENTRY_DATA, MATCH, MODULES, STATUS, URL, WEBHOOK_ID, routes


async def setup(hass, aioclient_mock):
    await async_process_ha_core_config(hass, {"internal_url": "http://192.168.41.10:8123"})
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True})
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    aioclient_mock.get(f"{URL}/api/modules", json=MODULES)
    aioclient_mock.get(routes("/webhook"), json={"registered": False})
    aioclient_mock.post(routes("/webhook"), json={"registered": True})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    aioclient_mock.get(routes("/state"), json={**MATCH, "active": False})
    entry = MockConfigEntry(domain=DOMAIN, unique_id="board-123", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def push(type_="throw", tags=None, data=None, state=None):
    return {
        "v": 1,
        "type": type_,
        "ts": "2026-10-19T12:00:00.000Z",
        "tags": tags or [],
        "data": data or {},
        "state": state or MATCH,
    }


async def test_push_updates_state_and_fires_event(hass, aioclient_mock, hass_client_no_auth):
    entry = await setup(hass, aioclient_mock)
    events = async_capture_events(hass, EVENT_NAME)
    client = await hass_client_no_auth()
    resp = await client.post(
        f"/api/webhook/{WEBHOOK_ID}",
        json=push(tags=["180", "triple"], data={"segment": "T20", "points": 60}),
    )
    await hass.async_block_till_done()
    assert resp.status == 200
    assert entry.runtime_data.match["active"] is True
    assert len(events) == 1
    assert events[0].data == {
        "segment": "T20",
        "points": 60,
        "device_id": entry.runtime_data.device_id,
        "type": "throw",
        "tags": ["180", "triple"],
    }


async def test_state_push_fires_no_event(hass, aioclient_mock, hass_client_no_auth):
    await setup(hass, aioclient_mock)
    events = async_capture_events(hass, EVENT_NAME)
    client = await hass_client_no_auth()
    await client.post(f"/api/webhook/{WEBHOOK_ID}", json=push("state"))
    await hass.async_block_till_done()
    assert events == []


async def test_invalid_payloads_are_rejected(hass, aioclient_mock, hass_client_no_auth):
    entry = await setup(hass, aioclient_mock)
    events = async_capture_events(hass, EVENT_NAME)
    client = await hass_client_no_auth()
    for bad in [
        push("evil"),
        push(tags=["nope"]),
        push(data={"x": {"nested": 1}}),
        push(data={"x": "y" * 201}),
        {**push(), "v": 2},
        "not json",
    ]:
        kwargs = {"data": bad} if isinstance(bad, str) else {"json": bad}
        resp = await client.post(f"/api/webhook/{WEBHOOK_ID}", **kwargs)
        assert resp.status == 400
    await hass.async_block_till_done()
    assert events == []
    assert entry.runtime_data.match["active"] is False
