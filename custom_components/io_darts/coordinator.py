"""Polling of the hub and push state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HubAuthError, HubClient, HubConnectionError, ModuleMissingError
from .const import DOMAIN, POLL_INTERVAL

_LOGGER = logging.getLogger(__name__)

EMPTY_MATCH: dict[str, Any] = {
    "active": False,
    "matchId": None,
    "variant": None,
    "mode": None,
    "round": None,
    "currentPlayer": None,
    "players": [],
    "lastThrow": None,
    "lastTurnPoints": None,
    "winnerName": None,
}


@dataclass
class HubData:
    """Result of one poll."""

    status: dict[str, Any]
    modules: list[dict[str, Any]]


class IoDartsCoordinator(DataUpdateCoordinator[HubData]):
    """Polls hub status and modules; holds the pushed match state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: HubClient, webhook_url: str) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=DOMAIN, update_interval=POLL_INTERVAL)
        self.client = client
        self.webhook_url = webhook_url
        self.match: dict[str, Any] = dict(EMPTY_MATCH)
        self.device_id: str | None = None
        self._synced = False

    async def _async_update_data(self) -> HubData:
        try:
            status = await self.client.get_status()
            modules = await self.client.get_modules()
            await self._sync_module()
        except HubAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except HubConnectionError as err:
            raise UpdateFailed(str(err)) from err
        return HubData(status=status, modules=modules)

    async def _sync_module(self) -> None:
        """Re-register our webhook on every poll; reload state when the module's URL changed.

        POST /webhook is idempotent, so registering every poll also takes the
        webhook back if the module restarted or was re-pointed elsewhere.
        """
        try:
            changed = await self.client.register_webhook(self.webhook_url)
            if changed or not self._synced:
                self.match = await self.client.get_match_state()
                self._synced = True
        except ModuleMissingError:
            self._synced = False
            self.match = dict(EMPTY_MATCH)
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                "module_missing",
                is_fixable=False,
                severity=ir.IssueSeverity.ERROR,
                translation_key="module_missing",
            )
            return
        ir.async_delete_issue(self.hass, DOMAIN, "module_missing")

    @callback
    def handle_push(self, payload: dict[str, Any]) -> None:
        """Apply a validated webhook payload."""
        self.match = payload["state"]
        self.async_update_listeners()
