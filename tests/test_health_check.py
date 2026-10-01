from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock

from signalbot import ReadyContext

from signalblast.health_check import HealthCheck

RECEIVER = "+49000"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("localhost", 0))
        return sock.getsockname()[1]


async def request(port: int) -> str:
    for _ in range(50):  # Wait for the server to start listening
        try:
            reader, writer = await asyncio.open_connection("localhost", port)
            break
        except ConnectionRefusedError:
            await asyncio.sleep(0.01)
    writer.write(b"GET / HTTP/1.0\r\n\r\n")
    response = await reader.read()
    writer.close()
    return response.decode()


async def start_health_check(send: AsyncMock) -> tuple[HealthCheck, int]:
    bot = MagicMock()
    bot.messages.send = send
    port = free_port()
    health_check = HealthCheck(RECEIVER, port)
    await health_check.handle_ready(ReadyContext(bot))
    return health_check, port


async def test_ok_when_the_ping_is_sent() -> None:
    send = AsyncMock()
    health_check, port = await start_health_check(send)

    assert (await request(port)).startswith("HTTP/1.0 200 OK")
    assert send.call_args.args[0].text == "Ping"
    assert send.call_args.args[1] == RECEIVER

    assert health_check._task is not None  # noqa: SLF001
    health_check._task.cancel()  # noqa: SLF001


async def test_error_when_the_ping_fails() -> None:
    health_check, port = await start_health_check(AsyncMock(side_effect=RuntimeError("signal is down")))

    assert (await request(port)).startswith("HTTP/1.0 500")

    assert health_check._task is not None  # noqa: SLF001
    health_check._task.cancel()  # noqa: SLF001


async def test_starts_only_once_when_signalbot_reruns_its_start_up() -> None:
    health_check, _ = await start_health_check(AsyncMock())
    first_task = health_check._task  # noqa: SLF001

    await health_check.handle_ready(ReadyContext(MagicMock()))

    assert health_check._task is first_task  # noqa: SLF001
    assert first_task is not None
    first_task.cancel()
