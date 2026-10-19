"""Tests for the hub client."""

import aiohttp
import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.io_darts.api import (
    HubAuthError,
    HubClient,
    HubConnectionError,
    ModuleMissingError,
)

from .const import MATCH, MODULES, STATUS, URL, routes


def client(hass, username="admin", password="pw"):
    return HubClient(async_get_clientsession(hass), URL + "/", username, password)


async def test_login_stores_session_cookie(hass, aioclient_mock):
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True}, cookies={"autodarts_session": "sid1"})
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    c = client(hass)
    await c.login()
    assert await c.get_status() == STATUS
    _, _, body, _ = aioclient_mock.mock_calls[0]
    assert body == {"username": "admin", "password": "pw"}
    assert aioclient_mock.mock_calls[1][3]["Cookie"] == "autodarts_session=sid1; session=sid1"


async def test_login_skipped_without_username(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/api/status", json=STATUS)
    c = client(hass, None, None)
    await c.login()
    await c.get_status()
    assert aioclient_mock.call_count == 1
    assert "Cookie" not in (aioclient_mock.mock_calls[0][3] or {})


async def test_login_wrong_password(hass, aioclient_mock):
    aioclient_mock.post(f"{URL}/api/auth/login", status=401, json={"success": False})
    with pytest.raises(HubAuthError):
        await client(hass).login()


async def test_401_relogs_once_then_raises(hass, aioclient_mock):
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True}, cookies={"autodarts_session": "sid"})
    aioclient_mock.get(f"{URL}/api/modules", status=401, json={})
    with pytest.raises(HubAuthError):
        await client(hass).get_modules()
    assert aioclient_mock.call_count == 3  # request, login, request


async def test_connection_error(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/api/status", exc=aiohttp.ClientError("boom"))
    with pytest.raises(HubConnectionError):
        await client(hass, None, None).get_status()


async def test_module_missing(hass, aioclient_mock):
    aioclient_mock.get(routes("/webhook"), status=404, json={"error": "No routes registered"})
    with pytest.raises(ModuleMissingError):
        await client(hass, None, None).webhook_registered()


async def test_module_not_ready(hass, aioclient_mock):
    aioclient_mock.get(routes("/state"), status=503, json={"error": "Module not ready"})
    with pytest.raises(ModuleMissingError):
        await client(hass, None, None).get_match_state()


async def test_module_routes(hass, aioclient_mock):
    aioclient_mock.get(routes("/webhook"), json={"registered": True})
    aioclient_mock.post(routes("/webhook"), json={"registered": True, "changed": False})
    aioclient_mock.delete(routes("/webhook"), json={"registered": False})
    aioclient_mock.get(routes("/state"), json=MATCH)
    aioclient_mock.post(routes("/intent"), json={"emitted": "homeassistant.trigger_2"})
    c = client(hass, None, None)
    assert await c.webhook_registered() is True
    assert await c.register_webhook("http://ha/api/webhook/x") is False
    await c.unregister_webhook()
    assert await c.get_match_state() == MATCH
    await c.trigger_intent(2, "party")
    assert aioclient_mock.mock_calls[1][2] == {"url": "http://ha/api/webhook/x"}
    assert aioclient_mock.mock_calls[4][2] == {"slot": 2, "data": "party"}


@pytest.mark.parametrize(
    ("body", "changed"),
    [({"registered": True, "changed": True}, True), ({"registered": True}, True), (None, True)],
)
async def test_register_webhook_treats_unknown_change_as_changed(hass, aioclient_mock, body, changed):
    """Older modules do not report "changed"; refetching state then is the safe choice."""
    if body is None:
        aioclient_mock.post(routes("/webhook"), status=204)
    else:
        aioclient_mock.post(routes("/webhook"), json=body)
    assert await client(hass, None, None).register_webhook("http://ha/api/webhook/x") is changed


async def test_module_route_sends_cookie_under_legacy_name_too(hass, aioclient_mock):
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True}, cookies={"autodarts_session": "sid2"})
    aioclient_mock.get(routes("/webhook"), json={"registered": True})
    c = client(hass)
    await c.login()
    await c.webhook_registered()
    assert aioclient_mock.mock_calls[1][3]["Cookie"] == "autodarts_session=sid2; session=sid2"


async def test_hub_actions(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/api/modules", json=MODULES)
    aioclient_mock.post(f"{URL}/api/modules/wled/stop", json={"success": True})
    aioclient_mock.post(f"{URL}/api/autodarts/connect", json={"success": True})
    aioclient_mock.post(f"{URL}/api/settings/restart", json={"success": True})
    c = client(hass, None, None)
    assert await c.get_modules() == MODULES
    await c.module_action("wled", "stop")
    await c.autodarts("connect")
    await c.restart_hub()
    assert aioclient_mock.call_count == 4


async def test_get_modules_keeps_only_well_formed_entries(hass, aioclient_mock):
    good = {"id": "wled", "name": "WLED", "status": "running"}
    no_status = {"id": "caller", "name": "Caller"}
    aioclient_mock.get(
        f"{URL}/api/modules",
        json=[
            good,
            no_status,
            "wled",
            {"id": 5, "name": "x"},
            {"id": "a"},
            {"id": "b", "name": None},
            {"id": "c", "name": "C", "status": 1},
        ],
    )
    assert await client(hass, None, None).get_modules() == [good, no_status]


@pytest.mark.parametrize(
    ("module_id", "action"),
    [("../settings", "stop"), ("wled", "delete"), ("WLED/x", "start")],
)
async def test_rejects_unsafe_module_actions(hass, module_id, action):
    with pytest.raises(ValueError):
        await client(hass, None, None).module_action(module_id, action)


async def test_rejects_unknown_autodarts_action(hass):
    with pytest.raises(ValueError):
        await client(hass, None, None).autodarts("reboot")


async def test_module_action_accepts_empty_body(hass, aioclient_mock):
    aioclient_mock.post(f"{URL}/api/modules/wled/stop", status=204)
    await client(hass, None, None).module_action("wled", "stop")


async def test_get_status_rejects_non_json_body(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/api/status", text="not json")
    with pytest.raises(HubConnectionError):
        await client(hass, None, None).get_status()


async def test_get_status_rejects_wrong_type(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/api/status", json=["not", "a", "dict"])
    with pytest.raises(HubConnectionError):
        await client(hass, None, None).get_status()


async def test_bodyless_post_is_accepted_by_a_strict_hub(socket_enabled):
    """The hub (Fastify) answers 415 to an empty body sent as application/octet-stream."""
    from aiohttp import web
    from aiohttp.test_utils import TestServer

    seen: list[str | None] = []

    async def handler(request: web.Request) -> web.Response:
        content_type = request.headers.get("Content-Type")
        seen.append(content_type)
        if content_type not in (None, "application/json"):
            return web.json_response({"error": "Unsupported Media Type"}, status=415)
        return web.json_response({"success": True})

    app = web.Application()
    app.router.add_post("/api/modules/{module}/{action}", handler)
    app.router.add_post("/api/autodarts/{action}", handler)
    app.router.add_post("/api/settings/restart", handler)
    async with TestServer(app, host="127.0.0.1") as server, aiohttp.ClientSession() as session:
        c = HubClient(session, str(server.make_url("")))
        await c.module_action("wled", "start")
        await c.autodarts("connect")
        await c.restart_hub()
    assert seen == [None, None, None]
