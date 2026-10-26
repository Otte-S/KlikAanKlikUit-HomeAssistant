from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import IcsDevice
from .const import DOMAIN, MANUFACTURER
from .coordinator import Ics2000Coordinator


class IcsEntity(CoordinatorEntity[Ics2000Coordinator]):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: Ics2000Coordinator, device: IcsDevice, suffix: str = ""
    ) -> None:
        super().__init__(coordinator)
        self.device = device
        identity = f"{coordinator.client.mac}-{device.id}"
        self._attr_unique_id = f"klikaanklikuit-{identity}{suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identity)},
            name=device.name,
            manufacturer=MANUFACTURER,
            model=f"ICS-2000 type {device.device_type}",
            via_device=coordinator.hub_identifier,
        )

    @property
    def status(self) -> list:
        return (self.coordinator.data or {}).get(self.device.id, [])

    @property
    def available(self) -> bool:
        return super().available and bool(self.status)
