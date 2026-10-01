from __future__ import annotations

import logging
from typing import TYPE_CHECKING, override

from signalblast.commands.base import Command

if TYPE_CHECKING:
    from signalbot import DataMessageContext

logger = logging.getLogger(__name__)


class Subscribe(Command):
    trigger = "!subscribe"
    description = "Sign up to receive the broadcasts"

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        if self.bot.db.is_banned(sender):
            await self.bot.reply(ctx, "This number is not allowed to subscribe")
            logger.info("A banned user tried to subscribe")
            return

        if not self.bot.db.add_subscriber(sender):
            await self.bot.reply(ctx, "Already subscribed!")
            return

        await self.bot.set_expiration_time(sender)
        await self.bot.reply(ctx, self.bot.settings.welcome_message)
        logger.info("New subscriber")
        logger.debug("%s subscribed", sender)


class Unsubscribe(Command):
    trigger = "!unsubscribe"
    description = "Stop receiving the broadcasts"

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        if not self.bot.db.remove_subscriber(sender):
            await self.bot.reply(ctx, "Not subscribed!")
            return

        await self.bot.reply(ctx, "Successfully unsubscribed!")
        logger.info("A subscriber unsubscribed")
        logger.debug("%s unsubscribed", sender)
