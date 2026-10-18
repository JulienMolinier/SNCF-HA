"""Tests for the board logic."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from custom_components.sncf_ha.models import Train, TrainStatus
from custom_components.sncf_ha.window import last_departure, plan_search, trim_to_board

PARIS = ZoneInfo("Europe/Paris")
START = time(7, 0)


def at(hour: int, minute: int = 0, day: int = 16) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=PARIS)


def train(hour: int, minute: int = 0) -> Train:
    dep = at(hour, minute)
    return Train(
        id=f"{hour}:{minute}",
        number=str(hour),
        direction="Nice",
        mode="TER",
        scheduled_departure=dep,
        scheduled_arrival=dep + timedelta(minutes=30),
        departure=dep,
        arrival=dep + timedelta(minutes=30),
        status=TrainStatus.ON_TIME,
    )


def test_before_start_looks_from_start_and_is_not_live() -> None:
    search = plan_search(at(4), START, finished=False)
    assert search.search_from == at(7)
    assert not search.active


def test_after_start_looks_from_now_and_is_live() -> None:
    search = plan_search(at(7, 30), START, finished=False)
    assert search.search_from == at(7, 30)
    assert search.active


def test_finished_board_waits_for_tomorrow() -> None:
    search = plan_search(at(9), START, finished=True)
    assert search.search_from == at(7, day=17)
    assert not search.active


def test_new_day_before_start_ignores_finished_flag() -> None:
    search = plan_search(at(1, day=17), START, finished=True)
    assert search.search_from == at(7, day=17)


def test_last_departure() -> None:
    assert last_departure([]) is None
    assert last_departure([train(7), train(8), train(7, 30)]) == at(8)


def test_trim_drops_trains_after_the_board_and_keeps_cutoff() -> None:
    board, cutoff, finished = trim_to_board([train(8), train(9), train(10)], at(8), at(7, 30))
    assert [t.number for t in board] == ["8"]
    assert cutoff == at(8)
    assert not finished


def test_trim_learns_cutoff_when_unknown() -> None:
    board, cutoff, finished = trim_to_board([train(8), train(9)], None, at(7, 30))
    assert len(board) == 2
    assert cutoff == at(9)
    assert not finished


def test_board_finished_when_all_left_and_cutoff_passed() -> None:
    board, cutoff, finished = trim_to_board([train(10)], at(8), at(8, 1))
    assert board == []
    assert cutoff == at(8)
    assert finished


def test_empty_answer_before_cutoff_is_not_finished() -> None:
    _, _, finished = trim_to_board([], at(8), at(7, 30))
    assert not finished


def test_nothing_known_is_not_finished() -> None:
    assert trim_to_board([], None, at(7, 30)) == ([], None, False)
