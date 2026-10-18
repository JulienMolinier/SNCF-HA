"""Which trains make up today's board, and when to poll (no Home Assistant import).

The board is the N trains leaving from the start time. Once they have all left,
the integration idles until the next start time and shows tomorrow's trains.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from .models import Train


@dataclass(frozen=True, slots=True)
class Search:
    """Where to start looking for trains, and whether the board is live."""

    search_from: datetime
    active: bool


def plan_search(now: datetime, start: time, finished: bool) -> Search:
    """Decide what to fetch.

    - before today's start time: the trains from the start time, not live;
    - board finished (all trains left): tomorrow's trains from the start time, not live;
    - otherwise: the next trains from now, live.
    """
    today_start = datetime.combine(now.date(), start, tzinfo=now.tzinfo)
    if now < today_start:
        return Search(today_start, active=False)
    if finished:
        return Search(today_start + timedelta(days=1), active=False)
    return Search(now, active=True)


def last_departure(trains: list[Train]) -> datetime | None:
    """Scheduled departure of the last train: the end of the board."""
    return max((t.scheduled_departure for t in trains), default=None)


def trim_to_board(
    trains: list[Train], cutoff: datetime | None, now: datetime
) -> tuple[list[Train], datetime | None, bool]:
    """Live refresh: keep only the trains of today's board.

    `cutoff` is the scheduled departure of the board's last train, learnt before
    the start time. If unknown (e.g. after a restart) it is taken from this
    refresh. Returns (board, cutoff, finished); the board is finished once no
    train is left and the last one's scheduled time has passed.
    """
    if cutoff is None:
        cutoff = last_departure(trains)
    if cutoff is None:
        return [], None, False
    board = [t for t in trains if t.scheduled_departure <= cutoff]
    return board, cutoff, not board and now >= cutoff
