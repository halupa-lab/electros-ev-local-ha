"""ElectroS EV Charger Local WebSocket API client."""

from __future__ import annotations

import asyncio
import base64
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


def parse_charger_state(message: str) -> dict:
    """Parse charger state from local WebSocket message.

    Local protocol sends a large newline-delimited status message.
    Format (based on reverse engineering):
      line 0:  WiFi SSID
      line 1:  WiFi password
      line 2:  cloud password
      line 3:  cloud host
      line 4:  cloud port
      line 5:  configured amps
      line 6:  status code (00 = idle, etc.)
      line 7:  ?
      line 8:  ?
      line 9:  ?
      line 10: ?
      line 11: mains voltage
      ...rest: history and diagnostics

    NOTE: This mapping will be refined once live charging data is captured.
    """
    parts = message.split("\n")

    def safe_int(idx: int, default=None):
        try:
            return int(parts[idx]) if len(parts) > idx and parts[idx].strip().isdigit() else default
        except (ValueError, IndexError):
            return default

    def safe_str(idx: int, default=""):
        try:
            return parts[idx].strip() if len(parts) > idx else default
        except IndexError:
            return default

    # Configured amps (line 5)
    current_amps = safe_int(5)

    # Status code (line 6) — "00" means idle/waiting
    raw_status = safe_str(6)
    # Normalize: "00" -> "0", "02" -> "2" etc.
    status_code = str(int(raw_status)) if raw_status.isdigit() else None

    # Mains voltage (line 11)
    mains_voltage = safe_int(11)

    # Measured current — not yet identified in local protocol
    # Will be updated once live charging data is available
    measured_current = None

    charging_power_w = None
    if measured_current is not None and mains_voltage is not None:
        charging_power_w = round(measured_current * mains_voltage, 1)

    return {
        "online": status_code != "7",
        "status_code": status_code,
        "status_text": STATUS_TEXT_EN.get(status_code, "unknown"),
        "current_amps": current_amps,
        "measured_current": measured_current,
        "mains_voltage": mains_voltage,
        "charging_power_w": charging_power_w,
        "raw_message": message,  # keep for debugging
    }


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

    async def _ws_communicate(self, message: str | None = None) -> str | None:
        """Open WebSocket, optionally send message, receive response."""
        key = base64.b64encode(os.urandom(16)).decode()

        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(self._host, self._port),
            timeout=10,
        )

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
            chunk = await asyncio.wait_for(reader.read(4096), timeout=10)
            if not chunk:
                break
            response += chunk

        if b"101 Switching Protocols" not in response:
            writer.close()
            raise RuntimeError(f"WebSocket upgrade failed: {response[:200]}")

        # Send command if provided
        if message is not None:
            await self._send_ws_frame(writer, message)

        # Receive one frame (the status update)
        result = await self._recv_ws_frame(reader)
        writer.close()
        return result

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
        first = await asyncio.wait_for(reader.readexactly(2), timeout=10)
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
                reader.read(frame_length - len(recv_payload)), timeout=10
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
            _LOGGER.error("Failed to get local charger state: %s", exc)
            return self._offline_state(f"error: {exc}")

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
            _LOGGER.error("Failed to start local charging: %s", exc)
            return False

    async def stop_charging(self) -> bool:
        """Stop charging."""
        try:
            # Local protocol: just "stop"
            await self._ws_communicate(message="stop")
            _LOGGER.info("Local: sent stop command")
            return True
        except Exception as exc:
            _LOGGER.error("Failed to stop local charging: %s", exc)
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
            "raw_message": "",
        }
