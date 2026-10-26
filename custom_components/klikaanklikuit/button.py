from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IcsConfigEntry
from .device_classifier import CATEGORY_GONG, classify
from .entity import IcsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: IcsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        Ics2000GongButton(coordinator, device, "-gong")
        for device in coordinator.client.devices
        if classify(device) == CATEGORY_GONG
    )


class Ics2000GongButton(IcsEntity, ButtonEntity):
    _attr_name = None

    @property
    def available(self) -> bool:
        return bool(self.coordinator.client.local_ip) or self.coordinator.last_update_success

    async def async_press(self) -> None:
        await self.coordinator.async_command(self.device, 0, 1)
