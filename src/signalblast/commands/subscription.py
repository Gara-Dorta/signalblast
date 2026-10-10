from __future__ import annotations

import logging
from typing import TYPE_CHECKING, override

from signalblast.commands.base import Command
from signalblast.utils import log_event

if TYPE_CHECKING:
    from signalbot import DataMessageContext

logger = logging.getLogger(__name__)

WELCOME = (
    "Welcome! Any message that you send will be forwarded to everybody in the list. "
    "In addition, you can also use these commands:"
)


class Subscribe(Command):
    trigger = "!subscribe"
    description = "Sign up to receive the broadcasts"

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        if self.bot.db.is_banned(sender):
            await self.bot.reply(ctx, "This number is not allowed to subscribe")
            log_event(logger, "A banned user tried to subscribe", user=sender)
            return

        if not self.bot.db.add_subscriber(sender):
            await self.bot.reply(ctx, "Already subscribed!")
            return

        # Imported here because the registry imports this module
        from signalblast.commands.registry import send_help  # noqa: PLC0415

        await send_help(self.bot, sender, intro=WELCOME)
        await self.bot.set_expiration_time(sender)
        log_event(logger, "New subscriber", user=sender)


class Unsubscribe(Command):
    trigger = "!unsubscribe"
    description = "Stop receiving the broadcasts"

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        if not self.bot.db.remove_subscriber(sender):
            await self.bot.reply(ctx, "Not subscribed!")
            return

        await self.bot.reply(ctx, "Successfully unsubscribed!")
        log_event(logger, "A subscriber unsubscribed", user=sender)
