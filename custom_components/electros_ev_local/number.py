"""Number platform for ElectroS EV Charger Local integration."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .charger_api import normalize_amps
from .const import CONF_HOST, DOMAIN
from .coordinator import ElectroSLocalCoordinator
from .entity_ids import suggested_entity_id

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ElectroSLocalCoordinator = entry.runtime_data
    host = entry.data[CONF_HOST]
    async_add_entities([ElectroSLocalAmpsNumber(coordinator, entry, host)])


class ElectroSLocalAmpsNumber(CoordinatorEntity[ElectroSLocalCoordinator], NumberEntity):
    _entity_id_key = "charging_current"
    _attr_has_entity_name = True
    _attr_name = "Струм зарядки"
    _attr_icon = "mdi:current-ac"
    _attr_native_min_value = 6
    _attr_native_max_value = 32
    _attr_native_step = 2
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator)
        self._host = host
        self.entity_id = suggested_entity_id("number", self._entity_id_key)
        self._attr_unique_id = f"local_{host}_charging_amps"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": f"ElectroS Local ({host})",
            "manufacturer": "ElectroS",
            "model": "EV Charger (Local)",
        }

    @property
    def native_value(self):
        return float(self.coordinator.target_amps)

    async def async_set_native_value(self, value: float) -> None:
        amps = normalize_amps(int(value))
        if amps <= 0:
            return
        # While not charging nothing is sent (the value is used with the next start), so only
        # a command that really went to the charger can fail here.
        if not await self.coordinator.async_set_amps(amps):
            raise HomeAssistantError(f"Зарядка {self._host} не прийняла струм {amps} A")
