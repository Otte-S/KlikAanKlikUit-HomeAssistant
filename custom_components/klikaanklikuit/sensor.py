from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IcsConfigEntry
from .api import IcsDevice
from .coordinator import Ics2000Coordinator
from .device_classifier import CATEGORY_TEMP_HUMIDITY, classify
from .entity import IcsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: IcsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        Ics2000Sensor(coordinator, device, kind)
        for device in coordinator.client.devices
        if classify(device) == CATEGORY_TEMP_HUMIDITY
        for kind in ("temperature", "humidity")
    )


class Ics2000Sensor(IcsEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: Ics2000Coordinator, device: IcsDevice, kind: str) -> None:
        super().__init__(coordinator, device, f"-{kind}")
        self._attr_translation_key = kind
        self._index = 4 if kind == "temperature" else 11
        self._attr_device_class = (
            SensorDeviceClass.TEMPERATURE if kind == "temperature" else SensorDeviceClass.HUMIDITY
        )
        self._attr_native_unit_of_measurement = (
            UnitOfTemperature.CELSIUS if kind == "temperature" else PERCENTAGE
        )

    @property
    def available(self) -> bool:
        return super().available and self.native_value is not None

    @property
    def native_value(self) -> float | None:
        if len(self.status) <= self._index or not isinstance(
            self.status[self._index], (int, float)
        ):
            return None
        value = round(self.status[self._index] / 100, 2)
        if self._index == 11 and not 0 <= value <= 100:
            return None
        return value
