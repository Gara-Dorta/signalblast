from __future__ import annotations

import asyncio
from logging.handlers import TimedRotatingFileHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from signalblast.broadcastbot import BroadcasBot


async def rotate_logs_periodically(bot: BroadcasBot) -> None:
    # Ensure the logs are rotated periodically even if no new log entries are made
    if len(bot.logger.handlers) == 0:
        return

    handler = bot.logger.handlers[0]

    if not isinstance(handler, TimedRotatingFileHandler):
        return

    while True:
        # `record` is unused by TimedRotatingFileHandler's time-based rollover check;
        # passing None is the standard idiom, typeshed just doesn't mark it optional.
        if handler.shouldRollover(None):  # pyright: ignore[reportArgumentType]
            handler.doRollover()

        await asyncio.sleep(60 * 60 * 12)  # Check every 12 hours
