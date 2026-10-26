from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import IcsAuthError, IcsClient, IcsDevice, IcsError
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SLEEP,
    CONF_TRIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLEEP,
    DEFAULT_TRIES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class Ics2000Coordinator(DataUpdateCoordinator[dict[int, list]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: IcsClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(
                seconds=max(5, entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
            ),
        )
        self.client = client
        self.hub_identifier = (DOMAIN, entry.entry_id)
        self.tries = entry.options.get(CONF_TRIES, DEFAULT_TRIES)
        self.delay = entry.options.get(CONF_SLEEP, DEFAULT_SLEEP)

    async def _async_update_data(self) -> dict[int, list]:
        try:
            return await self.client.async_get_statuses()
        except IcsAuthError as err:
            raise ConfigEntryAuthFailed("Account credentials rejected") from err
        except IcsError as err:
            raise UpdateFailed(str(err)) from err

    async def async_command(self, device: IcsDevice, function: int, value: int) -> None:
        try:
            await self.client.async_send(device.id, function, value, self.tries, self.delay)
        except IcsAuthError as err:
            raise ConfigEntryAuthFailed("Account credentials rejected") from err
        except IcsError as err:
            raise HomeAssistantError("Could not send the command to the ICS-2000") from err
