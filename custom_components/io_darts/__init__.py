"""The IO-Darts integration."""

from __future__ import annotations

from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.network import NoURLAvailableError
from homeassistant.helpers.typing import ConfigType

from .api import HubAuthError, HubClient, HubConnectionError, HubError
from .const import CONF_WEBHOOK_ID, DOMAIN
from .coordinator import IoDartsCoordinator
from .services import async_register_services
from .webhook_handler import make_webhook_handler

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.SENSOR, Platform.SWITCH]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type IoDartsConfigEntry = ConfigEntry[IoDartsCoordinator]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the integration: register the services shared by all entries."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IoDartsConfigEntry) -> bool:
    client = HubClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.data.get(CONF_USERNAME),
        entry.data.get(CONF_PASSWORD),
    )
    try:
        webhook_url = webhook.async_generate_url(
            hass, entry.data[CONF_WEBHOOK_ID], allow_external=False, allow_ip=True, prefer_external=False
        )
    except NoURLAvailableError as err:
        raise ConfigEntryNotReady("Home Assistant has no internal URL the hub can reach") from err

    try:
        await client.login()
    except HubAuthError as err:
        raise ConfigEntryAuthFailed(str(err)) from err
    except HubConnectionError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = IoDartsCoordinator(hass, entry, client, webhook_url)
    webhook.async_register(
        hass,
        DOMAIN,
        "IO-Darts",
        entry.data[CONF_WEBHOOK_ID],
        make_webhook_handler(coordinator),
        local_only=True,
        allowed_methods=["POST"],
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
        raise

    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer="castor.io",
        model="IO-Darts-Agent",
        name="IO-Darts Board",
        sw_version=coordinator.data.status.get("version"),
        configuration_url=client.url,
    )
    coordinator.device_id = device.id
    entry.runtime_data = coordinator
    # Keep polling alive for the entry's lifetime even before any entity
    # subscribes: DataUpdateCoordinator only reschedules itself while it has
    # listeners, but the webhook re-registration in _sync_module must keep
    # running regardless of how many entities are loaded.
    entry.async_on_unload(coordinator.async_add_listener(lambda: None))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: IoDartsConfigEntry) -> bool:
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is not None:
        try:
            await coordinator.client.unregister_webhook()
        except HubError:
            pass
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
