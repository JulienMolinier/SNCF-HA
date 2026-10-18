"""Async client for the SNCF (Navitia) API."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_COVERAGE,
    API_DATETIME_FORMAT,
    API_TIMEZONE,
    REQUEST_TIMEOUT,
)
from .models import Station, Train
from .parser import merge_trains, parse_journeys

# Navitia answers 404 for "nothing found": that is an empty result, not a failure.
_NO_RESULT_ERRORS = frozenset(
    {
        "no_solution",
        "no_origin",
        "no_destination",
        "no_origin_nor_destination",
        "date_out_of_bounds",
    }
)


class SncfApiError(Exception):
    """Generic API error."""


class SncfAuthError(SncfApiError):
    """Invalid or unauthorised API key."""


class SncfRateLimitError(SncfApiError):
    """Daily/minute quota exceeded."""


class SncfConnectionError(SncfApiError):
    """Network error or timeout."""


class SncfApiClient:
    """Thin wrapper around the SNCF API."""

    def __init__(self, session: aiohttp.ClientSession, api_key: str) -> None:
        self._session = session
        self._auth = aiohttp.BasicAuth(api_key, "")

    async def async_check_auth(self) -> None:
        """Raise SncfAuthError if the key is rejected."""
        await self._get("")

    async def async_search_stations(self, query: str) -> list[Station]:
        """Search stations by name."""
        payload = await self._get("places", {"q": query, "type[]": "stop_area", "count": 10})
        return [
            Station(id=place["id"], name=place["name"])
            for place in payload.get("places") or []
            if place.get("embedded_type") == "stop_area" and "id" in place and "name" in place
        ]

    async def async_get_trains(
        self,
        origin_id: str,
        destination_id: str,
        count: int,
        *,
        search_from: datetime,
        until: datetime | None = None,
    ) -> list[Train]:
        """Return upcoming direct trains, cancelled ones included.

        Two requests are needed: the realtime view has the accurate times but
        drops cancelled trains, the base-schedule view still lists them with
        their disruption.
        """
        base_params = {
            "from": origin_id,
            "to": destination_id,
            "datetime": search_from.astimezone(API_TIMEZONE).strftime(API_DATETIME_FORMAT),
            "datetime_represents": "departure",
            "count": count,
            "max_nb_transfers": 0,
        }
        realtime, scheduled = await asyncio.gather(
            self._get("journeys", {**base_params, "data_freshness": "realtime"}),
            self._get("journeys", {**base_params, "data_freshness": "base_schedule"}),
        )
        return merge_trains(
            parse_journeys(realtime, origin_id=origin_id, destination_id=destination_id),
            parse_journeys(scheduled, origin_id=origin_id, destination_id=destination_id),
            count,
            until,
        )

    async def _get(self, path: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        url = f"{API_BASE_URL}/coverage/{API_COVERAGE}/{path}".rstrip("/")
        try:
            async with (
                asyncio.timeout(REQUEST_TIMEOUT),
                self._session.get(url, params=params, auth=self._auth) as response,
            ):
                if response.status in (401, 403):
                    raise SncfAuthError("API key rejected")
                if response.status == 429:
                    raise SncfRateLimitError("API quota exceeded")
                payload = await response.json(content_type=None)
                if response.status == 404 and _is_no_result(payload):
                    return {}
                if response.status >= 400:
                    raise SncfApiError(f"Unexpected HTTP status {response.status}")
        except TimeoutError as err:
            raise SncfConnectionError("Timeout while contacting the SNCF API") from err
        except aiohttp.ClientError as err:
            raise SncfConnectionError(f"Error contacting the SNCF API: {err}") from err
        except ValueError as err:
            raise SncfApiError("Invalid JSON received from the SNCF API") from err
        if not isinstance(payload, dict):
            raise SncfApiError("Unexpected payload from the SNCF API")
        return payload


def _is_no_result(payload: Any) -> bool:
    return isinstance(payload, dict) and (payload.get("error") or {}).get("id") in _NO_RESULT_ERRORS
