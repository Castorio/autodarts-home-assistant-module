"""Tests for device triggers."""

import pytest
from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.core_config import async_process_ha_core_config
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_get_device_automations

from custom_components.io_darts.const import DOMAIN, EVENT_NAME
from custom_components.io_darts.device_trigger import TRIGGERS

from .const import ENTRY_DATA, MATCH, MODULES, STATUS, URL, routes


async def setup(hass, aioclient_mock):
    await async_process_ha_core_config(hass, {"internal_url": "http://192.168.41.10:8123"})
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True})
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    aioclient_mock.get(f"{URL}/api/modules", json=MODULES)
    aioclient_mock.get(routes("/webhook"), json={"registered": True})
    aioclient_mock.post(routes("/webhook"), json={"registered": True})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    aioclient_mock.get(routes("/state"), json=MATCH)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="board-123", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry.runtime_data.device_id


async def test_lists_all_triggers(hass, aioclient_mock):
    device_id = await setup(hass, aioclient_mock)
    triggers = await async_get_device_automations(hass, DeviceAutomationType.TRIGGER, device_id)
    # The device also exposes entity-based device triggers (binary_sensor, switch,
    # sensor, button) registered by earlier tasks; restrict to our own domain to
    # check that the io_darts platform contributes exactly the 11 custom types.
    assert {t["type"] for t in triggers if t["domain"] == DOMAIN} == set(TRIGGERS)


async def attach(hass, device_id, trigger_type):
    calls = []
    hass.services.async_register("test", "automation", lambda call: calls.append(call))
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"platform": "device", "domain": DOMAIN, "device_id": device_id, "type": trigger_type},
                    "action": {"service": "test.automation", "data_template": {"type": "{{ trigger.event.data.type }}"}},
                }
            ]
        },
    )
    return calls


@pytest.mark.parametrize(
    ("trigger_type", "event", "fires"),
    [
        ("throw_180", {"type": "throw", "tags": ["180", "triple"]}, True),
        ("throw_180", {"type": "throw", "tags": ["triple"]}, False),
        ("throw", {"type": "throw", "tags": []}, True),
        ("match_won", {"type": "match_finished", "tags": []}, True),
        ("high_finish", {"type": "turn_finished", "tags": ["high_finish"]}, True),
        ("leg_won", {"type": "match_finished", "tags": []}, False),
    ],
)
async def test_trigger_fires(hass, aioclient_mock, trigger_type, event, fires):
    device_id = await setup(hass, aioclient_mock)
    calls = await attach(hass, device_id, trigger_type)
    hass.bus.async_fire(EVENT_NAME, {"device_id": device_id, **event})
    await hass.async_block_till_done()
    assert len(calls) == (1 if fires else 0)


async def test_trigger_ignores_other_devices(hass, aioclient_mock):
    device_id = await setup(hass, aioclient_mock)
    calls = await attach(hass, device_id, "throw")
    hass.bus.async_fire(EVENT_NAME, {"device_id": "other", "type": "throw", "tags": []})
    await hass.async_block_till_done()
    assert calls == []
