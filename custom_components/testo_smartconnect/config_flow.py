"""UI configuration, key rotation and polling options."""

import hashlib

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import ApiError, AuthenticationError, TestoApi
from .const import CONF_INTERVAL, CONF_REGION, CONF_STALE, DEFAULT_INTERVAL, DEFAULT_STALE, DOMAIN, NAME


def user_schema():
    return vol.Schema(
        {
            vol.Required("api_key"): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(CONF_REGION, default="eu"): vol.In(["eu", "am", "ap"]),
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """One config entry per region and account, independent of key rotations."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            user_input["api_key"] = user_input["api_key"].strip()
            try:
                client = TestoApi(async_get_clientsession(self.hass), user_input["api_key"], user_input[CONF_REGION])
                rows = await client.query("properties")
                accounts = sorted({r.get("tenant_uuid") for r in rows if r.get("tenant_uuid")})
                if not accounts:
                    errors["base"] = "no_devices"
                else:
                    account_id = (
                        user_input[CONF_REGION] + ":" + hashlib.sha256("|".join(accounts).encode()).hexdigest()[:24]
                    )
                    await self.async_set_unique_id(account_id)
                    if self.source == config_entries.SOURCE_REAUTH:
                        entry = self._get_reauth_entry()
                        if entry.unique_id != account_id:
                            return self.async_abort(reason="wrong_account")
                        return self.async_update_reload_and_abort(entry, data_updates=user_input)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(title=NAME, data=user_input)
            except AuthenticationError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
        return self.async_show_form(step_id="user", data_schema=user_schema(), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INTERVAL, default=self.config_entry.options.get(CONF_INTERVAL, DEFAULT_INTERVAL)
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=60)),
                    vol.Required(CONF_STALE, default=self.config_entry.options.get(CONF_STALE, DEFAULT_STALE)): vol.All(
                        vol.Coerce(int), vol.Range(min=15, max=1440)
                    ),
                }
            ),
        )
