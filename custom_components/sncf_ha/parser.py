"""Turn Navitia journey payloads into Train objects (no Home Assistant import).

Cancellation rules (a train is CANCELLED when any of these holds):
  1. a linked disruption has effect NO_SERVICE, is active/future and covers
     the scheduled departure;
  2. a linked disruption deletes the origin or destination stop of *our*
     route (the train runs, but not for this trip);
  3. the journey itself is flagged with status NO_SERVICE.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from .const import API_DATETIME_FORMAT, API_TIMEZONE, EFFECT_NO_SERVICE
from .models import Train, TrainStatus

_LOGGER = logging.getLogger(__name__)

_ACTIVE_STATUSES = frozenset({"active", "future"})
_DELETED_STOP_EFFECTS = frozenset({"deleted", "deleted_for_detour"})
_DELAY_THRESHOLD = timedelta(minutes=1)


def parse_datetime(value: str) -> datetime:
    """Parse a Navitia datetime (local time of the coverage)."""
    return datetime.strptime(value, API_DATETIME_FORMAT).replace(tzinfo=API_TIMEZONE)


def parse_journeys(payload: dict[str, Any], *, origin_id: str, destination_id: str) -> list[Train]:
    """Parse a /journeys payload. Malformed journeys are skipped, never fatal."""
    disruptions = {d["id"]: d for d in payload.get("disruptions") or [] if "id" in d}
    route_stops = frozenset({origin_id, destination_id})
    trains: dict[str, Train] = {}
    for journey in payload.get("journeys") or []:
        section = _first_public_transport_section(journey)
        if section is None:
            continue
        try:
            train = _build_train(journey, section, disruptions, route_stops)
        except (KeyError, TypeError, ValueError):
            _LOGGER.debug("Skipping malformed journey", exc_info=True)
            continue
        trains.setdefault(train.id, train)
    return list(trains.values())


def merge_trains(
    realtime: list[Train],
    scheduled: list[Train],
    limit: int,
) -> list[Train]:
    """Merge the realtime and base-schedule views of the same route.

    The realtime view has the accurate times but may omit a cancelled train
    altogether; the base-schedule view still lists it, together with its
    NO_SERVICE disruption. A cancellation always wins.
    """
    merged = {train.id: train for train in realtime}
    for train in scheduled:
        if train.is_cancelled:
            merged[train.id] = train
    return sorted(merged.values(), key=lambda t: t.scheduled_departure)[:limit]


def _first_public_transport_section(journey: dict[str, Any]) -> dict[str, Any] | None:
    for section in journey.get("sections") or []:
        if section.get("type") == "public_transport":
            return section
    return None


def _build_train(
    journey: dict[str, Any],
    section: dict[str, Any],
    disruptions: dict[str, dict[str, Any]],
    route_stops: frozenset[str],
) -> Train:
    info = section.get("display_informations") or {}
    departure = parse_datetime(section["departure_date_time"])
    arrival = parse_datetime(section["arrival_date_time"])
    scheduled_departure = parse_datetime(
        section.get("base_departure_date_time") or section["departure_date_time"]
    )
    scheduled_arrival = parse_datetime(
        section.get("base_arrival_date_time") or section["arrival_date_time"]
    )

    linked = _linked_disruptions(info, disruptions)
    cancelled, message = _detect_cancellation(journey, linked, route_stops, scheduled_departure)

    if cancelled:
        status = TrainStatus.CANCELLED
    elif departure - scheduled_departure >= _DELAY_THRESHOLD:
        status = TrainStatus.DELAYED
    else:
        status = TrainStatus.ON_TIME

    number = str(info.get("headsign") or "")
    return Train(
        # Number + scheduled departure is stable between realtime and base views.
        id=f"{number or 'unknown'}@{scheduled_departure.isoformat()}",
        number=number,
        direction=str(info.get("direction") or ""),
        mode=str(info.get("commercial_mode") or info.get("network") or ""),
        scheduled_departure=scheduled_departure,
        scheduled_arrival=scheduled_arrival,
        departure=departure,
        arrival=arrival,
        status=status,
        message=message,
    )


def _linked_disruptions(
    info: dict[str, Any], disruptions: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    ids = [link.get("id") for link in info.get("links") or [] if link.get("type") == "disruption"]
    return [disruptions[i] for i in ids if i in disruptions]


def _detect_cancellation(
    journey: dict[str, Any],
    linked: list[dict[str, Any]],
    route_stops: frozenset[str],
    scheduled_departure: datetime,
) -> tuple[bool, str | None]:
    for disruption in linked:
        if disruption.get("status") not in _ACTIVE_STATUSES:
            continue
        if not _period_covers(disruption, scheduled_departure):
            continue
        effect = (disruption.get("severity") or {}).get("effect")
        if effect == EFFECT_NO_SERVICE or _deletes_route_stop(disruption, route_stops):
            return True, _message(disruption)
    if journey.get("status") == EFFECT_NO_SERVICE:
        return True, next((m for d in linked if (m := _message(d))), None)
    return False, None


def _period_covers(disruption: dict[str, Any], moment: datetime) -> bool:
    periods = disruption.get("application_periods") or []
    if not periods:
        return True
    for period in periods:
        try:
            if parse_datetime(period["begin"]) <= moment <= parse_datetime(period["end"]):
                return True
        except (KeyError, TypeError, ValueError):
            continue
    return False


def _deletes_route_stop(disruption: dict[str, Any], route_stops: frozenset[str]) -> bool:
    for impacted in disruption.get("impacted_objects") or []:
        for stop in impacted.get("impacted_stops") or []:
            stop_area = ((stop.get("stop_point") or {}).get("stop_area") or {}).get("id")
            if stop_area not in route_stops:
                continue
            if stop.get("stop_time_effect") in _DELETED_STOP_EFFECTS:
                return True
            if "deleted" in (stop.get("departure_status"), stop.get("arrival_status")):
                return True
    return False


def _message(disruption: dict[str, Any]) -> str | None:
    for message in disruption.get("messages") or []:
        if text := message.get("text"):
            return str(text)
    return None
