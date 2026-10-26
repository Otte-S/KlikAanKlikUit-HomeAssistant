from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.klikaanklikuit.api import IcsAuthError, IcsError
from custom_components.klikaanklikuit.const import DOMAIN

DATA = {"mac": "00:11:22:33:44:55", "email": "e@example.com", "password": "secret", "local_ip": ""}


async def test_user_flow(hass):
    with (
        patch("custom_components.klikaanklikuit.config_flow.IcsClient.async_login", AsyncMock()),
        patch("custom_components.klikaanklikuit.async_setup_entry", AsyncMock(return_value=True)),
    ):
        flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], dict(DATA))
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "001122334455"
    assert result["data"]["mac"] == "001122334455"


@pytest.mark.parametrize(
    "error,expected", [(IcsAuthError(), "invalid_auth"), (IcsError(), "cannot_connect")]
)
async def test_flow_reports_errors(hass, error, expected):
    with patch(
        "custom_components.klikaanklikuit.config_flow.IcsClient.async_login",
        AsyncMock(side_effect=error),
    ):
        flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(flow["flow_id"], dict(DATA))
    assert result["errors"] == {"base": expected}


async def test_invalid_mac(hass):
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {**DATA, "mac": "invalid"}
    )
    assert result["errors"] == {"base": "invalid_input"}


async def test_duplicate_mac_formats(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="001122334455", version=2)
    entry.add_to_hass(hass)
    flow = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(flow["flow_id"], dict(DATA))
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_uses_readonly_config_entry_and_can_clear_setup_ip(hass):
    entry = MockConfigEntry(domain=DOMAIN, data={**DATA, "local_ip": "10.0.0.2"}, version=2)
    entry.add_to_hass(hass)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        flow["flow_id"], {"tries": 2, "sleep": 0, "scan_interval": 30, "local_ip": ""}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["local_ip"] == ""


async def test_reauthentication_updates_credentials(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="001122334455", version=2)
    entry.add_to_hass(hass)
    with (
        patch("custom_components.klikaanklikuit.config_flow.IcsClient.async_login", AsyncMock()),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload", AsyncMock(return_value=True)
        ),
    ):
        flow = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "reauth", "entry_id": entry.entry_id}, data=DATA
        )
        result = await hass.config_entries.flow.async_configure(
            flow["flow_id"], {"email": "new@example.com", "password": "new"}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["password"] == "new"
    assert entry.data["mac"] == DATA["mac"]
