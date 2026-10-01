from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from signalbot import DataMessageContext

    from signalblast.broadcastbot import BroadcastBot

logger = logging.getLogger(__name__)


async def subscribe(bot: BroadcastBot, ctx: DataMessageContext, _args: str) -> None:
    sender = ctx.message.source_uuid
    if sender is None:
        return

    if bot.db.is_banned(sender):
        await bot.reply(ctx, "This number is not allowed to subscribe")
        logger.info("A banned user tried to subscribe")
        return

    if not bot.db.add_subscriber(sender):
        await bot.reply(ctx, "Already subscribed!")
        return

    await bot.set_expiration_time(sender)
    await bot.reply(ctx, bot.settings.welcome_message)
    logger.info("New subscriber")
    logger.debug("%s subscribed", sender)


async def unsubscribe(bot: BroadcastBot, ctx: DataMessageContext, _args: str) -> None:
    sender = ctx.message.source_uuid
    if sender is None:
        return

    if not bot.db.remove_subscriber(sender):
        await bot.reply(ctx, "Not subscribed!")
        return

    await bot.reply(ctx, "Successfully unsubscribed!")
    logger.info("A subscriber unsubscribed")
    logger.debug("%s unsubscribed", sender)
