"""Every entity suggests a fixed English ID; the packages and the card use exactly these."""

from types import SimpleNamespace

from custom_components.electros_ev_local.number import ElectroSLocalAmpsNumber
from custom_components.electros_ev_local.sensor import (
    ElectroSLocalClockOffsetSensor,
    ElectroSLocalCurrentAmpsSensor,
    ElectroSLocalLastCommandSensor,
    ElectroSLocalLastEventSensor,
    ElectroSLocalLastRestartSensor,
    ElectroSLocalMeasuredCurrentSensor,
    ElectroSLocalPowerSensor,
    ElectroSLocalStatusSensor,
    ElectroSLocalTimerSensor,
    ElectroSLocalVoltageSensor,
)
from custom_components.electros_ev_local.switch import ElectroSLocalChargingSwitch

HOST = "192.168.1.124"

EXPECTED = {
    ElectroSLocalChargingSwitch: "switch.electros_charging",
    ElectroSLocalAmpsNumber: "number.electros_charging_current",
    ElectroSLocalStatusSensor: "sensor.electros_status",
    ElectroSLocalCurrentAmpsSensor: "sensor.electros_set_current",
    ElectroSLocalMeasuredCurrentSensor: "sensor.electros_measured_current",
    ElectroSLocalVoltageSensor: "sensor.electros_voltage",
    ElectroSLocalPowerSensor: "sensor.electros_power",
    ElectroSLocalTimerSensor: "sensor.electros_timer",
    ElectroSLocalClockOffsetSensor: "sensor.electros_clock_offset",
    ElectroSLocalLastEventSensor: "sensor.electros_last_event",
    ElectroSLocalLastRestartSensor: "sensor.electros_last_restart",
    ElectroSLocalLastCommandSensor: "sensor.electros_last_command",
}


def test_entity_ids():
    for cls, expected in EXPECTED.items():
        assert cls(SimpleNamespace(data=None), None, HOST).entity_id == expected, cls.__name__
