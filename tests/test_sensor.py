"""Tests for the read-only timer / clock / event sensors, with a fake coordinator."""

from datetime import datetime, time, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from homeassistant.util import dt as dt_util

from custom_components.electros_ev_local.sensor import (
    ElectroSLocalClockOffsetSensor,
    ElectroSLocalLastEventSensor,
    ElectroSLocalTimerSensor,
)

KYIV = ZoneInfo("Europe/Kyiv")


@pytest.fixture(autouse=True)
def kyiv_time_zone():
    dt_util.set_default_time_zone(KYIV)
    yield
    dt_util.set_default_time_zone(ZoneInfo("UTC"))


def make(cls, data):
    return cls(SimpleNamespace(data=data), None, "192.168.1.124")


def test_unique_ids_are_new_and_stable():
    ids = {make(c, {}).unique_id for c in (ElectroSLocalTimerSensor, ElectroSLocalClockOffsetSensor, ElectroSLocalLastEventSensor)}
    assert ids == {
        "local_192.168.1.124_timer",
        "local_192.168.1.124_clock_offset",
        "local_192.168.1.124_last_event",
    }


def test_timer_sensor():
    off = make(ElectroSLocalTimerSensor, {"timer": None})
    assert off.native_value == "вимкнено"
    assert off.extra_state_attributes == {"enabled": False, "start": None, "end": None}
    on = make(ElectroSLocalTimerSensor, {"timer": (time(23, 0), time(7, 0))})
    assert on.native_value == "23:00–07:00"
    assert on.extra_state_attributes == {"enabled": True, "start": "23:00", "end": "07:00"}
    assert make(ElectroSLocalTimerSensor, None).native_value is None


def test_clock_offset_uses_local_time_and_rounds():
    received = datetime(2026, 11, 10, 13, 48, 12, tzinfo=KYIV).astimezone(ZoneInfo("UTC"))
    charger = datetime(2026, 11, 10, 13, 52, 0)  # naive, charger local time: 228 s ahead
    sensor = make(ElectroSLocalClockOffsetSensor, {"clock": charger, "received_at": received})
    assert sensor.native_value == 230
    behind = make(ElectroSLocalClockOffsetSensor, {"clock": charger - timedelta(minutes=10), "received_at": received})
    assert behind.native_value == -370
    assert make(ElectroSLocalClockOffsetSensor, {"clock": None, "received_at": received}).native_value is None


def test_last_event_sensor():
    events = [("10:33:13", "25"), ("22:59:59", "21"), ("23:00:00", "20"), ("23:00:01", "99")]
    sensor = make(ElectroSLocalLastEventSensor, {"events": events})
    assert sensor.native_value == "Код 99"
    attrs = sensor.extra_state_attributes
    assert attrs["code"] == "99"
    assert attrs["event_en"] == "unknown"
    assert attrs["time"] == "23:00:01"
    assert attrs["recent"][1:3] == ["22:59:59 Таймер. Заборона заряджання", "23:00:00 Таймер. Дозвіл заряджання"]
    assert make(ElectroSLocalLastEventSensor, {"events": []}).native_value is None


def test_last_event_english_name():
    sensor = make(ElectroSLocalLastEventSensor, {"events": [("23:00:00", "21")]})
    assert sensor.native_value == "Таймер. Заборона заряджання"
    assert sensor.extra_state_attributes["event_en"] == "timer_charging_blocked"


def test_every_event_has_english_name():
    from custom_components.electros_ev_local.const import EVENT_TEXT, EVENT_TEXT_EN, STATUS_TEXT_EN

    assert EVENT_TEXT.keys() == EVENT_TEXT_EN.keys()
    for code, name in EVENT_TEXT_EN.items():
        if code in STATUS_TEXT_EN:
            assert name == STATUS_TEXT_EN[code]
