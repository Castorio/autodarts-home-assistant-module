"""Services of the IO-Darts integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .api import HubError
from .const import DOMAIN, INTENT_SLOTS

SERVICE_TRIGGER_INTENT = "trigger_intent"

TRIGGER_INTENT_SCHEMA = vol.Schema(
    {
        vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=1, max=INTENT_SLOTS)),
        vol.Optional("data"): vol.All(str, vol.Length(max=200)),
        vol.Optional("config_entry_id"): str,
    }
)


def async_register_services(hass: HomeAssistant) -> None:
    async def trigger_intent(call: ServiceCall) -> None:
        entries = [
            e
            for e in hass.config_entries.async_entries(DOMAIN)
            if e.state is ConfigEntryState.LOADED
            and ("config_entry_id" not in call.data or e.entry_id == call.data["config_entry_id"])
        ]
        if len(entries) != 1:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_hub")
        try:
            await entries[0].runtime_data.client.trigger_intent(call.data["slot"], call.data.get("data"))
        except HubError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="hub_error", translation_placeholders={"error": str(err)}
            ) from err

    hass.services.async_register(DOMAIN, SERVICE_TRIGGER_INTENT, trigger_intent, schema=TRIGGER_INTENT_SCHEMA)
