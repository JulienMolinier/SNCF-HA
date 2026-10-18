"""Constants for the SNCF HA integration (no Home Assistant import)."""

from __future__ import annotations

from typing import Final
from zoneinfo import ZoneInfo

DOMAIN: Final = "sncf_ha"

API_BASE_URL: Final = "https://api.sncf.com/v1"
API_COVERAGE: Final = "sncf"
# Navitia expects and returns datetimes in the coverage's local time.
API_TIMEZONE: Final = ZoneInfo("Europe/Paris")
API_DATETIME_FORMAT: Final = "%Y%m%dT%H%M%S"
REQUEST_TIMEOUT: Final = 20

CONF_ORIGIN_QUERY: Final = "origin_query"
CONF_DESTINATION_QUERY: Final = "destination_query"
CONF_ORIGIN_ID: Final = "origin_id"
CONF_ORIGIN_NAME: Final = "origin_name"
CONF_DESTINATION_ID: Final = "destination_id"
CONF_DESTINATION_NAME: Final = "destination_name"
CONF_TIME_START: Final = "time_start"
CONF_TRAIN_COUNT: Final = "train_count"

# Each refresh costs 2 API requests (realtime + base schedule).
DEFAULT_SCAN_INTERVAL: Final = 300
MIN_SCAN_INTERVAL: Final = 180
MAX_SCAN_INTERVAL: Final = 3600
DEFAULT_TIME_START: Final = "00:00:00"
DEFAULT_TRAIN_COUNT: Final = 5
MIN_TRAIN_COUNT: Final = 1
MAX_TRAIN_COUNT: Final = 20
# Before the start time we only poll slowly (and wake up at the start time).
IDLE_SCAN_INTERVAL: Final = 3600

EFFECT_NO_SERVICE: Final = "NO_SERVICE"
