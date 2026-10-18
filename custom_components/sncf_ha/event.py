"""Event entity: fires when a train gets cancelled."""

from __future__ import annotations

from homeassistant.components.event import EventEntity, EventEntityDescription
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import SncfConfigEntry, SncfCoordinator
from .entity import SncfEntity

EVENT_CANCELLED = "cancelled"

DESCRIPTION = EventEntityDescription(
    key="cancellation",
    translation_key="cancellation",
    event_types=[EVENT_CANCELLED],
)


async def async_setup_entry(
    hass: HomeAssistant, entry: SncfConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the event entity."""
    async_add_entities([SncfCancellationEvent(entry.runtime_data)])


class SncfCancellationEvent(SncfEntity, EventEntity):
    """One event per newly cancelled train, with the train's details as attributes."""

    def __init__(self, coordinator: SncfCoordinator) -> None:
        super().__init__(coordinator, DESCRIPTION)

    @callback
    def _handle_coordinator_update(self) -> None:
        # Write the state after each event, or automations would only see the
        # last one when several trains are cancelled in the same refresh.
        for train in self.coordinator.cancellations:
            self._trigger_event(EVENT_CANCELLED, {**train.as_dict(), "train_id": train.id})
            self.async_write_ha_state()
        super()._handle_coordinator_update()
