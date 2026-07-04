"""Config flow for the KlikAanKlikUit (ICS-2000) integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from ics2000_python.Core import CoreException, Hub

import homeassistant.helpers.config_validation as cv
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_EMAIL, CONF_MAC, CONF_PASSWORD
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

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

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MAC): str,
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_LOCAL_IP): str,
    }
)


def _validate(mac: str, email: str, password: str) -> None:
    """Blocking credential check - creating a Hub logs in and pulls devices."""
    hub = Hub(mac, email, password)
    if not hub.connected:
        raise CoreException("Hub did not report connected")


class Ics2000ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ICS2000."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            mac = user_input[CONF_MAC]
            await self.async_set_unique_id(mac.replace(":", "").lower())
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(
                    _validate, mac, user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except CoreException:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected error validating ICS2000 hub")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=f"KlikAanKlikUit ({mac})", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> Ics2000OptionsFlow:
        return Ics2000OptionsFlow(config_entry)


class Ics2000OptionsFlow(OptionsFlow):
    """Runtime-tunable options: retry behaviour and poll interval."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_TRIES, default=options.get(CONF_TRIES, DEFAULT_TRIES)
                ): cv.positive_int,
                vol.Optional(
                    CONF_SLEEP, default=options.get(CONF_SLEEP, DEFAULT_SLEEP)
                ): cv.positive_int,
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=5)),
                vol.Optional(
                    CONF_LOCAL_IP,
                    description={
                        "suggested_value": options.get(
                            CONF_LOCAL_IP, self.config_entry.data.get(CONF_LOCAL_IP, "")
                        )
                    },
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
