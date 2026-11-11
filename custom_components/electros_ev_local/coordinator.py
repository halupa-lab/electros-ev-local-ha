"""DataUpdateCoordinator for ElectroS EV Charger Local integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .charger_api import ElectroSLocalApi, normalize_amps
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

COMMAND_SETTLE_DELAY = 2
POST_STOP_REFRESHES = 3
POST_STOP_INTERVAL = 3


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
