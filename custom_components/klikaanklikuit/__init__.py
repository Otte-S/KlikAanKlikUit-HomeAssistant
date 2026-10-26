from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_MAC, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import IcsAuthError, IcsClient, IcsError, normalize_mac
from .const import CONF_LOCAL_IP, DOMAIN, MANUFACTURER, MODEL_HUB
from .coordinator import Ics2000Coordinator
from .device_classifier import classify

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.LIGHT, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]
type IcsConfigEntry = ConfigEntry[Ics2000Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: IcsConfigEntry) -> bool:

    local_ip = entry.options.get(CONF_LOCAL_IP, entry.data.get(CONF_LOCAL_IP, ""))
    client = IcsClient(
        async_get_clientsession(hass),
        entry.data[CONF_MAC],
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        local_ip,
    )
    try:
        await client.async_login()
        await client.async_get_devices()
        await client.async_discover()
    except IcsAuthError as err:
        raise ConfigEntryAuthFailed("Check the hub account credentials") from err
    except IcsError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = Ics2000Coordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={coordinator.hub_identifier},
        manufacturer=MANUFACTURER,
        model=MODEL_HUB,
        name="KlikAanKlikUit hub",
    )
    for device in client.devices:
        if classify(device) is None:
            _LOGGER.warning(
                "Unsupported ICS-2000 device type %s (device %s); see diagnostics",
                device.device_type,
                device.id,
            )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: IcsConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: IcsConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version > 2:
        return False
    if entry.version == 1:
        mac = normalize_mac(entry.data[CONF_MAC])
        registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
            prefix = "klikaanklikuit-"
            if entity.unique_id.startswith(prefix):
                rest = entity.unique_id[len(prefix) :]
                if rest.split("-", 1)[0].isdigit():
                    registry.async_update_entity(
                        entity.entity_id, new_unique_id=f"{prefix}{mac}-{rest}"
                    )
        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
            identifiers = {
                (domain, f"{mac}-{identifier}")
                if domain == DOMAIN and identifier.isdigit()
                else (domain, identifier)
                for domain, identifier in device.identifiers
            }
            if identifiers != device.identifiers:
                device_registry.async_update_device(device.id, new_identifiers=identifiers)
        hass.config_entries.async_update_entry(entry, version=2, unique_id=mac)
    return True
