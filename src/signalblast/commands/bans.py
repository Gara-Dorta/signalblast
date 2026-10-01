from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from signalblast.commands.messaging import resolve_quote

if TYPE_CHECKING:
    from signalbot import DataMessageContext

    from signalblast.broadcastbot import BroadcastBot

logger = logging.getLogger(__name__)


async def ban(bot: BroadcastBot, ctx: DataMessageContext, _args: str) -> None:
    sender = ctx.message.source_uuid
    target = resolve_quote(bot, ctx)
    if target is None:
        await bot.reply(
            ctx,
            "To ban someone, quote their broadcast (from the last 24 hours) or their message to the admins "
            "(from the last 7 days) and send !ban",
        )
        return

    if bot.db.is_admin(target.uuid):
        await bot.reply(ctx, "Admins can't be banned, remove them as admin first")
        return

    ban_id, is_new = bot.db.ban(target.uuid, target.snippet)
    if not is_new:
        await bot.reply(ctx, f"Already banned (ban #{ban_id})")
        return

    notified = await bot.send(target.uuid, "You have been banned") is not None
    about = f'the sender of "{target.snippet}"' if target.snippet else "the sender of that message"
    reply = f"Banned {about} (ban #{ban_id}), undo it with !lift ban {ban_id}"
    await bot.reply(ctx, reply if notified else reply + ". They could not be notified")
    await bot.notify_admins(f"An admin banned {about} (ban #{ban_id})", exclude=(sender,))
    logger.info("Ban #%s", ban_id)
    logger.debug("Ban #%s is %s", ban_id, target.uuid)


async def list_bans(bot: BroadcastBot, ctx: DataMessageContext, _args: str) -> None:
    bans = bot.db.bans()
    if not bans:
        await bot.reply(ctx, "Nobody is banned")
        return

    lines = [f"#{b.id} · {b.banned_at[:10]}" + (f' · "{b.snippet}"' if b.snippet else "") for b in bans]
    await bot.reply(ctx, "Banned users:\n" + "\n".join(lines))


async def lift_ban(bot: BroadcastBot, ctx: DataMessageContext, args: str) -> None:
    sender = ctx.message.source_uuid
    try:
        ban_id = int(args.removeprefix("#"))
    except ValueError:
        await bot.reply(ctx, "Usage: !lift ban <number>, see the ban numbers with !list bans")
        return

    uuid = bot.db.lift_ban(ban_id)
    if uuid is None:
        await bot.reply(ctx, f"There is no ban #{ban_id}, see the ban numbers with !list bans")
        return

    notified = await bot.send(uuid, "Your ban has been lifted, you can subscribe again with !subscribe") is not None
    reply = f"Lifted ban #{ban_id}"
    await bot.reply(ctx, reply if notified else reply + ". They could not be notified")
    await bot.notify_admins(f"An admin lifted ban #{ban_id}", exclude=(sender,))
    logger.info("Lifted ban #%s", ban_id)
