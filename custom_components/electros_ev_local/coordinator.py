"""DataUpdateCoordinator for ElectroS EV Charger Local integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import time, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .charger_api import ElectroSLocalApi, normalize_amps
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

COMMAND_SETTLE_DELAY = 2
POST_STOP_REFRESHES = 3
POST_STOP_INTERVAL = 3

# After a timer command: re-read the charger up to this many times before giving up.
TIMER_VERIFY_READS = 3
# The charger clock counts as set when it is this close to HA time (frame clock has 1 s resolution,
# plus the time between sending the command and reading the frame back).
CLOCK_TOLERANCE_S = 15


class ElectroSLocalCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator for local ElectroS charger."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: ElectroSLocalApi,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.target_amps: int = 6
        self._user_set_amps: bool = False

    async def _async_update_data(self) -> dict:
        try:
            data = await self.api.get_state()
        except Exception as err:
            raise UpdateFailed(f"Error communicating with local charger: {err}") from err

        if data.get("status_text", "").startswith("error"):
            raise UpdateFailed(f"Charger error: {data['status_text']}")

        # When the frame was received: the charger clock in it is compared with HA time.
        data["received_at"] = dt_util.utcnow()

        if not self._user_set_amps:
            charger_amps = data.get("current_amps")
            if charger_amps is not None and charger_amps > 0:
                self.target_amps = charger_amps

        return data

    async def async_start_charging(self, amps: int) -> bool:
        amps = normalize_amps(amps)
        if amps <= 0:
            return False
        success = await self.api.start_charging(amps)
        if success:
            self.target_amps = amps
            self._user_set_amps = True
            await asyncio.sleep(COMMAND_SETTLE_DELAY)
            await self.async_request_refresh()
        return success

    async def async_stop_charging(self) -> bool:
        success = await self.api.stop_charging()
        if success:
            for i in range(POST_STOP_REFRESHES):
                await asyncio.sleep(COMMAND_SETTLE_DELAY if i == 0 else POST_STOP_INTERVAL)
                await self.async_request_refresh()
        return success

    async def async_set_amps(self, amps: int) -> bool:
        amps = normalize_amps(amps)
        if amps <= 0:
            return False
        self.target_amps = amps
        self._user_set_amps = True
        self.async_update_listeners()
        if self.data and self.data.get("status_text") == "charging":
            success = await self.api.start_charging(amps)
            if success:
                await asyncio.sleep(COMMAND_SETTLE_DELAY)
                await self.async_request_refresh()
            return success
        return True

    # ---------- timer and clock ----------
    # One command ("datetime") sets the charger clock and the timer together, like "Задати" on the
    # charger's web page. Every method below checks a fresh state frame afterwards and raises if the
    # charger does not report what was asked, so automations never assume a timer that is not there.

    def clock_offset_s(self) -> float | None:
        """Charger clock minus HA time, in seconds, from the last frame."""
        data = self.data or {}
        clock, received_at = data.get("clock"), data.get("received_at")
        if clock is None or received_at is None:
            return None
        return (clock.replace(tzinfo=dt_util.get_default_time_zone()) - received_at).total_seconds()

    async def async_set_timer(self, timer: tuple[time, time] | None) -> None:
        """Set the timer (None = off) and the charger clock to HA local time, then verify both."""
        host = self.api._host
        now = dt_util.now().replace(tzinfo=None)  # the charger clock has no time zone: local time
        if not await self.api.set_timer(now, timer):
            raise HomeAssistantError(f"Зарядка {host} не прийняла команду таймера")
        for _ in range(TIMER_VERIFY_READS):
            await asyncio.sleep(COMMAND_SETTLE_DELAY)
            await self.async_refresh()
            if not self.last_update_success or not self.data:
                continue
            offset = self.clock_offset_s()
            if self.data.get("timer") == timer and offset is not None and abs(offset) <= CLOCK_TOLERANCE_S:
                return
        wanted = f"{timer[0]:%H:%M}–{timer[1]:%H:%M}" if timer else "вимкнено"
        got = (self.data or {}).get("timer")
        got_text = f"{got[0]:%H:%M}–{got[1]:%H:%M}" if got else "вимкнено"
        offset = self.clock_offset_s()
        raise HomeAssistantError(
            f"Зарядка {host}: таймер не підтверджено (просили {wanted}, у зарядці {got_text}, "
            f"відхилення годинника {'невідоме' if offset is None else f'{offset:+.0f} с'})"
        )

    async def async_sync_clock(self) -> None:
        """Set the charger clock to HA time and keep the timer that is in the charger now."""
        data = self.data or {}
        if not self.last_update_success or not data.get("timer_valid"):
            # Re-sending a timer we could not read would clear it.
            raise HomeAssistantError(
                f"Зарядка {self.api._host}: не вдалося прочитати поточний таймер, годинник не змінено"
            )
        await self.async_set_timer(data.get("timer"))
