import asyncio

from signalblast.broadcastbot import BroadcasBot


async def health_check(bot: BroadcasBot, receiver: str, port: int) -> None:
    async def handle_health_check_request(
        _reader: asyncio.streams.StreamReader,
        writer: asyncio.streams.StreamWriter,
    ) -> None:
        bot.logger.info("Handle health check request")

        try:
            # The health check is to send a ping message to receiver
            await asyncio.wait_for(bot.send(receiver, "Ping"), timeout=30)
            response = "HTTP/1.0 200 OK\r\n\r\nOK \r\n"

            bot.logger.info("Health check message sent")
        except Exception:
            bot.logger.exception("")
            response = "HTTP/1.0 500 Internal Server Error\r\n\r\nInternal Server Error \r\n"

        writer.write(response.encode("utf8"))
        await writer.drain()
        writer.close()

        bot.logger.info("Health check performed")

    server = await asyncio.start_server(handle_health_check_request, "localhost", port)
    async with server:
        await server.serve_forever()
