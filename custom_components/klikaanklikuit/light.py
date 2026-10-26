from __future__ import annotations

import math
import time
from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import IcsConfigEntry
from .api import IcsDevice
from .coordinator import Ics2000Coordinator
from .device_classifier import (
    CATEGORY_DIMMER,
    CATEGORY_LIGHT,
    classify,
    dim_function,
    max_brightness,
    power_function,
)
from .entity import IcsEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: IcsConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        Ics2000Light(coordinator, device)
        for device in coordinator.client.devices
        if classify(device) in (CATEGORY_LIGHT, CATEGORY_DIMMER)
    )


class Ics2000Light(IcsEntity, LightEntity):
    _attr_name = None

    def __init__(self, coordinator: Ics2000Coordinator, device: IcsDevice) -> None:
        super().__init__(coordinator, device)
        self._dimmer = classify(device) == CATEGORY_DIMMER
        self._attr_color_mode = ColorMode.BRIGHTNESS if self._dimmer else ColorMode.ONOFF
        self._attr_supported_color_modes = {self._attr_color_mode}
        self._optimistic_on: bool | None = None
        self._optimistic_brightness: int | None = None
        self._optimistic_until = 0.0

    @property
    def optimistic(self) -> bool:
        return time.monotonic() < self._optimistic_until

    @property
    def available(self) -> bool:

        return bool(self.coordinator.client.local_ip) or super().available

    @property
    def assumed_state(self) -> bool:
        return self.optimistic or not self.coordinator.last_update_success

    @property
    def is_on(self) -> bool | None:
        if self.optimistic:
            return self._optimistic_on
        index = power_function(self.device)
        return self.status[index] == 1 if len(self.status) > index else None

    @property
    def brightness(self) -> int | None:
        if not self._dimmer:
            return None
        if self.optimistic:
            return self._optimistic_brightness
        index = dim_function(self.device)
        if len(self.status) <= index or not isinstance(self.status[index], (int, float)):
            return None
        return max(0, min(255, round(self.status[index] * 255 / max_brightness(self.device))))

    @callback
    def _handle_coordinator_update(self) -> None:
        if self.optimistic:
            p, b = power_function(self.device), dim_function(self.device)
            on_matches = len(self.status) > p and (self.status[p] == 1) == self._optimistic_on
            brightness_matches = self._optimistic_brightness is None or (
                len(self.status) > b
                and abs(
                    round(self.status[b] * 255 / max_brightness(self.device))
                    - self._optimistic_brightness
                )
                <= math.ceil(255 / max_brightness(self.device))
            )
            if on_matches and brightness_matches:
                self._optimistic_until = 0
        super()._handle_coordinator_update()

    def _set_optimistic(self, on: bool, brightness: int | None = None) -> None:
        self._optimistic_on = on
        self._optimistic_brightness = brightness
        interval = self.coordinator.update_interval
        self._optimistic_until = (
            time.monotonic() + (interval.total_seconds() if interval else 30) + 5
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        if brightness == 0:
            await self.async_turn_off()
            return
        if brightness is not None and self._dimmer:
            brightness = max(1, min(255, int(brightness)))
            level = max(1, round(brightness * max_brightness(self.device) / 255))
            await self.coordinator.async_command(self.device, dim_function(self.device), level)

        await self.coordinator.async_command(self.device, power_function(self.device), 1)
        self._set_optimistic(True, brightness if self._dimmer else None)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_command(self.device, power_function(self.device), 0)
        self._set_optimistic(False)
        await self.coordinator.async_request_refresh()
