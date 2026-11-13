"""Switch platform for ElectroS EV Charger Local integration."""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, DOMAIN
from .coordinator import ElectroSLocalCoordinator
from .entity_ids import suggested_entity_id

_LOGGER = logging.getLogger(__name__)

_CHARGING_STATUSES = {"charging"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ElectroSLocalCoordinator = entry.runtime_data
    host = entry.data[CONF_HOST]
    async_add_entities([ElectroSLocalChargingSwitch(coordinator, entry, host)])


class ElectroSLocalChargingSwitch(CoordinatorEntity[ElectroSLocalCoordinator], SwitchEntity):
    _entity_id_key = "charging"
    _attr_has_entity_name = True
    _attr_name = "Зарядка"
    _attr_icon = "mdi:ev-station"
    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator)
        self._host = host
        self.entity_id = suggested_entity_id("switch", self._entity_id_key)
        self._attr_unique_id = f"local_{host}_charging_switch"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": f"ElectroS Local ({host})",
            "manufacturer": "ElectroS",
            "model": "EV Charger (Local)",
        }

    @property
    def is_on(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("status_text") in _CHARGING_STATUSES

    # A failed command raises, so a script or automation stops (or can use continue_on_error)
    # instead of silently assuming the charger got it.
    async def async_turn_on(self, **kwargs) -> None:
        if not await self.coordinator.async_start_charging(self.coordinator.target_amps):
            raise HomeAssistantError(f"Зарядка {self._host} не прийняла команду «почати»")

    async def async_turn_off(self, **kwargs) -> None:
        if not await self.coordinator.async_stop_charging():
            raise HomeAssistantError(f"Зарядка {self._host} не прийняла команду «зупинити»")
