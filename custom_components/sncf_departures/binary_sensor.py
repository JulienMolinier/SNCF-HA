"""Binary sensor: is any monitored train cancelled?"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SncfConfigEntry, SncfCoordinator
from .entity import SncfEntity
from .models import cancelled_trains

DESCRIPTION = BinarySensorEntityDescription(
    key="cancellation",
    translation_key="cancellation",
    device_class=BinarySensorDeviceClass.PROBLEM,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SncfConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the binary sensor."""
    async_add_entities([SncfCancellationSensor(entry.runtime_data)])


class SncfCancellationSensor(SncfEntity, BinarySensorEntity):
    """On when at least one upcoming train is cancelled."""

    _unrecorded_attributes = frozenset({"trains"})

    def __init__(self, coordinator: SncfCoordinator) -> None:
        super().__init__(coordinator, DESCRIPTION)

    @property
    def is_on(self) -> bool:
        """Return True if a train is cancelled."""
        return bool(cancelled_trains(self.coordinator.data))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the cancelled trains."""
        return {"trains": [t.as_dict() for t in cancelled_trains(self.coordinator.data)]}
