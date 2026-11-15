"""The WebSocket exchange against a fake charger on localhost: one connection at a time, always closed."""

import asyncio

import pytest

from custom_components.electros_ev_local import charger_api
from custom_components.electros_ev_local.charger_api import ElectroSLocalApi


class FakeCharger:
    """Accepts the upgrade, then answers with one text frame (or stays silent), and records what it saw."""

    def __init__(self, answer=True, delay=0.05):
        self.answer, self.delay = answer, delay
        self.open_now = self.max_open = self.connections = 0
        self.close_frames = 0
        self.closed_by_client = 0

    async def handle(self, reader, writer):
        self.connections += 1
        self.open_now += 1
        self.max_open = max(self.max_open, self.open_now)
        try:
            await reader.readuntil(b"\r\n\r\n")
            writer.write(b"HTTP/1.1 101 Switching Protocols\r\n\r\n")
            await writer.drain()
            if self.answer:
                await asyncio.sleep(self.delay)
                payload = b"frame"
                writer.write(bytes([0x81, len(payload)]) + payload)
                await writer.drain()
            while True:
                head = await reader.readexactly(2)
                length = head[1] & 0x7F
                await reader.readexactly(4 + length)  # mask + payload
                if head[0] & 0x0F == 8:
                    self.close_frames += 1
        except (asyncio.IncompleteReadError, ConnectionError):
            self.closed_by_client += 1
        finally:
            self.open_now -= 1
            writer.close()


async def run(fake, coro_factory, n=1):
    server = await asyncio.start_server(fake.handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    api = ElectroSLocalApi("127.0.0.1", port)
    try:
        return await asyncio.gather(*(coro_factory(api) for _ in range(n)), return_exceptions=True)
    finally:
        await asyncio.sleep(0.1)
        server.close()
        await server.wait_closed()


def test_exchange_sends_close_frame_and_closes():
    fake = FakeCharger()
    results = asyncio.run(run(fake, lambda api: api._ws_communicate("stop")))
    assert results == ["frame"]
    assert fake.close_frames == 1 and fake.closed_by_client == 1 and fake.open_now == 0


def test_one_connection_at_a_time():
    fake = FakeCharger()
    results = asyncio.run(run(fake, lambda api: api._ws_communicate(None), n=4))
    assert results == ["frame"] * 4
    assert fake.connections == 4 and fake.max_open == 1


def test_timeout_still_closes_the_socket(monkeypatch):
    monkeypatch.setattr(charger_api, "READ_TIMEOUT", 0.2)
    fake = FakeCharger(answer=False)
    (result,) = asyncio.run(run(fake, lambda api: api._ws_communicate(None)))
    assert isinstance(result, (asyncio.TimeoutError, TimeoutError))
    assert fake.closed_by_client == 1 and fake.open_now == 0


def test_timeout_is_named_in_the_log(monkeypatch, caplog):
    monkeypatch.setattr(charger_api, "READ_TIMEOUT", 0.2)
    fake = FakeCharger(answer=False)
    (state,) = asyncio.run(run(fake, lambda api: api.get_state()))
    assert state["status_text"].startswith("error: TimeoutError")
    assert "Failed to get local charger state: TimeoutError" in caplog.text


@pytest.mark.parametrize("options, data, expected", [({}, {"scan_interval": 5}, 5), ({"scan_interval": 15}, {"scan_interval": 5}, 15), ({}, {}, 5)])
def test_scan_interval_option_wins(options, data, expected):
    from custom_components.electros_ev_local.const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL

    assert options.get(CONF_SCAN_INTERVAL, data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)) == expected
