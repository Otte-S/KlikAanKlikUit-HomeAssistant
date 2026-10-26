from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from . import IcsConfigEntry
from .device_classifier import classify

TO_REDACT = {"password", "email", "mac", "local_ip", "name"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IcsConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "entry_data": dict(entry.data),
            "entry_options": dict(entry.options),
            "local_transport_configured": bool(coordinator.client.local_ip),
            "last_update_success": coordinator.last_update_success,
            "devices": [
                {
                    "id": device.id,
                    "name": device.name,
                    "device_type": device.device_type,
                    "category": classify(device),
                    "status": (coordinator.data or {}).get(device.id),
                }
                for device in coordinator.client.devices
            ],
        },
        TO_REDACT,
    )
