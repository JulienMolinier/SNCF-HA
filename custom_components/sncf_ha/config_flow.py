"""Config flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_API_KEY, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .api import SncfApiClient, SncfApiError, SncfAuthError, SncfRateLimitError
from .const import (
    CONF_DESTINATION_ID,
    CONF_DESTINATION_NAME,
    CONF_DESTINATION_QUERY,
    CONF_ORIGIN_ID,
    CONF_ORIGIN_NAME,
    CONF_ORIGIN_QUERY,
    CONF_TIME_START,
    CONF_TRAIN_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIME_START,
    DEFAULT_TRAIN_COUNT,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MAX_TRAIN_COUNT,
    MIN_SCAN_INTERVAL,
    MIN_TRAIN_COUNT,
)
from .models import Station

_API_KEY_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): _API_KEY_SELECTOR})
_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): _API_KEY_SELECTOR,
        vol.Required(CONF_ORIGIN_QUERY): str,
        vol.Required(CONF_DESTINATION_QUERY): str,
    }
)


def _board_fields(defaults: Mapping[str, Any]) -> dict[Any, Any]:
    """Schema fields shared by the creation step and the options: start time, train count."""
    return {
        vol.Required(
            CONF_TIME_START, default=defaults.get(CONF_TIME_START, DEFAULT_TIME_START)
        ): TimeSelector(),
        vol.Required(
            CONF_TRAIN_COUNT, default=defaults.get(CONF_TRAIN_COUNT, DEFAULT_TRAIN_COUNT)
        ): NumberSelector(
            NumberSelectorConfig(
                min=MIN_TRAIN_COUNT,
                max=MAX_TRAIN_COUNT,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
    }


def _error_key(err: SncfApiError) -> str:
    if isinstance(err, SncfAuthError):
        return "invalid_auth"
    if isinstance(err, SncfRateLimitError):
        return "rate_limited"
    return "cannot_connect"


def _station_selector(stations: list[Station]) -> SelectSelector:
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=s.id, label=s.name) for s in stations],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


class SncfConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a route: API key, then origin and destination stations."""

    VERSION = 1

    def __init__(self) -> None:
        self._api_key = ""
        self._origins: list[Station] = []
        self._destinations: list[Station] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for the API key and the station names to search."""
        errors: dict[str, str] = {}
        if user_input is not None:
            client = SncfApiClient(async_get_clientsession(self.hass), user_input[CONF_API_KEY])
            try:
                origins = await client.async_search_stations(user_input[CONF_ORIGIN_QUERY])
                destinations = await client.async_search_stations(
                    user_input[CONF_DESTINATION_QUERY]
                )
            except SncfApiError as err:
                errors["base"] = _error_key(err)
            else:
                if not origins:
                    errors[CONF_ORIGIN_QUERY] = "no_station_found"
                if not destinations:
                    errors[CONF_DESTINATION_QUERY] = "no_station_found"
                if not errors:
                    self._api_key = user_input[CONF_API_KEY]
                    self._origins, self._destinations = origins, destinations
                    return await self.async_step_stations()
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(_USER_SCHEMA, user_input),
            errors=errors,
        )

    async def async_step_stations(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Pick the exact origin and destination stations."""
        errors: dict[str, str] = {}
        if user_input is not None:
            origin_id, destination_id = user_input[CONF_ORIGIN_ID], user_input[CONF_DESTINATION_ID]
            if origin_id == destination_id:
                errors["base"] = "same_station"
            else:
                await self.async_set_unique_id(f"{origin_id}>{destination_id}")
                self._abort_if_unique_id_configured()
                origin = next(s for s in self._origins if s.id == origin_id)
                destination = next(s for s in self._destinations if s.id == destination_id)
                return self.async_create_entry(
                    title=f"{origin.name} → {destination.name}",
                    data={
                        CONF_API_KEY: self._api_key,
                        CONF_ORIGIN_ID: origin.id,
                        CONF_ORIGIN_NAME: origin.name,
                        CONF_DESTINATION_ID: destination.id,
                        CONF_DESTINATION_NAME: destination.name,
                    },
                    options={
                        CONF_TIME_START: user_input[CONF_TIME_START],
                        CONF_TRAIN_COUNT: int(user_input[CONF_TRAIN_COUNT]),
                    },
                )
        schema = vol.Schema(
            {
                vol.Required(CONF_ORIGIN_ID): _station_selector(self._origins),
                vol.Required(CONF_DESTINATION_ID): _station_selector(self._destinations),
                **_board_fields({}),
            }
        )
        return self.async_show_form(step_id="stations", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Start the reauth flow when the API key is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for a new API key."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if (error := await _async_validate_key(self.hass, user_input[CONF_API_KEY])) is None:
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data_updates=user_input
                )
            errors["base"] = error
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=_REAUTH_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return SncfOptionsFlow()


async def _async_validate_key(hass: HomeAssistant, api_key: str) -> str | None:
    """Return an error key, or None if the key works."""
    try:
        await SncfApiClient(async_get_clientsession(hass), api_key).async_check_auth()
    except SncfApiError as err:
        return _error_key(err)
    return None


class SncfOptionsFlow(OptionsFlow):
    """Refresh interval, start time and number of trains."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_TIME_START: user_input[CONF_TIME_START],
                    CONF_TRAIN_COUNT: int(user_input[CONF_TRAIN_COUNT]),
                }
            )
        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL,
                        max=MAX_SCAN_INTERVAL,
                        step=60,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.BOX,
                    )
                ),
                **_board_fields(options),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
