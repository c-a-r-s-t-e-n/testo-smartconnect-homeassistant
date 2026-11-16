"""Validate form, account identity and authentication error behavior."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.testo_smartconnect.api import AuthenticationError
from custom_components.testo_smartconnect.config_flow import ConfigFlow


@pytest.mark.asyncio
async def test_form_has_password_selector(tmp_path):
    flow = ConfigFlow()
    flow.hass = HomeAssistant(str(tmp_path))
    flow.context = {"source": "user"}
    result = await flow.async_step_user()
    assert result["step_id"] == "user"
    assert result["description_placeholders"]["cloud_url"] == "https://www.eu.smartconnect.testo.com/"
    assert "api_key" in str(result["data_schema"].schema)


@pytest.mark.asyncio
async def test_valid_key_creates_entry_and_account_id(tmp_path):
    flow = ConfigFlow()
    flow.hass = HomeAssistant(str(tmp_path))
    flow.context = {"source": "user"}
    flow.async_set_unique_id = AsyncMock()
    flow._abort_if_unique_id_configured = MagicMock()
    with (
        patch("custom_components.testo_smartconnect.config_flow.async_get_clientsession"),
        patch("custom_components.testo_smartconnect.config_flow.TestoApi") as cls,
    ):
        cls.return_value.query = AsyncMock(return_value=[{"tenant_uuid": "synthetic-account"}])
        result = await flow.async_step_user({"api_key": " synthetic-key ", "region": "eu"})
    assert result["type"] == "create_entry"
    assert result["data"]["api_key"] == "synthetic-key"
    assert flow.async_set_unique_id.call_args.args[0].startswith("eu:")


@pytest.mark.asyncio
async def test_auth_error_returns_form(tmp_path):
    flow = ConfigFlow()
    flow.hass = HomeAssistant(str(tmp_path))
    flow.context = {"source": "user"}
    with (
        patch("custom_components.testo_smartconnect.config_flow.async_get_clientsession"),
        patch("custom_components.testo_smartconnect.config_flow.TestoApi") as cls,
    ):
        cls.return_value.query = AsyncMock(side_effect=AuthenticationError("Invalid key"))
        result = await flow.async_step_user({"api_key": "bad", "region": "eu"})
    assert result["errors"] == {"base": "invalid_auth"}
