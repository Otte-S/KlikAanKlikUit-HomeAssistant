from unittest.mock import patch

import pytest
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.klikaanklikuit import async_migrate_entry
from custom_components.klikaanklikuit.api import IcsAuthError, IcsError
from custom_components.klikaanklikuit.const import DOMAIN
from custom_components.klikaanklikuit.diagnostics import async_get_config_entry_diagnostics

DATA = {
    "mac": "001122334455",
    "email": "private@example.com",
    "password": "secret",
    "local_ip": "10.0.0.2",
}


async def setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DATA["mac"], data=DATA, version=2)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_platforms_types_and_experimental_input_defaults(hass, mock_client):
    entry = await setup(hass)
    registry = er.async_get(hass)
    entities = er.async_entries_for_config_entry(registry, entry.entry_id)
    assert len(entities) == 7
    assert hass.states.get("sensor.climate_temperature").state == "21.5"
    assert hass.states.get("sensor.climate_humidity").state == "45.0"
    assert hass.states.get("light.dimmer").attributes["brightness"] == 128
    assert hass.states.get("binary_sensor.contact").state == "on"
    doorbell = next(e for e in entities if e.entity_id == "binary_sensor.doorbell")
    assert doorbell.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert not any(e.entity_id.endswith("unknown") for e in entities)


async def test_zigbee_dimming_uses_zigbee_functions_and_power_on(hass, mock_client):
    await setup(hass)
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.dimmer", "brightness": 128}, blocking=True
    )
    assert mock_client.async_send.call_args_list[0].args[:3] == (2, 4, 127)
    assert mock_client.async_send.call_args_list[1].args[:3] == (2, 3, 1)
    assert hass.states.get("light.dimmer").state == "on"


async def test_zero_brightness_turns_off(hass, mock_client):
    await setup(hass)
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.dimmer", "brightness": 0}, blocking=True
    )
    assert mock_client.async_send.call_args.args[:3] == (2, 3, 0)


async def test_cloud_failure_marks_sensors_unavailable_but_keeps_local_commands(hass, mock_client):
    entry = await setup(hass)
    mock_client.async_get_statuses.side_effect = IcsError("Cloud unavailable")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert not entry.runtime_data.last_update_success
    assert hass.states.get("sensor.climate_temperature").state == STATE_UNAVAILABLE
    assert hass.states.get("light.desk").state != STATE_UNAVAILABLE
    assert hass.states.get("light.desk").attributes["assumed_state"]


async def test_auth_failure_requests_reauthentication(hass, mock_client):
    entry = await setup(hass)
    mock_client.async_get_statuses.side_effect = IcsAuthError()
    with pytest.raises(ConfigEntryAuthFailed):
        await entry.runtime_data._async_update_data()


async def test_optimistic_brightness_not_dropped_when_only_power_matches(hass, mock_client):
    entry = await setup(hass)
    mock_client.async_get_statuses.return_value[2] = [0, 0, 0, 1, 20]
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.dimmer", "brightness": 200}, blocking=True
    )
    assert hass.states.get("light.dimmer").attributes["brightness"] == 200
    mock_client.async_get_statuses.return_value[2] = [0, 0, 0, 1, 199]
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("light.dimmer").attributes["brightness"] == 200


async def test_diagnostics_redact_account_and_addresses(hass, mock_client):
    entry = await setup(hass)
    text = str(await async_get_config_entry_diagnostics(hass, entry))
    for private in (DATA["email"], DATA["password"], DATA["mac"], DATA["local_ip"], "Climate"):
        assert private not in text


async def test_migration_preserves_entity_ids_and_scopes_devices_to_hub(hass):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id=DATA["mac"], version=1)
    entry.add_to_hass(hass)
    devices = dr.async_get(hass)
    device = devices.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "42")}, name="My lamp"
    )
    registry = er.async_get(hass)
    entity = registry.async_get_or_create(
        "light",
        DOMAIN,
        "klikaanklikuit-42",
        config_entry=entry,
        device_id=device.id,
        suggested_object_id="custom_lamp",
    )
    assert await async_migrate_entry(hass, entry)
    migrated = registry.async_get(entity.entity_id)
    assert migrated.entity_id == "light.custom_lamp"
    assert migrated.unique_id == "klikaanklikuit-001122334455-42"
    assert devices.async_get(device.id).identifiers == {(DOMAIN, "001122334455-42")}
    assert entry.version == 2


async def test_setup_connection_error_retries(hass, mock_client):
    mock_client.async_login.side_effect = IcsError("Offline")
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, version=2)
    entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state.value == "setup_retry"


async def test_cleared_local_ip_overrides_old_entry_data(hass, mock_client):
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, options={"local_ip": ""}, version=2)
    entry.add_to_hass(hass)
    with patch("custom_components.klikaanklikuit.IcsClient", return_value=mock_client) as factory:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert factory.call_args.args[-1] == ""


async def test_classic_dimmer_uses_fifteen_steps(hass, mock_client):
    from custom_components.klikaanklikuit.api import IcsDevice

    mock_client.devices[1] = IcsDevice(2, "Dimmer", 2)
    mock_client.async_get_statuses.return_value[2] = [1, 15]
    await setup(hass)
    await hass.services.async_call(
        "light", "turn_on", {"entity_id": "light.dimmer", "brightness": 128}, blocking=True
    )
    assert mock_client.async_send.call_args_list[0].args[:3] == (2, 1, 8)
    assert mock_client.async_send.call_args_list[1].args[:3] == (2, 0, 1)


async def test_missing_status_only_disables_affected_sensors(hass, mock_client):
    entry = await setup(hass)
    mock_client.async_get_statuses.return_value = {1: [1], 2: [0, 0, 0, 1, 127], 3: []}
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.climate_temperature").state == STATE_UNAVAILABLE
    assert hass.states.get("light.desk").state == "on"


def test_two_hubs_get_distinct_device_and_entity_ids(hass, mock_client):
    from custom_components.klikaanklikuit.api import IcsDevice
    from custom_components.klikaanklikuit.coordinator import Ics2000Coordinator
    from custom_components.klikaanklikuit.light import Ics2000Light

    entry = MockConfigEntry(domain=DOMAIN, data=DATA, version=2)
    coordinator = Ics2000Coordinator(hass, entry, mock_client)
    first = Ics2000Light(coordinator, IcsDevice(1, "Desk", 1))
    mock_client.mac = "aabbccddeeff"
    second = Ics2000Light(coordinator, IcsDevice(1, "Desk", 1))
    assert first.unique_id != second.unique_id
    assert first.device_info["identifiers"] != second.device_info["identifiers"]
