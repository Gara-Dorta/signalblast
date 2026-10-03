from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from signalbot import ReadyHandler, SendMessage

if TYPE_CHECKING:
    from signalbot import ReadyContext, SignalBot

logger = logging.getLogger(__name__)


class HealthCheck(ReadyHandler):
    """Serves an HTTP endpoint on localhost that sends a "Ping" message to `receiver` on every
    request. It answers 200 if the message was sent and 500 otherwise, docker's HEALTHCHECK uses it."""

    def __init__(self, receiver: str, port: int) -> None:
        self.receiver = receiver
        self.port = port
        self._task: asyncio.Task | None = None

    async def handle_ready(self, context: ReadyContext) -> None:
        # signalbot re-runs its start up if it fails, only start the server once
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._serve(context.bot))
        self._task.add_done_callback(self._log_failure)

    @staticmethod
    def _log_failure(task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.error("The health check server stopped", exc_info=task.exception())

    async def _serve(self, bot: SignalBot) -> None:
        async def handle_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            # Consume the request, closing the socket with unread data resets the connection instead of
            # delivering the response
            with contextlib.suppress(asyncio.IncompleteReadError, asyncio.LimitOverrunError, TimeoutError):
                await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
            try:
                await asyncio.wait_for(bot.messages.send(SendMessage(text="Ping"), self.receiver), timeout=30)
                response = "HTTP/1.0 200 OK\r\n\r\nOK\r\n"
                logger.info("Health check message sent")
            except Exception:
                logger.exception("Health check failed")
                response = "HTTP/1.0 500 Internal Server Error\r\n\r\nInternal Server Error\r\n"

            writer.write(response.encode("utf8"))
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_request, "localhost", self.port)
        logger.info("Health check listening on port %s", self.port)
        async with server:
            await server.serve_forever()
