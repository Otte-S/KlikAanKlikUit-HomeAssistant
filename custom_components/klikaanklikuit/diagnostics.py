"""Diagnostics support for ICS2000.

Download via Settings > Devices & Services > ICS2000 > ... > Download
diagnostics. Gives a full dump of every known device with its raw status,
which is the fastest way to identify an unmapped device (e.g. a doorbell).
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

REDACTED = "***REDACTED***"
_REDACT_KEYS = {"password", "email", "mac"}


def _redact(data: dict) -> dict:
    return {k: (REDACTED if k in _REDACT_KEYS else v) for k, v in data.items()}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    return {
        "entry_data": _redact(dict(entry.data)),
        "entry_options": dict(entry.options),
        "devices": [
            {
                "id": device.id,
                "name": device.name,
                "python_class": type(device).__name__,
                "status": coordinator.data.get(device.id, []),
            }
            for device in coordinator.hub.devices
        ],
    }
