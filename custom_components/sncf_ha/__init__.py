"""SNCF HA: next trains between two stations, with cancellation handling."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SncfApiClient
from .coordinator import SncfConfigEntry, SncfCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.EVENT]


async def async_setup_entry(hass: HomeAssistant, entry: SncfConfigEntry) -> bool:
    """Set up a monitored route."""
    client = SncfApiClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    coordinator = SncfCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_update))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SncfConfigEntry) -> bool:
    """Unload a route."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_on_update(hass: HomeAssistant, entry: SncfConfigEntry) -> None:
    """Reload when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
