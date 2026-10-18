"""Data update coordinator."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SncfApiClient, SncfApiError, SncfAuthError
from .const import (
    API_TIMEZONE,
    CONF_DESTINATION_ID,
    CONF_ORIGIN_ID,
    CONF_TIME_END,
    CONF_TIME_START,
    CONF_TRAIN_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIME_END,
    DEFAULT_TIME_START,
    DEFAULT_TRAIN_COUNT,
    DOMAIN,
    IDLE_SCAN_INTERVAL,
)
from .models import Train
from .window import TimeWindow

_LOGGER = logging.getLogger(__name__)

type SncfConfigEntry = ConfigEntry[SncfCoordinator]


class SncfCoordinator(DataUpdateCoordinator[list[Train]]):
    """Fetch the upcoming trains of one route."""

    config_entry: SncfConfigEntry

    def __init__(self, hass: HomeAssistant, entry: SncfConfigEntry, client: SncfApiClient) -> None:
        self._active_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN} {entry.title}",
            update_interval=self._active_interval,
        )
        self._client = client
        self._window = TimeWindow.from_strings(
            entry.options.get(CONF_TIME_START, DEFAULT_TIME_START),
            entry.options.get(CONF_TIME_END, DEFAULT_TIME_END),
        )

    async def _async_update_data(self) -> list[Train]:
        now = dt_util.now(API_TIMEZONE)
        slot = self._window.current_or_next_slot(now)
        self._schedule_next_interval(now, slot.active, slot.start)
        try:
            # Inside the window: trains from now. Outside: those of the next window.
            return await self._client.async_get_trains(
                self.config_entry.data[CONF_ORIGIN_ID],
                self.config_entry.data[CONF_DESTINATION_ID],
                int(self.config_entry.options.get(CONF_TRAIN_COUNT, DEFAULT_TRAIN_COUNT)),
                search_from=max(now, slot.start),
                until=slot.end,
            )
        except SncfAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SncfApiError as err:
            raise UpdateFailed(str(err)) from err

    def _schedule_next_interval(self, now: datetime, active: bool, slot_start: datetime) -> None:
        """Poll normally in the window, slowly outside, and wake up when it opens."""
        if active:
            self.update_interval = self._active_interval
            return
        until_start = slot_start - now
        self.update_interval = max(
            self._active_interval, min(timedelta(seconds=IDLE_SCAN_INTERVAL), until_start)
        )
