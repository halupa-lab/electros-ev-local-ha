"""ElectroS EV Charger Local WebSocket API client."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, time, timedelta
import logging
import os
import ssl
import struct

from .const import (
    AMP_TO_INDEX,
    DEFAULT_PORT,
    DEFAULT_WS_PATH,
    STATUS_TEXT_EN,
    SUPPORTED_AMPS,
)

_LOGGER = logging.getLogger(__name__)


def normalize_amps(amps: int) -> int:
    """Normalize amps to nearest supported value."""
    if amps <= 0:
        return 0
    supported = [value for value in SUPPORTED_AMPS if value <= amps]
    if not supported:
        return 0
    return max(supported)


def parse_clock(value: str) -> datetime | None:
    """Charger clock "10.11.2026T13:52:00" -> naive datetime (charger local time), None if invalid."""
    try:
        return datetime.strptime(value.strip(), "%d.%m.%YT%H:%M:%S")
    except ValueError:
        return None


def _parse_hhmm(value: str) -> time | None:
    try:
        return datetime.strptime(value.strip(), "%H:%M").time()
    except ValueError:
        return None


def parse_timer(start: str, stop: str) -> tuple[time, time] | None:
    """Timer window, or None when the timer is off.

    The web page turns the timer off by sending empty times; the charger then reports 00:00 / 00:00.
    A window with start == stop would be empty, so it is treated as off too.
    """
    t_start, t_stop = _parse_hhmm(start), _parse_hhmm(stop)
    if t_start is None or t_stop is None or t_start == t_stop:
        return None
    return t_start, t_stop


def timer_fields_valid(start: str, stop: str) -> bool:
    """True when both timer fields are "HH:MM" (an off timer is "00:00" / "00:00").

    Anything else means the frame layout is not what we expect, and re-sending "the current timer"
    could silently clear a timer we failed to read.
    """
    return _parse_hhmm(start) is not None and _parse_hhmm(stop) is not None


def format_clock(now: datetime) -> str:
    """Local time in the format of the charger's web page: "12.11.2026T07:41:08" (day not zero-padded)."""
    return f"{now.day}.{now:%m.%Y}T{now:%H:%M:%S}"


def build_timer_command(now: datetime, timer: tuple[time, time] | None) -> str:
    """The "datetime" command of the charger's web page ("Задати" on the timer tab).

    It always sets the charger clock to `now` (local time) and either sets the timer window
    or, with timer=None, turns the timer off (empty times, like the page does).
    """
    if timer is None:
        return f"datetime\n{format_clock(now)}\n\n\n"
    start, stop = timer
    return f"datetime\n{format_clock(now)}\n{start:%H:%M}\n{stop:%H:%M}\n"


def parse_events(value: str) -> list[tuple[str, str]]:
    """Event log "HH:MM:SS code HH:MM:SS code ..." -> [(time, code)], oldest first."""
    parts = value.split()
    return [
        (parts[i], parts[i + 1])
        for i in range(0, len(parts) - 1, 2)
        if parts[i].count(":") == 2 and parts[i + 1].isdigit()
    ]


# A charger that starts up writes "Режим роутера" (25) as the first entry of a fresh event log (13.11 19:34,
# 14.11 05:34, 14.11 15:30 and 15:33: then 23 "Підключення до роутера" and 10). The log is cleared at start.
BOOT_EVENT = "25"


def boot_log_start(events: list[tuple[str, str]]) -> str | None:
    """Charger clock time of the first entry of a log that begins with a start-up, else None."""
    if events and events[0][1] == BOOT_EVENT:
        return events[0][0]
    return None


def boot_time(events: list[tuple[str, str]], clock: datetime | None, received_at: datetime) -> datetime | None:
    """When the charger started (HA time), from its fresh event log: the first entry's time is on the charger
    clock, so it is taken relative to the frame's own clock (any clock offset cancels out). Within 24 h."""
    start = boot_log_start(events)
    if start is None or clock is None:
        return None
    try:
        h, m, s = (int(x) for x in start.split(":"))
    except ValueError:
        return None
    ago = (clock - clock.replace(hour=h, minute=m, second=s)).total_seconds()
    if ago < 0:  # the start was before midnight on the charger clock
        ago += 24 * 3600
    return received_at - timedelta(seconds=ago)


def parse_charger_state(message: str) -> dict:
    """Parse charger state from local WebSocket message.

    Uses 'electros.org.ua' as anchor to handle variable header length.

    Relative to anchor line:
      +1: cloud port (8000)
      +2: unknown
      +3: configured amps
      +4: status code (2=charging, 4=blocked, 1=connected_idle, 0=waiting)
      +5: unknown
      +6: mains voltage current (V)
      +7: measured current raw (divide by 10630 to get A)
      +8: charging power raw (divide by 10 to get W)
    """
    parts = message.split("\n")

    # Find anchor line containing 'electros.org.ua'
    anchor = None
    for i, part in enumerate(parts):
        if "electros.org.ua" in part:
            anchor = i
            break

    if anchor is None:
        _LOGGER.warning("Could not find anchor in message, using fallback index 4")
        anchor = 4

    def safe_int_rel(offset: int, default=None):
        idx = anchor + offset
        try:
            val = parts[idx].strip() if len(parts) > idx else ""
            return int(val) if val.isdigit() else default
        except (ValueError, IndexError):
            return default

    def safe_str_rel(offset: int, default=""):
        idx = anchor + offset
        try:
            return parts[idx].strip() if len(parts) > idx else default
        except IndexError:
            return default

    # anchor+3: configured amps
    current_amps = safe_int_rel(3)

    # anchor+4: status code
    raw_status = safe_str_rel(4)
    status_code = str(int(raw_status)) if raw_status.isdigit() else None

    # anchor+6: mains voltage current (V)
    mains_voltage = safe_int_rel(6)

    # anchor+7: NOT measured current — appears to be an energy counter
    # anchor+8: charging power raw / 10 = W
    # e.g. 21070 / 10 = 2107W ≈ 2.1 kW
    charging_power_w = None
    try:
        pw_raw = safe_int_rel(8)
        if pw_raw is not None and pw_raw > 0:
            charging_power_w = round(pw_raw / 10, 0)
    except (ValueError, IndexError):
        pass

    # Measured current: calculated from power and voltage
    # e.g. 2107W / 217V ≈ 9.7A
    measured_current = None
    if charging_power_w is not None and mains_voltage is not None and mains_voltage > 0:
        measured_current = round(charging_power_w / mains_voltage, 1)

    # Fields read by the charger's own web page (http://<ip>/), not used by HA before:
    # anchor+11 charger clock "D.MM.YYYYTHH:MM:SS" (local time, set by the "datetime" command),
    # anchor+22 / +23 timer start / stop "HH:MM", anchor+26 event log "HH:MM:SS code HH:MM:SS code ...".
    return {
        "clock": parse_clock(safe_str_rel(11)),
        "timer": parse_timer(safe_str_rel(22), safe_str_rel(23)),
        "timer_valid": timer_fields_valid(safe_str_rel(22), safe_str_rel(23)),
        "events": parse_events(safe_str_rel(26)),
        "online": status_code != "7",
        "status_code": status_code,
        "status_text": STATUS_TEXT_EN.get(status_code, "unknown"),
        "current_amps": current_amps,
        "measured_current": measured_current,
        "mains_voltage": mains_voltage,
        "charging_power_w": charging_power_w,
    }


# Seconds to wait for the charger at each step of an exchange.
READ_TIMEOUT = 10


def _describe(exc: BaseException) -> str:
    """A timeout has an empty message ("Failed to get local charger state: "): name the type too."""
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__


class ElectroSLocalApi:
    """Local API client for ElectroS EV Charger via direct WebSocket."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        ws_path: str = DEFAULT_WS_PATH,
    ) -> None:
        """Initialize the local API client."""
        self._host = host
        self._port = port
        self._ws_path = ws_path
        # The charger's small web server: one connection at a time (polls and commands wait for each other).
        self._lock = asyncio.Lock()

    async def _ws_communicate(self, message: str | None = None) -> str | None:
        """One exchange: open a WebSocket, optionally send a message, read one frame, close it properly.

        One at a time, and the socket is always closed (also on a timeout or error), with a WebSocket close
        frame first, so no half-open connections are left in the charger.
        """
        async with self._lock:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port),
                timeout=READ_TIMEOUT,
            )
            try:
                return await self._exchange(reader, writer, message)
            finally:
                await self._close(writer)

    async def _close(self, writer) -> None:
        try:
            # Close frame (opcode 8), masked like every client frame, status 1000 "normal closure".
            mask = os.urandom(4)
            payload = struct.pack("!H", 1000)
            writer.write(bytes([0x88, 0x80 | len(payload)]) + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))
            await asyncio.wait_for(writer.drain(), timeout=2)
        except Exception:  # noqa: BLE001 - the socket is closed below anyway
            pass
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), timeout=2)
        except Exception:  # noqa: BLE001
            pass

    async def _exchange(self, reader, writer, message: str | None) -> str | None:
        key = base64.b64encode(os.urandom(16)).decode()

        request = (
            f"GET {self._ws_path} HTTP/1.1\r\n"
            f"Host: {self._host}:{self._port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        )
        writer.write(request.encode("utf-8"))
        await writer.drain()

        # Read HTTP upgrade response
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=READ_TIMEOUT)
            if not chunk:
                break
            response += chunk

        if b"101 Switching Protocols" not in response:
            raise RuntimeError(f"WebSocket upgrade failed: {response[:200]}")

        # Send command if provided
        if message is not None:
            await self._send_ws_frame(writer, message)

        # Receive one frame (the status update)
        return await self._recv_ws_frame(reader)

    async def _send_ws_frame(self, writer, text: str) -> None:
        """Send a masked WebSocket text frame."""
        payload = text.encode("utf-8")
        header = bytearray([0x81])
        length = len(payload)
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        mask = os.urandom(4)
        header.extend(mask)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        writer.write(header + masked)
        await writer.drain()

    async def _recv_ws_frame(self, reader) -> str | None:
        """Receive a WebSocket frame."""
        first = await asyncio.wait_for(reader.readexactly(2), timeout=READ_TIMEOUT)
        byte1, byte2 = first
        opcode = byte1 & 0x0F
        frame_length = byte2 & 0x7F
        is_masked = (byte2 & 0x80) != 0
        if frame_length == 126:
            frame_length = struct.unpack("!H", await reader.readexactly(2))[0]
        elif frame_length == 127:
            frame_length = struct.unpack("!Q", await reader.readexactly(8))[0]
        frame_mask = await reader.readexactly(4) if is_masked else b""
        recv_payload = b""
        while len(recv_payload) < frame_length:
            chunk = await asyncio.wait_for(
                reader.read(frame_length - len(recv_payload)), timeout=READ_TIMEOUT
            )
            if not chunk:
                break
            recv_payload += chunk
        if is_masked:
            recv_payload = bytes(
                byte ^ frame_mask[i % 4] for i, byte in enumerate(recv_payload)
            )
        if opcode != 1:
            return None
        return recv_payload.decode("utf-8", errors="replace")

    async def get_state(self) -> dict:
        """Get charger state by connecting and reading the status frame."""
        try:
            response = await self._ws_communicate(message=None)
            if response is None:
                return self._offline_state("invalid_response")
            return parse_charger_state(response)
        except Exception as exc:
            _LOGGER.error("Failed to get local charger state: %s", _describe(exc))
            return self._offline_state(f"error: {_describe(exc)}")

    async def start_charging(self, amps: int) -> bool:
        """Start charging at specified amperage."""
        amps = normalize_amps(amps)
        if amps <= 0:
            return await self.stop_charging()
        try:
            index = AMP_TO_INDEX[amps]
            # Local protocol: "start\n{index}\n0" (no "site {login}" prefix)
            await self._ws_communicate(message=f"start\n{index}\n0")
            _LOGGER.info("Local: sent start command with %dA (index %d)", amps, index)
            return True
        except Exception as exc:
            _LOGGER.error("Failed to start local charging: %s", _describe(exc))
            return False

    async def stop_charging(self) -> bool:
        """Stop charging."""
        try:
            # Local protocol: just "stop"
            await self._ws_communicate(message="stop")
            _LOGGER.info("Local: sent stop command")
            return True
        except Exception as exc:
            _LOGGER.error("Failed to stop local charging: %s", _describe(exc))
            return False

    async def set_timer(self, now: datetime, timer: tuple[time, time] | None) -> bool:
        """Set the charger clock to `now` and set (or, with None, clear) the timer."""
        try:
            await self._ws_communicate(message=build_timer_command(now, timer))
            _LOGGER.info(
                "Local: sent timer %s with clock %s",
                f"{timer[0]:%H:%M}-{timer[1]:%H:%M}" if timer else "off",
                format_clock(now),
            )
            return True
        except Exception as exc:
            _LOGGER.error("Failed to set local charger timer: %s", _describe(exc))
            return False

    async def test_connection(self) -> bool:
        """Test connection to local charger."""
        try:
            state = await self.get_state()
            return state.get("online", False) or state.get("status_code") is not None
        except Exception:
            return False

    @staticmethod
    def _offline_state(reason: str) -> dict:
        """Return offline state dict."""
        return {
            "online": False,
            "status_code": None,
            "status_text": reason,
            "current_amps": None,
            "measured_current": None,
            "mains_voltage": None,
            "charging_power_w": None,
            "clock": None,
            "timer": None,
            "timer_valid": False,
            "events": [],
        }
