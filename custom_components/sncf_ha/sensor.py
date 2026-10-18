"""Sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import SncfConfigEntry, SncfCoordinator
from .entity import SncfEntity
from .models import Train, cancelled_trains, next_train


@dataclass(frozen=True, kw_only=True)
class SncfSensorDescription(SensorEntityDescription):
    """Sensor description with value/attribute extractors."""

    value_fn: Callable[[list[Train]], StateType | datetime]
    attrs_fn: Callable[[list[Train]], dict[str, Any]] | None = None


def _next_departure(trains: list[Train]) -> datetime | None:
    train = next_train(trains)
    return train.departure if train else None


def _next_delay(trains: list[Train]) -> int | None:
    train = next_train(trains)
    return train.delay_minutes if train else None


def _next_attrs(trains: list[Train]) -> dict[str, Any]:
    train = next_train(trains)
    return {
        **(train.as_dict() if train else {}),
        "trains": [t.as_dict() for t in trains],
    }


SENSORS: tuple[SncfSensorDescription, ...] = (
    SncfSensorDescription(
        key="next_departure",
        translation_key="next_departure",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_next_departure,
        attrs_fn=_next_attrs,
    ),
    SncfSensorDescription(
        key="next_delay",
        translation_key="next_delay",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=_next_delay,
    ),
    SncfSensorDescription(
        key="cancelled_trains",
        translation_key="cancelled_trains",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda trains: len(cancelled_trains(trains)),
        attrs_fn=lambda trains: {"trains": [t.as_dict() for t in cancelled_trains(trains)]},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SncfConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors."""
    coordinator = entry.runtime_data
    async_add_entities(SncfSensor(coordinator, description) for description in SENSORS)


class SncfSensor(SncfEntity, SensorEntity):
    """A route sensor."""

    entity_description: SncfSensorDescription
    # Train lists change on every refresh: keep them out of the recorder.
    _unrecorded_attributes = frozenset({"trains"})

    def __init__(self, coordinator: SncfCoordinator, description: SncfSensorDescription) -> None:
        super().__init__(coordinator, description)

    @property
    def native_value(self) -> StateType | datetime:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if (fn := self.entity_description.attrs_fn) is None:
            return None
        return fn(self.coordinator.data)
