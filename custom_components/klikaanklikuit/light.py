"""Light platform for ICS2000 - lights and dimmers, state polled via coordinator."""
from __future__ import annotations

import logging
import math
import time
from typing import Any

from ics2000_python.Devices import Dimmer, Light

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import Ics2000Coordinator

_LOGGER = logging.getLogger(__name__)

# NOTE on brightness mapping: the original integration divided HA's 0-255
# brightness by 17 to get a KAKU dim level of 1-15, based on a code comment in
# this component. The ics2000_python library's own Hub.dim() docstring says
# the level range is 1-10. These two claims contradict each other and neither
# is verified against real hardware here. This keeps the original 1-15
# mapping since that's what has actually been running in production - if dim
# levels look wrong (e.g. capped out too early), this is the first place to
# check.
KAKU_DIM_DIVISOR = 17


def _send_with_retries(tries: int, sleep: int, func, *args) -> None:
    for i in range(tries):
        func(*args)
        if i != tries - 1:
            time.sleep(sleep)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: Ics2000Coordinator = data["coordinator"]
    tries: int = data["tries"]
    sleep: int = data["sleep"]

    hub_identifier = data["hub_identifier"]
    entities = [
        Ics2000Light(coordinator, device, tries, sleep, hub_identifier)
        for device in coordinator.hub.devices
        if isinstance(device, (Light, Dimmer))
    ]
    async_add_entities(entities)


class Ics2000Light(CoordinatorEntity[Ics2000Coordinator], LightEntity):
    """A KlikAanKlikUit light or dimmer.

    State (on/off, brightness) comes from the coordinator, which polls the
    ICS2000 cloud. This reflects changes made via the Trust app or through
    the hub, but NOT a classic 433MHz remote talking directly to the receiver
    - that traffic never reaches the cloud, so it's invisible here. There is
    no way around this with the current hardware/library; it's a one-way RF
    limitation, not a bug in this integration.
    """

    _attr_has_entity_name = True
    _attr_name = None  # use the device name directly, no suffix

    def __init__(
        self,
        coordinator: Ics2000Coordinator,
        device,
        tries: int,
        sleep: int,
        hub_identifier: tuple[str, str],
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._hub = device.hub
        self._id = device.id
        self.tries = tries
        self.sleep = sleep
        self._attr_unique_id = f"klikaanklikuit-{device.id}"
        is_dimmer = isinstance(device, Dimmer)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(device.id))},
            name=device.name,
            manufacturer=MANUFACTURER,
            model="Dimmer" if is_dimmer else "Light/Switch",
            via_device=hub_identifier,
        )
        if is_dimmer:
            self._attr_color_mode = ColorMode.BRIGHTNESS
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
        else:
            self._attr_color_mode = ColorMode.ONOFF
            self._attr_supported_color_modes = {ColorMode.ONOFF}

    @property
    def _status(self) -> list:
        return self.coordinator.data.get(self._id, [])

    @property
    def is_on(self) -> bool | None:
        status = self._status
        if not status:
            return None
        return status[0] == 1

    @property
    def brightness(self) -> int | None:
        status = self._status
        if not isinstance(self._device, Dimmer) or len(status) < 2:
            return None
        return min(255, round(status[1] * KAKU_DIM_DIVISOR))

    async def async_turn_on(self, **kwargs: Any) -> None:
        if ATTR_BRIGHTNESS in kwargs:
            level = math.ceil(kwargs[ATTR_BRIGHTNESS] / KAKU_DIM_DIVISOR) or 1
            await self.hass.async_add_executor_job(
                _send_with_retries, self.tries, self.sleep, self._hub.dim, self._id, level
            )
        else:
            await self.hass.async_add_executor_job(
                _send_with_retries, self.tries, self.sleep, self._hub.turn_on, self._id
            )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.hass.async_add_executor_job(
            _send_with_retries, self.tries, self.sleep, self._hub.turn_off, self._id
        )
        await self.coordinator.async_request_refresh()
