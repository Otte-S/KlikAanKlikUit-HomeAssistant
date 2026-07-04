"""DataUpdateCoordinator for the KlikAanKlikUit (ICS-2000) integration.

The ics2000_python library exposes Hub.get_device_status(entity_id), which
polls trustsmartcloud2.com for the last known status of a device (as reported
by the Trust app, Zigbee devices, or commands sent through the hub itself).

Note this is NOT live feedback from the physical device: classic KlikAanKlikUit
433MHz devices are one-way RF, so a remote that talks directly to a receiver
(bypassing the ICS2000 hub) will never show up here. Only state changes the
ICS2000 cloud actually knows about are visible through this polling.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from ics2000_python.Core import CoreException, Hub

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class Ics2000Coordinator(DataUpdateCoordinator[dict[int, list]]):
    """Polls the ICS2000 cloud for the status of every known device."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        hub: Hub,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=max(scan_interval, 5)),
        )
        self.hub = hub
        self.entry = entry

    async def _async_update_data(self) -> dict[int, list]:
        try:
            return await self.hass.async_add_executor_job(self._poll_all)
        except CoreException as err:
            raise UpdateFailed(f"Could not reach ICS2000 cloud: {err}") from err

    def _poll_all(self) -> dict[int, list]:
        """Blocking: fetch status for every device. Runs in the executor."""
        statuses: dict[int, list] = {}
        for device in self.hub.devices:
            device_id = device.id
            try:
                statuses[device_id] = self.hub.get_device_status(device_id)
            except Exception as err:  # noqa: BLE001 - one bad device shouldn't kill the poll
                _LOGGER.debug(
                    "Could not fetch status for %s (%s): %s", device.name, device_id, err
                )
                statuses[device_id] = []
        return statuses

    async def async_refresh_device_list(self) -> None:
        """Re-sync the device list from the cloud (new/removed devices).

        Not called automatically - devices added in the Trust app after setup
        won't appear until Home Assistant is restarted or this is triggered,
        since entities are only created once at platform setup.
        """
        await self.hass.async_add_executor_job(self.hub.pull_devices)
