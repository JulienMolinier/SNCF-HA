"""Detect newly cancelled trains between two refreshes (no Home Assistant import)."""

from __future__ import annotations

from .models import Train


def detect_new_cancellations(previous: list[Train], current: list[Train]) -> list[Train]:
    """Return trains that are cancelled now and were not already known as cancelled.

    A train seen for the first time is reported if it is already cancelled.
    Reinstated or departed trains are ignored.
    """
    already_cancelled = {train.id for train in previous if train.is_cancelled}
    return [t for t in current if t.is_cancelled and t.id not in already_cancelled]
