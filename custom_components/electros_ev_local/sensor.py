"""Sensor platform for ElectroS EV Charger Local integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, DOMAIN, STATUS_TEXT
from .coordinator import ElectroSLocalCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: ElectroSLocalCoordinator = entry.runtime_data
    host = entry.data[CONF_HOST]

    async_add_entities([
        ElectroSLocalStatusSensor(coordinator, entry, host),
        ElectroSLocalCurrentAmpsSensor(coordinator, entry, host),
        ElectroSLocalMeasuredCurrentSensor(coordinator, entry, host),
        ElectroSLocalVoltageSensor(coordinator, entry, host),
        ElectroSLocalPowerSensor(coordinator, entry, host),
    ])


class ElectroSLocalBaseSensor(CoordinatorEntity[ElectroSLocalCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator)
        self._host = host
        self._attr_device_info = {
            "identifiers": {(DOMAIN, host)},
            "name": f"ElectroS Local ({host})",
            "manufacturer": "ElectroS",
            "model": "EV Charger (Local)",
        }


class ElectroSLocalStatusSensor(ElectroSLocalBaseSensor):
    _attr_name = "Статус"
    _attr_icon = "mdi:ev-station"

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator, entry, host)
        self._attr_unique_id = f"local_{host}_status"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        code = self.coordinator.data.get("status_code")
        return STATUS_TEXT.get(code, self.coordinator.data.get("status_text", "unknown"))

    @property
    def extra_state_attributes(self):
        if self.coordinator.data is None:
            return {}
        return {
            "online": self.coordinator.data.get("online"),
            "status_code": self.coordinator.data.get("status_code"),
            "status_text_en": self.coordinator.data.get("status_text"),
        }


class ElectroSLocalCurrentAmpsSensor(ElectroSLocalBaseSensor):
    _attr_name = "Налаштований струм"
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:current-ac"

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator, entry, host)
        self._attr_unique_id = f"local_{host}_current_amps"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("current_amps")


class ElectroSLocalMeasuredCurrentSensor(ElectroSLocalBaseSensor):
    _attr_name = "Виміряний струм"
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator, entry, host)
        self._attr_unique_id = f"local_{host}_measured_current"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("measured_current")


class ElectroSLocalVoltageSensor(ElectroSLocalBaseSensor):
    _attr_name = "Напруга мережі"
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator, entry, host)
        self._attr_unique_id = f"local_{host}_mains_voltage"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("mains_voltage")


class ElectroSLocalPowerSensor(ElectroSLocalBaseSensor):
    _attr_name = "Потужність зарядки"
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:lightning-bolt"

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator, entry, host)
        self._attr_unique_id = f"local_{host}_charging_power"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("charging_power_w")
