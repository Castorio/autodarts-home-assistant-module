"""Polling of the hub and push state."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import HubAuthError, HubClient, HubConnectionError, ModuleMissingError
from .const import DOMAIN, POLL_INTERVAL
from .schema import STATE_SCHEMA

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
    "currentPlayerColor": None,
    "nextPlayerColor": None,
}


@dataclass
class HubData:
    """Result of one poll."""

    status: dict[str, Any]
    modules: list[dict[str, Any]]
    hub_started: datetime | None = None


#: Below this, two computed start times are treated as the same restart (latency jitter
#: around a minute boundary); at or above it, the hub is assumed to have restarted.
RESTART_THRESHOLD = timedelta(seconds=90)


def _started_at(status: dict[str, Any]) -> datetime | None:
    """Start time of the hub (now - uptime), truncated to the minute so it stays stable between polls."""
    uptime = status.get("uptime")
    if isinstance(uptime, bool) or not isinstance(uptime, (int, float)) or not 0 <= uptime < 10**10:
        return None
    started = dt_util.utcnow() - timedelta(seconds=uptime)
    return started.replace(second=0, microsecond=0)


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
        return HubData(status=status, modules=modules, hub_started=self._resolve_hub_started(_started_at(status)))

    def _resolve_hub_started(self, new_started: datetime | None) -> datetime | None:
        """Keep the previous start time across small jitter; only move on an actual restart.

        `_started_at` truncates to the minute, so an unrelated second or two of latency
        between polls can push the raw value across a minute boundary and flip the
        truncated timestamp even though the hub kept running. Only treat it as a restart
        (and take the new value) once the two differ by RESTART_THRESHOLD or more.
        """
        previous = self.data.hub_started if self.data else None
        if previous is not None and new_started is not None and abs(new_started - previous) < RESTART_THRESHOLD:
            return previous
        return new_started

    async def _sync_module(self) -> None:
        """Re-register our webhook on every poll; reload state when the module's URL changed.

        POST /webhook is idempotent, so registering every poll also takes the
        webhook back if the module restarted or was re-pointed elsewhere.
        """
        try:
            changed = await self.client.register_webhook(self.webhook_url)
            if changed or not self._synced:
                self._load_state(await self.client.get_match_state())
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

    def _load_state(self, raw: dict[str, Any]) -> None:
        """Take a polled state only if it passes the same schema as webhook pushes.

        An invalid state leaves the match empty and stays unsynced, so the next
        poll fetches it again. The payload is not logged (it comes from the hub).
        """
        try:
            self.match = STATE_SCHEMA(raw)
        except vol.Invalid as err:
            _LOGGER.warning("Ignoring invalid match state from the hub module at %s", err.path)
            self.match = dict(EMPTY_MATCH)
            self._synced = False
            return
        self._synced = True

    @callback
    def handle_push(self, payload: dict[str, Any]) -> None:
        """Apply a validated webhook payload."""
        self.match = payload["state"]
        self.async_update_listeners()
