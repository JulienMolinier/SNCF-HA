"""Tests for cancellation alerts."""

from __future__ import annotations

from datetime import timedelta

from custom_components.sncf_ha.changes import detect_new_cancellations
from custom_components.sncf_ha.models import Train, TrainStatus
from custom_components.sncf_ha.parser import parse_datetime

BASE = parse_datetime("20261016T080000")


def train(number: str, *, delay: int = 0, cancelled: bool = False) -> Train:
    if cancelled:
        status = TrainStatus.CANCELLED
    elif delay:
        status = TrainStatus.DELAYED
    else:
        status = TrainStatus.ON_TIME
    return Train(
        id=f"{number}@2026-10-16",
        number=number,
        direction="Lyon",
        mode="TER",
        scheduled_departure=BASE,
        scheduled_arrival=BASE + timedelta(hours=1),
        departure=BASE + timedelta(minutes=delay),
        arrival=BASE + timedelta(hours=1, minutes=delay),
        status=status,
    )


def numbers(previous: list[Train], current: list[Train]) -> list[str]:
    return [t.number for t in detect_new_cancellations(previous, current)]


def test_train_becomes_cancelled() -> None:
    assert numbers([train("1")], [train("1", cancelled=True)]) == ["1"]
    assert numbers([train("1", delay=6)], [train("1", cancelled=True)]) == ["1"]


def test_already_cancelled_train_is_not_reported_again() -> None:
    assert numbers([train("1", cancelled=True)], [train("1", cancelled=True)]) == []


def test_new_train_already_cancelled_is_reported() -> None:
    assert numbers([], [train("1", cancelled=True)]) == ["1"]


def test_new_train_not_cancelled_is_ignored() -> None:
    assert numbers([], [train("1"), train("2", delay=4)]) == []


def test_delays_never_alert() -> None:
    assert numbers([train("1")], [train("1", delay=5)]) == []
    assert numbers([train("1", delay=5)], [train("1", delay=12)]) == []


def test_reinstated_and_departed_trains_are_ignored() -> None:
    assert numbers([train("1", cancelled=True)], [train("1")]) == []
    assert numbers([train("1", cancelled=True)], []) == []


def test_several_cancellations_in_one_refresh() -> None:
    previous = [train("1"), train("2"), train("3")]
    current = [train("1", cancelled=True), train("2"), train("3", cancelled=True)]
    assert numbers(previous, current) == ["1", "3"]
