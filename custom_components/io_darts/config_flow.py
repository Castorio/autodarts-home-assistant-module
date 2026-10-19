"""Config flow for IO-Darts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from yarl import URL

from .api import HubAuthError, HubClient, HubConnectionError, ModuleMissingError
from .const import CONF_WEBHOOK_ID, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)
REAUTH_SCHEMA = vol.Schema({vol.Optional(CONF_USERNAME): str, vol.Optional(CONF_PASSWORD): str})


def _normalize_url(raw: str) -> str | None:
    try:
        url = URL(raw.strip())
    except ValueError:
        return None
    if url.scheme not in ("http", "https") or not url.host:
        return None
    return str(url.with_path(url.path.rstrip("/")).with_query(None).with_fragment(None)).rstrip("/")


class IoDartsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up the connection to an IO-Darts-Agent hub."""

    VERSION = 1

    async def _validate(self, url: str, username: str | None, password: str | None) -> str:
        """Check login, hub and module; return the unique id."""
        client = HubClient(async_get_clientsession(self.hass), url, username, password)
        await client.login()
        status = await client.get_status()
        await client.webhook_registered()
        board_id = (status.get("autodarts") or {}).get("boardId")
        if board_id:
            return str(board_id)
        parsed = URL(url)
        return f"{parsed.host}:{parsed.port}"

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = _normalize_url(user_input[CONF_URL])
            if url is None:
                errors["base"] = "invalid_url"
            else:
                try:
                    unique_id = await self._validate(
                        url, user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)
                    )
                except HubAuthError:
                    errors["base"] = "invalid_auth"
                except ModuleMissingError:
                    errors["base"] = "module_missing"
                except HubConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(unique_id)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="IO-Darts Board",
                        data={
                            CONF_URL: url,
                            CONF_USERNAME: user_input.get(CONF_USERNAME, ""),
                            CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                            CONF_WEBHOOK_ID: webhook.async_generate_id(),
                        },
                    )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            try:
                await self._validate(
                    entry.data[CONF_URL], user_input.get(CONF_USERNAME), user_input.get(CONF_PASSWORD)
                )
            except HubAuthError:
                errors["base"] = "invalid_auth"
            except ModuleMissingError:
                errors["base"] = "module_missing"
            except HubConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={
                        CONF_USERNAME: user_input.get(CONF_USERNAME, ""),
                        CONF_PASSWORD: user_input.get(CONF_PASSWORD, ""),
                    },
                )
        return self.async_show_form(step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors)
