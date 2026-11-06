"""Tests for the journey parser and cancellation detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from custom_components.sncf_ha.models import TrainStatus
from custom_components.sncf_ha.parser import merge_trains, parse_journeys

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
                    {
                        "stop_point": {"id": sa.replace("stop_area", "stop_point") + ":Train"},
                        "departure_status": eff,
                        "arrival_status": eff,
                        "stop_time_effect": eff,
                    }
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
    assert sum(t.is_cancelled for t in merged) == 1


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


# --- Real data -------------------------------------------------------------
# tests/fixtures/disruption_reduced_service.json is a real disruption captured on
# 2026-10-27 (train 881203, Menton direction, 08:03 from Antibes): effect
# REDUCED_SERVICE, deleted stops listed as stop_point ids (no stop_area), and the
# train ends its trip at Cannes. Its status was "active" while it ran.

ANTIBES = "stop_area:SNCF:87757674"
NICE_ST_AUGUSTIN = "stop_area:SNCF:87756254"


def _real_disruption() -> dict[str, Any]:
    path = Path(__file__).parent / "fixtures" / "disruption_reduced_service.json"
    return json.loads(path.read_text())


def _stop_area(name: str) -> str:
    disruption = _real_disruption()
    for stop in disruption["impacted_objects"][0]["impacted_stops"]:
        if stop["stop_point"]["name"] == name:
            return (
                stop["stop_point"]["id"].replace("stop_point", "stop_area").removesuffix(":Train")
            )
    raise AssertionError(name)


def _real_payload(disruption: dict[str, Any]) -> dict[str, Any]:
    j = journey("881203", "20261027T080300", "20261027T082300", links=(disruption["id"],))
    return {"journeys": [j], "disruptions": [disruption]}


def _parse_real(origin: str, destination: str, disruption: dict[str, Any] | None = None):
    payload = _real_payload(disruption or _real_disruption())
    return parse_journeys(payload, origin_id=origin, destination_id=destination)


def test_real_partial_cancellation_antibes_to_nice() -> None:
    (train,) = _parse_real(ANTIBES, NICE_ST_AUGUSTIN)
    assert train.status is TrainStatus.CANCELLED
    assert train.message == "Défaillance de matériel"


def test_real_train_ending_at_cannes_is_fine_for_a_trip_ending_at_cannes() -> None:
    # Cannes La Bocca -> Cannes: the train still runs there (its departure from
    # Cannes is deleted, but nobody boards there).
    (train,) = _parse_real(_stop_area("Cannes La Bocca"), _stop_area("Cannes"))
    assert not train.is_cancelled


def test_real_train_cannot_be_boarded_at_cannes() -> None:
    (train,) = _parse_real(_stop_area("Cannes"), NICE_ST_AUGUSTIN)
    assert train.is_cancelled


def test_real_disruption_once_past_is_ignored() -> None:
    (train,) = _parse_real(ANTIBES, NICE_ST_AUGUSTIN, {**_real_disruption(), "status": "past"})
    assert not train.is_cancelled
