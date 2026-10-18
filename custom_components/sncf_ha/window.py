"""When to look for trains (no Home Assistant import)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True, slots=True)
class Search:
    """Where to start looking for trains, and whether the board is live."""

    search_from: datetime
    active: bool


def plan_search(now: datetime, start: time) -> Search:
    """Before today's start time: look from the start time (not live yet).

    From the start time on: look from now, so the board shows the next trains.
    """
    today_start = datetime.combine(now.date(), start, tzinfo=now.tzinfo)
    if now < today_start:
        return Search(search_from=today_start, active=False)
    return Search(search_from=now, active=True)
