import asyncio
from logging.handlers import TimedRotatingFileHandler

from signalblast.broadcastbot import BroadcasBot


async def rotate_logs_periodically(bot: BroadcasBot) -> None:
    # Ensure the logs are rotated periodically even if no new log entries are made
    if len(bot.logger.handlers) == 0:
        return

    handler = bot.logger.handlers[0]

    if not isinstance(handler, TimedRotatingFileHandler):
        return

    while True:
        if handler.shouldRollover(None):
            handler.doRollover()

        await asyncio.sleep(60 * 60 * 12)  # Check every 12 hours
