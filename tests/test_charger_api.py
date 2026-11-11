"""Tests for parsing the charger state frame (no Home Assistant instance needed)."""

from datetime import datetime, time

from custom_components.electros_ev_local.charger_api import (
    parse_charger_state,
    parse_clock,
    parse_events,
    parse_timer,
)

# A real frame from an ElectroS WiFi (firmware 1.1.4) while charging at 6 A, 10.11.2026.
# Wi-Fi / server / device passwords (fields 1-3 and 29) are replaced.
FRAME_FIELDS = [
    "Halupa",
    "secret1",
    "secret2",
    "secret3",
    "electros.org.ua",
    "8000",
    "0",
    "6",
    "2",
    "63",
    "216",
    "11533918",
    "13608",
    "218",
    "2",
    "10.11.2026T13:51:17",
    "230",
    "203",
    "231",
    "206",
    "217",
    "220",
    "0.01165",
    "0.00155",
    "180",
    "0",
    "00:00",
    "00:00",
    "b9747",
    "secret4",
    "10:33:13 25 10:33:13 23 10:35:35 1 10:35:36 2 13:33:21 22 13:33:21 2 ",
    "11 0 0 0 0 0 0 0 0 0 57338 79155 0",
    "08.11 12:48:42 5916731 07.11 08:41:14 1705",
    "",
]


def frame(**overrides: str) -> str:
    fields = list(FRAME_FIELDS)
    for index, value in overrides.items():
        fields[int(index.lstrip("f"))] = value
    return "\n".join(fields)


def test_existing_fields_unchanged():
    state = parse_charger_state(frame())
    assert state["status_code"] == "2"
    assert state["status_text"] == "charging"
    assert state["current_amps"] == 6
    assert state["mains_voltage"] == 216
    assert state["charging_power_w"] == 1361
    assert state["online"] is True


def test_clock():
    assert parse_charger_state(frame())["clock"] == datetime(2026, 11, 10, 13, 51, 17)
    assert parse_clock("7.11.2026T08:07:20") == datetime(2026, 11, 7, 8, 7, 20)
    assert parse_clock("") is None
    assert parse_clock("garbage") is None


def test_timer_off():
    assert parse_charger_state(frame())["timer"] is None
    assert parse_timer("", "") is None
    assert parse_timer("23:00", "23:00") is None


def test_timer_on():
    state = parse_charger_state(frame(f26="23:00", f27="07:00"))
    assert state["timer"] == (time(23, 0), time(7, 0))


def test_events():
    events = parse_charger_state(frame())["events"]
    assert events[0] == ("10:33:13", "25")
    assert events[-1] == ("13:33:21", "2")
    assert len(events) == 6


def test_events_tolerate_garbage():
    assert parse_events("") == []
    assert parse_events("10:00:00") == []
    assert parse_events("10:00:00 21 broken x 11:00:00 20") == [("10:00:00", "21"), ("11:00:00", "20")]


def test_short_frame_does_not_crash():
    state = parse_charger_state("\n".join(FRAME_FIELDS[:10]))
    assert state["clock"] is None
    assert state["timer"] is None
    assert state["events"] == []
