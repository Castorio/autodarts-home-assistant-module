"""Device triggers for IO-Darts events."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, Event, HassJob, HomeAssistant, callback
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, EVENT_NAME

# trigger type -> (push type, required tag)
TRIGGERS: dict[str, tuple[str, str | None]] = {
    "match_started": ("match_started", None),
    "match_won": ("match_finished", None),
    "leg_won": ("leg_finished", None),
    "player_changed": ("player_changed", None),
    "throw": ("throw", None),
    "throw_180": ("throw", "180"),
    "bust": ("throw", "bust"),
    "bullseye": ("throw", "bullseye"),
    "triple": ("throw", "triple"),
    "high_finish": ("turn_finished", "high_finish"),
    "cricket_closed": ("cricket_closed", None),
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend({vol.Required(CONF_TYPE): vol.In(TRIGGERS)})


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, Any]]:
    return [
        {CONF_PLATFORM: "device", CONF_DOMAIN: DOMAIN, CONF_DEVICE_ID: device_id, CONF_TYPE: trigger_type}
        for trigger_type in TRIGGERS
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    trigger_type = config[CONF_TYPE]
    push_type, tag = TRIGGERS[trigger_type]
    device_id = config[CONF_DEVICE_ID]
    job = HassJob(action)
    trigger_data = trigger_info["trigger_data"]

    @callback
    def handle(event: Event) -> None:
        data = event.data
        if data.get("device_id") != device_id or data.get("type") != push_type:
            return
        if tag is not None and tag not in (data.get("tags") or []):
            return
        hass.async_run_hass_job(
            job,
            {
                "trigger": {
                    **trigger_data,
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_TYPE: trigger_type,
                    "event": event,
                    "description": f"IO-Darts {trigger_type}",
                }
            },
            event.context,
        )

    return hass.bus.async_listen(EVENT_NAME, handle)
