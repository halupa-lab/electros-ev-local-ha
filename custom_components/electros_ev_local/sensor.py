"""Sensor platform for ElectroS EV Charger Local integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import CONF_HOST, DOMAIN, EVENT_TEXT, EVENT_TEXT_EN, STATUS_TEXT
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
        ElectroSLocalTimerSensor(coordinator, entry, host),
        ElectroSLocalClockOffsetSensor(coordinator, entry, host),
        ElectroSLocalLastEventSensor(coordinator, entry, host),
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


class ElectroSLocalTimerSensor(ElectroSLocalBaseSensor):
    """Charging timer stored in the charger (read only). Outside the window the charger does not charge."""

    _attr_name = "Таймер зарядки"
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator, entry, host)
        self._attr_unique_id = f"local_{host}_timer"

    @property
    def native_value(self):
        if self.coordinator.data is None:
            return None
        timer = self.coordinator.data.get("timer")
        if timer is None:
            return "вимкнено"
        return f"{timer[0]:%H:%M}–{timer[1]:%H:%M}"

    @property
    def extra_state_attributes(self):
        timer = (self.coordinator.data or {}).get("timer")
        return {
            "enabled": timer is not None,
            "start": f"{timer[0]:%H:%M}" if timer else None,
            "end": f"{timer[1]:%H:%M}" if timer else None,
        }


class ElectroSLocalClockOffsetSensor(ElectroSLocalBaseSensor):
    """How far the charger clock is ahead (+) or behind (-) of HA time. The timer runs on this clock."""

    _attr_name = "Відхилення годинника зарядки"
    _attr_icon = "mdi:clock-alert-outline"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"
    _attr_suggested_display_precision = 0
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator, entry, host)
        self._attr_unique_id = f"local_{host}_clock_offset"

    def _charger_time(self):
        clock = (self.coordinator.data or {}).get("clock")
        # The charger clock has no time zone: it shows local time, like the charger web page.
        return clock.replace(tzinfo=dt_util.get_default_time_zone()) if clock else None

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        charger_time = self._charger_time()
        received_at = data.get("received_at")
        if charger_time is None or received_at is None:
            return None
        # Rounded to 10 s: the frame and the poll time differ by up to a second or two,
        # and a new value every 5 s would only fill the history.
        return int(round((charger_time - received_at).total_seconds() / 10) * 10)

    @property
    def extra_state_attributes(self):
        charger_time = self._charger_time()
        return {"charger_time": charger_time.isoformat() if charger_time else None}


class ElectroSLocalLastEventSensor(ElectroSLocalBaseSensor):
    """Last entry of the charger's own event log (timer allow / forbid, programming, errors, ...)."""

    _attr_name = "Остання подія зарядки"
    _attr_icon = "mdi:message-text-clock-outline"

    def __init__(self, coordinator, entry, host) -> None:
        super().__init__(coordinator, entry, host)
        self._attr_unique_id = f"local_{host}_last_event"

    def _events(self):
        return (self.coordinator.data or {}).get("events") or []

    @staticmethod
    def _text(code):
        return EVENT_TEXT.get(code, f"Код {code}")

    @property
    def native_value(self):
        events = self._events()
        return self._text(events[-1][1]) if events else None

    @property
    def extra_state_attributes(self):
        events = self._events()
        if not events:
            return {}
        last_time, last_code = events[-1]
        return {
            "code": last_code,
            "event_en": EVENT_TEXT_EN.get(last_code, "unknown"),
            "time": last_time,  # charger clock, local time
            "recent": [f"{t} {self._text(c)}" for t, c in events[-10:]],
        }
