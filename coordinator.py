"""Data update coordinator."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SncfApiClient, SncfApiError, SncfAuthError
from .const import (
    CONF_DESTINATION_ID,
    CONF_ORIGIN_ID,
    CONF_TRAIN_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TRAIN_COUNT,
    DOMAIN,
)
from .models import Train

_LOGGER = logging.getLogger(__name__)

type SncfConfigEntry = ConfigEntry[SncfCoordinator]


class SncfCoordinator(DataUpdateCoordinator[list[Train]]):
    """Fetch the upcoming trains of one route."""

    config_entry: SncfConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SncfConfigEntry, client: SncfApiClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )
        self._client = client

    async def _async_update_data(self) -> list[Train]:
        try:
            return await self._client.async_get_trains(
                self.config_entry.data[CONF_ORIGIN_ID],
                self.config_entry.data[CONF_DESTINATION_ID],
                int(self.config_entry.options.get(CONF_TRAIN_COUNT, DEFAULT_TRAIN_COUNT)),
            )
        except SncfAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SncfApiError as err:
            raise UpdateFailed(str(err)) from err
