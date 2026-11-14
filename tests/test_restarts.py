"""Charger restarts from its event log, and the last command HA sent (nothing is sent to a real charger)."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from custom_components.electros_ev_local.charger_api import boot_log_start, boot_time, parse_events
from custom_components.electros_ev_local.coordinator import ElectroSLocalCoordinator
from custom_components.electros_ev_local.sensor import ElectroSLocalLastCommandSensor, ElectroSLocalLastRestartSensor

HOST = "192.168.1.124"
NOW = datetime(2026, 11, 14, 13, 31, 20, tzinfo=timezone.utc)
# A log right after a start-up (14.11 15:30 local): router mode, connecting to router, 10, then charging.
BOOT_LOG = parse_events("15:30:41 25 15:30:44 23 15:30:50 10 15:31:15 2")


def test_boot_log_start():
    assert boot_log_start(BOOT_LOG) == "15:30:41"
    assert boot_log_start(parse_events("14:53:02 1 14:53:04 2")) is None
    assert boot_log_start([]) is None


def test_boot_time_is_relative_to_the_charger_clock():
    # charger clock 15:31:40 (any offset to HA time), start-up 59 s before it
    assert boot_time(BOOT_LOG, datetime(2026, 11, 14, 15, 31, 40), NOW) == NOW - timedelta(seconds=59)


def test_boot_time_across_midnight():
    log = parse_events("23:59:30 25 23:59:33 23")
    assert boot_time(log, datetime(2026, 11, 15, 0, 0, 30), NOW) == NOW - timedelta(seconds=60)


def test_boot_time_without_a_start_up():
    assert boot_time(parse_events("14:53:02 1"), datetime(2026, 11, 14, 15, 0), NOW) is None


def sensor_with(frames):
    coord = SimpleNamespace(data=None)
    s = ElectroSLocalLastRestartSensor(coord, None, HOST)
    for data in frames:
        coord.data = data
        s._update_from_frame()
    return s


def frame(events, clock):
    return {"events": parse_events(events), "clock": clock, "received_at": NOW}


def test_restart_counted_once_per_log():
    clock = datetime(2026, 11, 14, 15, 31, 40)
    s = sensor_with([
        frame("15:20:00 1 15:21:00 2", clock),                      # an ordinary log: nothing
        frame("15:30:41 25 15:30:44 23", clock),                    # a restart
        frame("15:30:41 25 15:30:44 23 15:31:15 2", clock),         # same log, more entries: same restart
        frame("15:33:02 25 15:33:05 23", clock + timedelta(minutes=3)),  # a second restart
    ])
    assert s.extra_state_attributes == {"count": 2, "charger_log_start": "15:33:02"}


def test_last_command_recorded():
    c = object.__new__(ElectroSLocalCoordinator)
    c.api = SimpleNamespace(stop_charging=AsyncMock(return_value=False))
    c.async_update_listeners = lambda: None
    c.last_command = None
    asyncio.run(c.async_stop_charging())
    text, when, delivered = c.last_command
    assert (text, delivered) == ("зупинити", False)
    s = ElectroSLocalLastCommandSensor(c, None, HOST)
    assert s.native_value == "зупинити"
    assert s.extra_state_attributes["delivered"] is False
