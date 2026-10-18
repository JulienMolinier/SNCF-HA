"""Data update coordinator."""

from __future__ import annotations

import logging
from datetime import datetime, time, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import SncfApiClient, SncfApiError, SncfAuthError
from .changes import detect_new_cancellations
from .const import (
    API_TIMEZONE,
    CONF_DESTINATION_ID,
    CONF_ORIGIN_ID,
    CONF_TIME_START,
    CONF_TRAIN_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIME_START,
    DEFAULT_TRAIN_COUNT,
    DOMAIN,
    IDLE_SCAN_INTERVAL,
)
from .models import Train
from .window import plan_search

_LOGGER = logging.getLogger(__name__)

type SncfConfigEntry = ConfigEntry[SncfCoordinator]


class SncfCoordinator(DataUpdateCoordinator[list[Train]]):
    """Fetch the next trains of one route."""

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
        self._start = time.fromisoformat(entry.options.get(CONF_TIME_START, DEFAULT_TIME_START))
        # Trains newly cancelled by the last successful refresh (empty otherwise).
        self.cancellations: list[Train] = []

    async def _async_update_data(self) -> list[Train]:
        self.cancellations = []
        now = dt_util.now(API_TIMEZONE)
        search = plan_search(now, self._start)
        self._schedule_next_interval(now, search.active, search.search_from)
        try:
            trains = await self._client.async_get_trains(
                self.config_entry.data[CONF_ORIGIN_ID],
                self.config_entry.data[CONF_DESTINATION_ID],
                int(self.config_entry.options.get(CONF_TRAIN_COUNT, DEFAULT_TRAIN_COUNT)),
                search_from=search.search_from,
            )
        except SncfAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except SncfApiError as err:
            raise UpdateFailed(str(err)) from err
        # No alerts on the very first refresh (e.g. after a restart).
        if self.data is not None:
            self.cancellations = detect_new_cancellations(self.data, trains)
        return trains

    def _schedule_next_interval(self, now: datetime, active: bool, search_from: datetime) -> None:
        """Poll at the chosen interval once started; hourly before (waking up at the start)."""
        if active:
            self.update_interval = self._active_interval
            return
        self.update_interval = max(
            self._active_interval,
            min(timedelta(seconds=IDLE_SCAN_INTERVAL), search_from - now),
        )
