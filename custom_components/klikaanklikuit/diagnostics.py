"""Diagnostics support for KlikAanKlikUit.

Download via Settings > Devices & Services > KlikAanKlikUit > ... > Download
diagnostics. Gives a full dump of every device including its raw ICS2000
device_type number - the fastest way to identify special devices (doorbell,
gong, wall-switch input) so they can be classified correctly.

The device_type is re-fetched here from the same 'sync' endpoint the library
uses, because ics2000_python discards the type for devices it can't classify
(it collapses them to a bare Device object). Fetching it separately is the
only way to see the real number.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import requests
from ics2000_python.Core import Hub
from ics2000_python.Cryptographer import decrypt

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

REDACTED = "***REDACTED***"
_REDACT_KEYS = {"password", "email", "mac"}


def _redact(data: dict) -> dict:
    return {k: (REDACTED if k in _REDACT_KEYS else v) for k, v in data.items()}


def _fetch_raw_device_types(hub: Hub) -> dict[int, dict]:
    """Re-fetch the sync endpoint to recover each device's device_type number.

    Runs in the executor (blocking HTTP + decrypt). Accesses a few of the
    library's internal attributes (email/password/home_id) because they aren't
    exposed via a public API; this is diagnostics-only and degrades gracefully
    if the library internals ever change.
    """
    result: dict[int, dict] = {}
    try:
        url = f"{Hub.base_url}/gateway.php"
        params = {
            "action": "sync",
            "email": hub._email,  # noqa: SLF001
            "mac": hub.mac.replace(":", ""),
            "password_hash": hub._password,  # noqa: SLF001
            "home_id": hub._homeId,  # noqa: SLF001
        }
        resp = requests.get(url, params=params, timeout=15)
        for device in resp.json():
            try:
                data = json.loads(decrypt(device["data"], hub.aes))
                module = data.get("module", {})
                if "id" in module:
                    result[module["id"]] = {
                        "name": module.get("name"),
                        "device_type": module.get("device"),
                    }
            except Exception:  # noqa: BLE001 - one bad device shouldn't kill the dump
                continue
    except Exception as err:  # noqa: BLE001
        result[-1] = {"error": str(err)}
    return result


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    raw_types = await hass.async_add_executor_job(
        _fetch_raw_device_types, coordinator.hub
    )

    return {
        "entry_data": _redact(dict(entry.data)),
        "entry_options": dict(entry.options),
        "devices": [
            {
                "id": device.id,
                "name": device.name,
                "python_class": type(device).__name__,
                "device_type": raw_types.get(device.id, {}).get("device_type"),
                "status": coordinator.data.get(device.id, []),
            }
            for device in coordinator.hub.devices
        ],
    }
