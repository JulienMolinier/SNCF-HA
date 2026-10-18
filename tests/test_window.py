"""Tests for the monitoring window."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.sncf_ha.window import TimeWindow

PARIS = ZoneInfo("Europe/Paris")
WINDOW = TimeWindow.from_strings("06:00", "09:00:00")


def at(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=PARIS)


def test_before_window_targets_today_start() -> None:
    slot = WINDOW.current_or_next_slot(at(16, 4))
    assert not slot.active
    assert slot.start == at(16, 6)
    assert slot.end == at(16, 9)


def test_inside_window_is_active() -> None:
    slot = WINDOW.current_or_next_slot(at(16, 7, 30))
    assert slot.active
    assert slot.end == at(16, 9)


def test_after_window_targets_tomorrow() -> None:
    slot = WINDOW.current_or_next_slot(at(16, 9, 1))
    assert not slot.active
    assert slot.start == at(17, 6)
    assert slot.end == at(17, 9)


def test_invalid_window_rejected() -> None:
    with pytest.raises(ValueError):
        TimeWindow.from_strings("09:00", "06:00")
    with pytest.raises(ValueError):
        TimeWindow.from_strings("nope", "06:00")
