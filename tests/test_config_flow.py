"""Tests for the config flow."""

from unittest.mock import patch

import aiohttp

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.io_darts.const import DOMAIN

from .const import ENTRY_DATA, STATUS, URL, routes

USER_INPUT = {"url": URL + "/", "username": "admin", "password": "pw"}


@pytest.fixture(autouse=True)
def no_setup():
    with (
        patch("custom_components.io_darts.async_setup_entry", return_value=True),
        patch("custom_components.io_darts.async_unload_entry", return_value=True),
    ):
        yield


def mock_hub(aioclient_mock, status=STATUS):
    aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True}, cookies={"autodarts_session": "sid"})
    aioclient_mock.get(f"{URL}/api/status", json=status)
    aioclient_mock.get(routes("/webhook"), json={"registered": False})


async def start(hass):
    return await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})


async def test_user_flow_creates_entry(hass, aioclient_mock):
    mock_hub(aioclient_mock)
    result = await start(hass)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "IO-Darts Board"
    assert result["result"].unique_id == "board-123"
    data = result["data"]
    assert data["url"] == URL
    assert data["username"] == "admin"
    assert len(data["webhook_id"]) >= 32


async def test_unique_id_falls_back_to_host(hass, aioclient_mock):
    mock_hub(aioclient_mock, {**STATUS, "autodarts": {"connected": False}})
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["result"].unique_id == "hub.local:3000"


@pytest.mark.parametrize(
    ("setup", "error"),
    [
        ("auth", "invalid_auth"),
        ("down", "cannot_connect"),
        ("module", "module_missing"),
    ],
)
async def test_user_flow_errors(hass, aioclient_mock, setup, error):
    if setup == "auth":
        aioclient_mock.post(f"{URL}/api/auth/login", status=401, json={})
    else:
        aioclient_mock.post(f"{URL}/api/auth/login", json={"success": True})
        if setup == "down":
            aioclient_mock.get(f"{URL}/api/status", status=500, json={})
        else:
            aioclient_mock.get(f"{URL}/api/status", json=STATUS)
            aioclient_mock.get(routes("/webhook"), status=404, json={})
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}


@pytest.mark.parametrize("url", ["hub.local:3000", "ftp://hub.local", "http://"])
async def test_invalid_url(hass, url):
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"url": url})
    assert result["errors"] == {"base": "invalid_url"}


async def test_already_configured(hass, aioclient_mock):
    MockConfigEntry(domain=DOMAIN, unique_id="board-123", data=ENTRY_DATA).add_to_hass(hass)
    mock_hub(aioclient_mock)
    result = await start(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass, aioclient_mock):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="board-123", data=ENTRY_DATA)
    entry.add_to_hass(hass)
    mock_hub(aioclient_mock)
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"username": "admin", "password": "new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new"
    assert entry.data["webhook_id"] == ENTRY_DATA["webhook_id"]


async def test_flow_uses_a_private_cookie_jar(hass, aioclient_mock):
    mock_hub(aioclient_mock)
    with patch(
        "custom_components.io_darts.config_flow.async_create_clientsession", wraps=async_create_clientsession
    ) as create:
        result = await start(hass)
        await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert isinstance(create.call_args.kwargs["cookie_jar"], aiohttp.DummyCookieJar)
