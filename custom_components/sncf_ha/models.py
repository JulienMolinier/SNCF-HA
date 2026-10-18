"""Data models (no Home Assistant import)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any


class TrainStatus(StrEnum):
    """Status of a train for the monitored route."""

    ON_TIME = "on_time"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Station:
    """A station returned by the places search."""

    id: str
    name: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Train:
    """A direct train between the configured origin and destination."""

    id: str
    number: str
    direction: str
    mode: str
    scheduled_departure: datetime
    scheduled_arrival: datetime
    departure: datetime
    arrival: datetime
    status: TrainStatus
    message: str | None = None

    @property
    def is_cancelled(self) -> bool:
        """Return True if the train does not run (fully or on our route)."""
        return self.status is TrainStatus.CANCELLED

    @property
    def delay_minutes(self) -> int:
        """Departure delay in whole minutes (0 for cancelled trains)."""
        if self.is_cancelled:
            return 0
        return max(int((self.departure - self.scheduled_departure) / timedelta(minutes=1)), 0)

    @property
    def arrival_delay_minutes(self) -> int:
        """Arrival delay in whole minutes (0 for cancelled trains)."""
        if self.is_cancelled:
            return 0
        return max(int((self.arrival - self.scheduled_arrival) / timedelta(minutes=1)), 0)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation for state attributes."""
        return {
            "number": self.number,
            "direction": self.direction,
            "mode": self.mode,
            "status": self.status.value,
            "scheduled_departure": self.scheduled_departure.isoformat(),
            "departure": self.departure.isoformat(),
            "scheduled_arrival": self.scheduled_arrival.isoformat(),
            "arrival": self.arrival.isoformat(),
            "delay_minutes": self.delay_minutes,
            "arrival_delay_minutes": self.arrival_delay_minutes,
            "message": self.message,
        }


def next_train(trains: list[Train]) -> Train | None:
    """Return the earliest train that actually runs."""
    return min((t for t in trains if not t.is_cancelled), key=lambda t: t.departure, default=None)


def cancelled_trains(trains: list[Train]) -> list[Train]:
    """Return the cancelled trains."""
    return [t for t in trains if t.is_cancelled]
