from __future__ import annotations

import logging
from typing import TYPE_CHECKING, override

from signalblast.commands.base import Command
from signalblast.commands.messaging import resolve_quote

if TYPE_CHECKING:
    from signalbot import DataMessageContext

logger = logging.getLogger(__name__)


class Ban(Command):
    trigger = "!ban"
    description = "Reply !ban to a broadcast or a message from a user to ban its sender"
    for_admins = True
    admin_only = True

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        target = resolve_quote(self.bot, ctx)
        if target is None:
            await self.bot.reply(
                ctx,
                "To ban someone, reply !ban to their broadcast (from the last 24 hours) or their message to the "
                "admins (from the last 7 days)",
            )
            return

        if self.bot.db.is_admin(target.uuid):
            await self.bot.reply(ctx, "Admins can't be banned, remove them as admin first")
            return

        ban_id, is_new = self.bot.db.ban(target.uuid, target.snippet)
        if not is_new:
            await self.bot.reply(ctx, f"Already banned (ban #{ban_id})")
            return

        notified = await self.bot.send(target.uuid, "You have been banned") is not None
        about = f'the sender of "{target.snippet}"' if target.snippet else "the sender of that message"
        reply = f"Banned {about} (ban #{ban_id}), undo it with !lift ban {ban_id}"
        await self.bot.reply(ctx, reply if notified else reply + ". They could not be notified")
        await self.bot.notify_admins(f"An admin banned {about} (ban #{ban_id})", exclude=(sender,))
        logger.info("Ban #%s", ban_id)
        logger.debug("Ban #%s is %s", ban_id, target.uuid)


class ListBans(Command):
    trigger = "!list bans"
    description = "Show the banned users"
    for_admins = True
    admin_only = True

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        bans = self.bot.db.bans()
        if not bans:
            await self.bot.reply(ctx, "Nobody is banned")
            return

        lines = [f"#{b.id} · {b.banned_at[:10]}" + (f' · "{b.snippet}"' if b.snippet else "") for b in bans]
        await self.bot.reply(ctx, "Banned users:\n" + "\n".join(lines))


class LiftBan(Command):
    trigger = "!lift ban"
    args = "<number>"
    description = "Lift a ban, see the ban numbers with !list bans"
    for_admins = True
    admin_only = True

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        try:
            ban_id = int(args.removeprefix("#"))
        except ValueError:
            await self.bot.reply(ctx, "Usage: !lift ban <number>, see the ban numbers with !list bans")
            return

        uuid = self.bot.db.lift_ban(ban_id)
        if uuid is None:
            await self.bot.reply(ctx, f"There is no ban #{ban_id}, see the ban numbers with !list bans")
            return

        notified = (
            await self.bot.send(uuid, "Your ban has been lifted, you can subscribe again with !subscribe") is not None
        )
        reply = f"Lifted ban #{ban_id}"
        await self.bot.reply(ctx, reply if notified else reply + ". They could not be notified")
        await self.bot.notify_admins(f"An admin lifted ban #{ban_id}", exclude=(sender,))
        logger.info("Lifted ban #%s", ban_id)
