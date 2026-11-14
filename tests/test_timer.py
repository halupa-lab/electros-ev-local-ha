"""Timer and clock commands, checked against a fake charger (nothing is sent to a real one)."""

import asyncio
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import dt as dt_util

from custom_components.electros_ev_local import coordinator as coordinator_module
from custom_components.electros_ev_local.charger_api import (
    build_timer_command,
    format_clock,
    parse_charger_state,
)
from custom_components.electros_ev_local.coordinator import ElectroSLocalCoordinator
from custom_components.electros_ev_local.services import SET_TIMER_SCHEMA

from .test_charger_api import frame

KYIV = ZoneInfo("Europe/Kyiv")
NOW = datetime(2026, 11, 12, 7, 41, 8, tzinfo=KYIV)
NIGHT = (time(23, 0), time(7, 0))


def test_format_clock_like_the_web_page():
    assert format_clock(datetime(2026, 11, 7, 8, 7, 20)) == "7.11.2026T08:07:20"
    assert format_clock(datetime(2026, 12, 25, 23, 0, 5)) == "25.12.2026T23:00:05"


def test_timer_command():
    now = datetime(2026, 11, 12, 7, 41, 8)
    assert build_timer_command(now, NIGHT) == "datetime\n12.11.2026T07:41:08\n23:00\n07:00\n"
    assert build_timer_command(now, None) == "datetime\n12.11.2026T07:41:08\n\n\n"


def test_timer_valid_flag():
    assert parse_charger_state(frame())["timer_valid"] is True  # 00:00 / 00:00 = off, but readable
    assert parse_charger_state(frame(f26="23:00", f27="07:00"))["timer_valid"] is True
    assert parse_charger_state(frame(f26="b9747", f27="x"))["timer_valid"] is False


class FakeCharger:
    """Stores what the last command set; `refresh` returns it as a state frame would."""

    def __init__(self, timer=None, clock_offset=timedelta(seconds=230), accepts=True, applies=True):
        self.timer, self.clock_offset, self.accepts, self.applies = timer, clock_offset, accepts, applies
        self.set_timer = AsyncMock(side_effect=self._set_timer)
        self.start_charging = AsyncMock(side_effect=self._start)
        self._host = "192.168.1.124"
        self.status = "charging"

    async def _start(self, amps):
        # "start" is a one-off override: the timer reads as off while it lasts.
        self.timer = None
        return True

    async def _set_timer(self, now, timer):
        if self.accepts and self.applies:
            self.timer, self.clock_offset = timer, timedelta(seconds=1)
        return self.accepts


@pytest.fixture
def coord(monkeypatch):
    dt_util.set_default_time_zone(KYIV)
    monkeypatch.setattr(dt_util, "now", lambda time_zone=None: NOW)
    monkeypatch.setattr(coordinator_module, "COMMAND_SETTLE_DELAY", 0)

    def make(charger, timer_valid=True):
        c = object.__new__(ElectroSLocalCoordinator)
        c.api = charger
        c.last_update_success = True

        def read():
            c.data = {
                "status_text": charger.status,
                "timer": charger.timer,
                "timer_valid": timer_valid,
                "clock": (NOW + charger.clock_offset).replace(tzinfo=None),
                "received_at": NOW.astimezone(ZoneInfo("UTC")),
            }

        async def async_refresh():
            read()

        c.async_refresh = async_refresh
        c.async_request_refresh = async_refresh
        c.async_update_listeners = lambda: None
        c._user_set_amps = False
        read()
        return c

    yield make
    dt_util.set_default_time_zone(ZoneInfo("UTC"))


def test_set_timer_sends_local_time_and_verifies(coord):
    charger = FakeCharger()
    asyncio.run(coord(charger).async_set_timer(NIGHT))
    charger.set_timer.assert_awaited_once_with(datetime(2026, 11, 12, 7, 41, 8), NIGHT)
    assert charger.timer == NIGHT


def test_clear_timer(coord):
    charger = FakeCharger(timer=NIGHT)
    asyncio.run(coord(charger).async_set_timer(None))
    assert charger.timer is None


def test_command_not_delivered_raises(coord):
    with pytest.raises(HomeAssistantError, match="не прийняла"):
        asyncio.run(coord(FakeCharger(accepts=False)).async_set_timer(NIGHT))


def test_timer_not_applied_raises(coord):
    with pytest.raises(HomeAssistantError, match="просили 23:00–07:00, у зарядці вимкнено"):
        asyncio.run(coord(FakeCharger(applies=False, clock_offset=timedelta(0))).async_set_timer(NIGHT))


def test_clock_not_set_raises(coord):
    with pytest.raises(HomeAssistantError, match=r"\+230 с"):
        asyncio.run(coord(FakeCharger(timer=NIGHT, applies=False)).async_set_timer(NIGHT))


def test_sync_clock_keeps_timer(coord):
    charger = FakeCharger(timer=NIGHT)
    asyncio.run(coord(charger).async_sync_clock())
    charger.set_timer.assert_awaited_once_with(datetime(2026, 11, 12, 7, 41, 8), NIGHT)


def test_sync_clock_refuses_unreadable_timer(coord):
    charger = FakeCharger(timer=None)
    with pytest.raises(HomeAssistantError, match="не вдалося прочитати"):
        asyncio.run(coord(charger, timer_valid=False).async_sync_clock())
    charger.set_timer.assert_not_awaited()


def test_set_timer_schema():
    data = SET_TIMER_SCHEMA({"start": "23:00", "end": "07:00"})
    assert (data["start"], data["end"]) == NIGHT
    with pytest.raises(vol.Invalid):
        SET_TIMER_SCHEMA({"start": "23:00", "end": "23:00"})
    with pytest.raises(vol.Invalid):
        SET_TIMER_SCHEMA({"start": "23:00"})


def test_current_change_keeps_the_timer(coord):
    # charging by the night timer: the new current goes with "start", then the timer is sent again
    charger = FakeCharger(timer=NIGHT)
    assert asyncio.run(coord(charger).async_set_amps(10)) is True
    charger.start_charging.assert_awaited_once_with(10)
    charger.set_timer.assert_awaited_once_with(datetime(2026, 11, 12, 7, 41, 8), NIGHT)
    assert charger.timer == NIGHT


def test_current_change_in_a_one_off_charge_sends_no_timer(coord):
    # a one-off charge (timer reads as off): only the new current, the override stays
    charger = FakeCharger(timer=None)
    asyncio.run(coord(charger).async_set_amps(10))
    charger.start_charging.assert_awaited_once_with(10)
    charger.set_timer.assert_not_awaited()


def test_current_change_while_not_charging_sends_nothing(coord):
    charger = FakeCharger(timer=NIGHT)
    charger.status = "waiting"
    c = coord(charger)
    asyncio.run(c.async_set_amps(10))
    assert c.target_amps == 10
    charger.start_charging.assert_not_awaited()
    charger.set_timer.assert_not_awaited()


def test_current_change_unreadable_timer_sends_no_timer(coord):
    charger = FakeCharger(timer=NIGHT)
    asyncio.run(coord(charger, timer_valid=False).async_set_amps(10))
    charger.set_timer.assert_not_awaited()
