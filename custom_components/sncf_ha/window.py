"""Monitoring time window (no Home Assistant import)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo


@dataclass(frozen=True, slots=True)
class Slot:
    """A concrete occurrence of the window on a given day."""

    start: datetime
    end: datetime
    active: bool


@dataclass(frozen=True, slots=True)
class TimeWindow:
    """Daily window, in the API's local time. Must not cross midnight."""

    start: time
    end: time

    def __post_init__(self) -> None:
        if self.start >= self.end:
            raise ValueError("Window start must be before its end")

    @classmethod
    def from_strings(cls, start: str, end: str) -> TimeWindow:
        """Build a window from 'HH:MM[:SS]' strings."""
        return cls(time.fromisoformat(start), time.fromisoformat(end))

    def current_or_next_slot(self, now: datetime) -> Slot:
        """Return today's slot, or tomorrow's once today's has ended."""
        start, end = self._bounds(now.date(), now.tzinfo)
        if now > end:
            start, end = self._bounds(now.date() + timedelta(days=1), now.tzinfo)
        return Slot(start=start, end=end, active=start <= now <= end)

    def _bounds(self, day: date, tz: tzinfo | None) -> tuple[datetime, datetime]:
        return (
            datetime.combine(day, self.start, tzinfo=tz),
            datetime.combine(day, self.end, tzinfo=tz),
        )
