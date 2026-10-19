"""Client for the IO-Darts-Agent hub API."""

from __future__ import annotations

import json as json_lib
import re
from typing import Any

import aiohttp

from .const import LEGACY_SESSION_COOKIE, MODULE_ROUTES, REQUEST_TIMEOUT, SESSION_COOKIE

_MODULE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_MODULE_ACTIONS = {"start", "stop", "restart"}
_AUTODARTS_ACTIONS = {"connect", "disconnect"}


class HubError(Exception):
    """Base error of the hub client."""


class HubConnectionError(HubError):
    """Hub not reachable or answered with an error."""


class HubAuthError(HubError):
    """Login failed or session rejected."""


class ModuleMissingError(HubError):
    """The homeassistant module is not installed or not running."""


class HubClient:
    """Talks to the hub with a session cookie (when web auth is enabled)."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        url: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._username = username or None
        self._password = password or ""
        self._cookie: str | None = None
        self._timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)

    @property
    def url(self) -> str:
        """Base URL of the hub."""
        return self._url

    async def login(self) -> None:
        """Get a session cookie; does nothing without a username."""
        if not self._username:
            return
        try:
            async with self._session.post(
                f"{self._url}/api/auth/login",
                json={"username": self._username, "password": self._password},
                timeout=self._timeout,
            ) as resp:
                if resp.status == 401:
                    raise HubAuthError("invalid credentials")
                if resp.status >= 400:
                    raise HubConnectionError(f"login failed: HTTP {resp.status}")
                cookie = resp.cookies.get(SESSION_COOKIE)
                self._cookie = cookie.value if cookie else None
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HubConnectionError(str(err)) from err

    async def _request(self, method: str, path: str, json: Any = None, retry: bool = True) -> Any:
        headers = (
            {"Cookie": f"{SESSION_COOKIE}={self._cookie}; {LEGACY_SESSION_COOKIE}={self._cookie}"}
            if self._cookie
            else {}
        )
        retry_needed = False
        text: str | None = None
        try:
            async with self._session.request(
                method, f"{self._url}{path}", json=json, headers=headers, timeout=self._timeout
            ) as resp:
                if resp.status == 401 and retry and self._username:
                    # Note the retry; the actual login + retry happens after this
                    # response context has been exited below.
                    retry_needed = True
                elif resp.status == 401:
                    raise HubAuthError("session rejected")
                elif path.startswith(MODULE_ROUTES) and resp.status in (404, 503):
                    raise ModuleMissingError(f"{method} {path}: HTTP {resp.status}")
                elif resp.status >= 400:
                    raise HubConnectionError(f"{method} {path}: HTTP {resp.status}")
                else:
                    text = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise HubConnectionError(str(err)) from err

        if retry_needed:
            await self.login()
            return await self._request(method, path, json, retry=False)

        if not text:
            return None
        try:
            return json_lib.loads(text)
        except ValueError as err:
            raise HubConnectionError("invalid JSON from hub") from err

    async def get_status(self) -> dict[str, Any]:
        result = await self._request("GET", "/api/status")
        if not isinstance(result, dict):
            raise HubConnectionError("expected a JSON object from /api/status")
        return result

    async def get_modules(self) -> list[dict[str, Any]]:
        result = await self._request("GET", "/api/modules")
        if not isinstance(result, list):
            raise HubConnectionError("expected a JSON array from /api/modules")
        return result

    async def module_action(self, module_id: str, action: str) -> None:
        if not _MODULE_ID.match(module_id) or action not in _MODULE_ACTIONS:
            raise ValueError(f"invalid module action {module_id}/{action}")
        await self._request("POST", f"/api/modules/{module_id}/{action}")

    async def autodarts(self, action: str) -> None:
        if action not in _AUTODARTS_ACTIONS:
            raise ValueError(f"invalid autodarts action {action}")
        await self._request("POST", f"/api/autodarts/{action}")

    async def restart_hub(self) -> None:
        await self._request("POST", "/api/settings/restart")

    async def webhook_registered(self) -> bool:
        result = await self._request("GET", f"{MODULE_ROUTES}/webhook")
        if not isinstance(result, dict):
            raise HubConnectionError("expected a JSON object from the webhook route")
        return bool(result.get("registered"))

    async def register_webhook(self, url: str) -> None:
        await self._request("POST", f"{MODULE_ROUTES}/webhook", {"url": url})

    async def unregister_webhook(self) -> None:
        await self._request("DELETE", f"{MODULE_ROUTES}/webhook")

    async def get_match_state(self) -> dict[str, Any]:
        result = await self._request("GET", f"{MODULE_ROUTES}/state")
        if not isinstance(result, dict):
            raise HubConnectionError("expected a JSON object from the state route")
        return result

    async def trigger_intent(self, slot: int, data: str | None) -> None:
        body: dict[str, Any] = {"slot": slot}
        if data is not None:
            body["data"] = data
        await self._request("POST", f"{MODULE_ROUTES}/intent", body)
