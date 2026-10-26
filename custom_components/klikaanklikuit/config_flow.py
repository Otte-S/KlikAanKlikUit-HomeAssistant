from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_MAC, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IcsAuthError, IcsClient, IcsError, normalize_ip, normalize_mac
from .const import (
    CONF_LOCAL_IP,
    CONF_SCAN_INTERVAL,
    CONF_SLEEP,
    CONF_TRIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLEEP,
    DEFAULT_TRIES,
    DOMAIN,
)

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_LOCAL_IP, default=""): str,
    }
)


class Ics2000ConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def _async_validate(self, data: dict[str, Any]) -> None:
        client = IcsClient(
            async_get_clientsession(self.hass),
            data[CONF_MAC],
            data[CONF_EMAIL],
            data[CONF_PASSWORD],
            data.get(CONF_LOCAL_IP, ""),
        )
        await client.async_login()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                mac = normalize_mac(user_input[CONF_MAC])
                user_input[CONF_LOCAL_IP] = normalize_ip(user_input.get(CONF_LOCAL_IP, ""))
                await self.async_set_unique_id(mac)
                self._abort_if_unique_id_configured()
                await self._async_validate(user_input)
            except ValueError:
                errors["base"] = "invalid_input"
            except IcsAuthError:
                errors["base"] = "invalid_auth"
            except IcsError:
                errors["base"] = "cannot_connect"
            else:
                user_input[CONF_MAC] = mac
                return self.async_create_entry(title="KlikAanKlikUit", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._async_validate({**entry.data, **user_input})
            except IcsAuthError:
                errors["base"] = "invalid_auth"
            except IcsError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL, default=entry.data[CONF_EMAIL]): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> Ics2000OptionsFlow:

        return Ics2000OptionsFlow()


class Ics2000OptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                user_input[CONF_LOCAL_IP] = normalize_ip(user_input.get(CONF_LOCAL_IP, ""))
            except ValueError:
                errors["base"] = "invalid_input"
            else:
                return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(CONF_TRIES, default=options.get(CONF_TRIES, DEFAULT_TRIES)): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=5)
                ),
                vol.Optional(CONF_SLEEP, default=options.get(CONF_SLEEP, DEFAULT_SLEEP)): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=30)
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=3600)),
                vol.Optional(
                    CONF_LOCAL_IP,
                    default=options.get(
                        CONF_LOCAL_IP, self.config_entry.data.get(CONF_LOCAL_IP, "")
                    ),
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
