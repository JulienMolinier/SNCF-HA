"""Sensor: the list of trains on the monitored window."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SncfConfigEntry, SncfCoordinator
from .entity import SncfEntity
from .models import TrainStatus

DESCRIPTION = SensorEntityDescription(key="trains", translation_key="trains")


async def async_setup_entry(
    hass: HomeAssistant, entry: SncfConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensor."""
    async_add_entities([SncfTrainsSensor(entry.runtime_data)])


class SncfTrainsSensor(SncfEntity, SensorEntity):
    """State: number of trains. Attribute `trains`: status, times and delay of each."""

    # The list changes on every refresh: keep it out of the recorder database.
    _unrecorded_attributes = frozenset({"trains"})

    def __init__(self, coordinator: SncfCoordinator) -> None:
        super().__init__(coordinator, DESCRIPTION)

    @property
    def native_value(self) -> int:
        """Return the number of trains in the window."""
        return len(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the trains."""
        trains = self.coordinator.data
        return {
            "trains": [train.as_dict() for train in trains],
            "cancelled_count": sum(t.is_cancelled for t in trains),
            "delayed_count": sum(t.status is TrainStatus.DELAYED for t in trains),
        }
