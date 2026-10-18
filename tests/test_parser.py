"""Tests for the journey parser and cancellation detection."""

from __future__ import annotations

from typing import Any

from custom_components.sncf_departures.models import TrainStatus, cancelled_trains, next_train
from custom_components.sncf_departures.parser import merge_trains, parse_journeys

ORIGIN = "stop_area:SNCF:87391003"
DEST = "stop_area:SNCF:87686006"
OTHER = "stop_area:SNCF:87000000"


def journey(
    number: str,
    dep: str,
    arr: str,
    *,
    base_dep: str | None = None,
    base_arr: str | None = None,
    links: tuple[str, ...] = (),
    status: str = "",
) -> dict[str, Any]:
    return {
        "status": status,
        "sections": [
            {"type": "waiting"},
            {
                "type": "public_transport",
                "departure_date_time": dep,
                "arrival_date_time": arr,
                "base_departure_date_time": base_dep or dep,
                "base_arrival_date_time": base_arr or arr,
                "display_informations": {
                    "headsign": number,
                    "direction": "Lyon",
                    "commercial_mode": "TER",
                    "links": [{"type": "disruption", "id": i} for i in links],
                },
            },
        ],
    }


def disruption(
    id_: str,
    effect: str,
    *,
    status: str = "active",
    stops: tuple[tuple[str, str], ...] = (),
    begin: str = "20261016T000000",
    end: str = "20261016T235959",
) -> dict[str, Any]:
    return {
        "id": id_,
        "status": status,
        "severity": {"effect": effect},
        "messages": [{"text": "Train supprimé"}],
        "application_periods": [{"begin": begin, "end": end}],
        "impacted_objects": [
            {
                "impacted_stops": [
                    {"stop_point": {"stop_area": {"id": sa}}, "stop_time_effect": eff}
                    for sa, eff in stops
                ]
            }
        ],
    }


def parse(payload: dict[str, Any]):
    return parse_journeys(payload, origin_id=ORIGIN, destination_id=DEST)


def test_on_time() -> None:
    (train,) = parse({"journeys": [journey("8501", "20261016T080000", "20261016T093000")]})
    assert train.status is TrainStatus.ON_TIME
    assert train.delay_minutes == 0
    assert train.number == "8501"


def test_delayed() -> None:
    (train,) = parse(
        {
            "journeys": [
                journey(
                    "8501",
                    "20261016T080700",
                    "20261016T094000",
                    base_dep="20261016T080000",
                    base_arr="20261016T093000",
                )
            ]
        }
    )
    assert train.status is TrainStatus.DELAYED
    assert train.delay_minutes == 7
    assert train.arrival_delay_minutes == 10


def test_cancelled_by_no_service_disruption() -> None:
    payload = {
        "journeys": [journey("8501", "20261016T080000", "20261016T093000", links=("d1",))],
        "disruptions": [disruption("d1", "NO_SERVICE")],
    }
    (train,) = parse(payload)
    assert train.status is TrainStatus.CANCELLED
    assert train.message == "Train supprimé"
    assert train.delay_minutes == 0


def test_cancelled_by_journey_status() -> None:
    payload = {
        "journeys": [
            journey(
                "8501", "20261016T080000", "20261016T093000", links=("d1",), status="NO_SERVICE"
            )
        ],
        "disruptions": [disruption("d1", "SIGNIFICANT_DELAYS", status="past")],
    }
    (train,) = parse(payload)
    assert train.is_cancelled


def test_cancelled_when_destination_stop_deleted() -> None:
    payload = {
        "journeys": [journey("8501", "20261016T080000", "20261016T093000", links=("d1",))],
        "disruptions": [disruption("d1", "REDUCED_SERVICE", stops=((DEST, "deleted"),))],
    }
    (train,) = parse(payload)
    assert train.is_cancelled


def test_deleted_intermediate_stop_is_not_a_cancellation() -> None:
    payload = {
        "journeys": [journey("8501", "20261016T080000", "20261016T093000", links=("d1",))],
        "disruptions": [disruption("d1", "REDUCED_SERVICE", stops=((OTHER, "deleted"),))],
    }
    (train,) = parse(payload)
    assert train.status is TrainStatus.ON_TIME


def test_past_disruption_ignored() -> None:
    payload = {
        "journeys": [journey("8501", "20261016T080000", "20261016T093000", links=("d1",))],
        "disruptions": [disruption("d1", "NO_SERVICE", status="past")],
    }
    (train,) = parse(payload)
    assert not train.is_cancelled


def test_disruption_outside_period_ignored() -> None:
    payload = {
        "journeys": [journey("8501", "20261016T080000", "20261016T093000", links=("d1",))],
        "disruptions": [
            disruption("d1", "NO_SERVICE", begin="20261017T000000", end="20261017T235959")
        ],
    }
    (train,) = parse(payload)
    assert not train.is_cancelled


def test_malformed_journey_is_skipped() -> None:
    bad = journey("8501", "garbage", "20261016T093000")
    good = journey("8502", "20261016T090000", "20261016T103000")
    trains = parse({"journeys": [bad, good]})
    assert [t.number for t in trains] == ["8502"]


def test_empty_payload() -> None:
    assert parse({}) == []


def test_merge_adds_cancelled_train_missing_from_realtime() -> None:
    realtime = parse({"journeys": [journey("8502", "20261016T090000", "20261016T103000")]})
    scheduled = parse(
        {
            "journeys": [
                journey("8501", "20261016T080000", "20261016T093000", links=("d1",)),
                journey("8502", "20261016T090000", "20261016T103000"),
            ],
            "disruptions": [disruption("d1", "NO_SERVICE")],
        }
    )
    merged = merge_trains(realtime, scheduled, limit=5)
    assert [(t.number, t.status) for t in merged] == [
        ("8501", TrainStatus.CANCELLED),
        ("8502", TrainStatus.ON_TIME),
    ]
    assert next_train(merged).number == "8502"  # type: ignore[union-attr]
    assert len(cancelled_trains(merged)) == 1


def test_merge_keeps_realtime_times_for_running_trains() -> None:
    realtime = parse(
        {
            "journeys": [
                journey(
                    "8502",
                    "20261016T090500",
                    "20261016T103000",
                    base_dep="20261016T090000",
                )
            ]
        }
    )
    scheduled = parse({"journeys": [journey("8502", "20261016T090000", "20261016T103000")]})
    (train,) = merge_trains(realtime, scheduled, limit=5)
    assert train.delay_minutes == 5


def test_merge_respects_limit() -> None:
    scheduled = parse(
        {
            "journeys": [
                journey(str(n), f"20261016T0{n}0000", f"20261016T0{n}3000") for n in range(1, 5)
            ]
        }
    )
    assert len(merge_trains([], scheduled, limit=2)) == 0  # only cancelled ones are added
    assert len(merge_trains(scheduled, [], limit=2)) == 2
