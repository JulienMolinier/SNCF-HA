"""Tests for the search planning."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from custom_components.sncf_ha.window import plan_search

PARIS = ZoneInfo("Europe/Paris")
START = time(7, 0)


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 10, 16, hour, minute, tzinfo=PARIS)


def test_before_start_looks_from_start_and_is_not_live() -> None:
    search = plan_search(at(4), START)
    assert search.search_from == at(7)
    assert not search.active


def test_at_start_is_live_from_now() -> None:
    search = plan_search(at(7), START)
    assert search.search_from == at(7)
    assert search.active


def test_after_start_looks_from_now() -> None:
    search = plan_search(at(18, 30), START)
    assert search.search_from == at(18, 30)
    assert search.active
