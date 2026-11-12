"""Actions (services) for the charger timer and clock."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import ElectroSLocalCoordinator

SERVICE_SET_TIMER = "set_timer"
SERVICE_CLEAR_TIMER = "clear_timer"
SERVICE_SYNC_CLOCK = "sync_clock"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_START = "start"
ATTR_END = "end"

_BASE = {vol.Optional(ATTR_CONFIG_ENTRY_ID): cv.string}


def _different(data: dict) -> dict:
    # The charger treats start == end as "no window"; reject it instead of silently turning the timer off.
    if data[ATTR_START].replace(second=0, microsecond=0) == data[ATTR_END].replace(second=0, microsecond=0):
        raise vol.Invalid("start and end must differ")
    return data


SET_TIMER_SCHEMA = vol.All(
    vol.Schema({**_BASE, vol.Required(ATTR_START): cv.time, vol.Required(ATTR_END): cv.time}),
    _different,
)
BASE_SCHEMA = vol.Schema(_BASE)


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> ElectroSLocalCoordinator:
    """The charger the action is for. config_entry_id may be left out when there is one charger."""
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.state is ConfigEntryState.LOADED]
    entry_id = call.data.get(ATTR_CONFIG_ENTRY_ID)
    if entry_id:
        entries = [e for e in entries if e.entry_id == entry_id]
    if len(entries) != 1:
        raise ServiceValidationError(
            "Зарядку не знайдено або вона не на зв'язку"
            if not entries
            else "Зарядок кілька: вкажіть config_entry_id"
        )
    return entries[0].runtime_data


def async_setup_services(hass: HomeAssistant) -> None:
    async def set_timer(call: ServiceCall) -> None:
        start = call.data[ATTR_START].replace(second=0, microsecond=0)
        end = call.data[ATTR_END].replace(second=0, microsecond=0)
        await _coordinator(hass, call).async_set_timer((start, end))

    async def clear_timer(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_set_timer(None)

    async def sync_clock(call: ServiceCall) -> None:
        await _coordinator(hass, call).async_sync_clock()

    hass.services.async_register(DOMAIN, SERVICE_SET_TIMER, set_timer, schema=SET_TIMER_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_CLEAR_TIMER, clear_timer, schema=BASE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SYNC_CLOCK, sync_clock, schema=BASE_SCHEMA)
