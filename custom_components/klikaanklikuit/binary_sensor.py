from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IcsConfigEntry
from .api import IcsDevice
from .coordinator import Ics2000Coordinator
from .device_classifier import CATEGORY_INPUT, classify
from .entity import IcsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: IcsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        Ics2000BinarySensor(coordinator, device)
        for device in coordinator.client.devices
        if classify(device) == CATEGORY_INPUT
    )


class Ics2000BinarySensor(IcsEntity, BinarySensorEntity):
    _attr_name = None

    def __init__(self, coordinator: Ics2000Coordinator, device: IcsDevice) -> None:
        super().__init__(coordinator, device, "-input")
        if device.device_type == 28:
            self._attr_device_class = BinarySensorDeviceClass.OPENING
        else:
            self._attr_entity_registry_enabled_default = False

    @property
    def is_on(self) -> bool | None:
        return self.status[0] == 1 if self.status else None
