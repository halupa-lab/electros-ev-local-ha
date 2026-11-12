"""A command the charger did not get must raise, so automations do not assume it worked."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.electros_ev_local.number import ElectroSLocalAmpsNumber
from custom_components.electros_ev_local.switch import ElectroSLocalChargingSwitch

HOST = "192.168.1.124"


def coordinator(ok: bool):
    return SimpleNamespace(
        data={"status_text": "charging"},
        target_amps=20,
        async_start_charging=AsyncMock(return_value=ok),
        async_stop_charging=AsyncMock(return_value=ok),
        async_set_amps=AsyncMock(return_value=ok),
    )


@pytest.mark.parametrize("method", ["async_turn_on", "async_turn_off"])
def test_switch_ok(method):
    c = coordinator(True)
    asyncio.run(getattr(ElectroSLocalChargingSwitch(c, None, HOST), method)())


@pytest.mark.parametrize("method", ["async_turn_on", "async_turn_off"])
def test_switch_failed_command_raises(method):
    c = coordinator(False)
    with pytest.raises(HomeAssistantError, match=HOST):
        asyncio.run(getattr(ElectroSLocalChargingSwitch(c, None, HOST), method)())


def test_switch_start_uses_target_amps():
    c = coordinator(True)
    asyncio.run(ElectroSLocalChargingSwitch(c, None, HOST).async_turn_on())
    c.async_start_charging.assert_awaited_once_with(20)


def test_number_ok_and_normalized():
    c = coordinator(True)
    asyncio.run(ElectroSLocalAmpsNumber(c, None, HOST).async_set_native_value(21))
    c.async_set_amps.assert_awaited_once_with(20)


def test_number_failed_command_raises():
    c = coordinator(False)
    with pytest.raises(HomeAssistantError, match="20 A"):
        asyncio.run(ElectroSLocalAmpsNumber(c, None, HOST).async_set_native_value(20))
