from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, override

from signalbot import __version__ as signalbot_version

from signalblast import __version__ as signalblast_version
from signalblast.commands.base import Command
from signalblast.passwords import check_password

if TYPE_CHECKING:
    from signalbot import DataMessageContext

    from signalblast.broadcastbot import BroadcastBot

logger = logging.getLogger(__name__)


async def _check_password(bot: BroadcastBot, ctx: DataMessageContext, password: str, action: str) -> bool:
    """Replies and warns the admins if the password is wrong. The sender's id is not shared."""
    password_hash = bot.db.password_hash()
    if password_hash is None:
        await bot.reply(ctx, "Admins can't be added or removed because no admin password is set")
        return False

    if not await check_password(password, password_hash):
        await bot.reply(ctx, "Wrong password!")
        await bot.notify_admins(f"Someone tried to {action} with a wrong password")
        logger.warning("Wrong password when trying to %s", action)
        return False

    return True


def _is_uuid(text: str) -> bool:
    try:
        uuid.UUID(text)
    except ValueError:
        return False
    return True


class AddAdmin(Command):
    trigger = "!add admin"
    args = "<password>"
    description = "Become an admin"
    for_admins = True

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        if not args:
            await self.bot.reply(ctx, "Missing the password, usage: !add admin <password>")
            return

        if not await _check_password(self.bot, ctx, args, "become an admin"):
            return

        if not self.bot.db.add_admin(sender):
            await self.bot.reply(ctx, "You are already an admin")
            return

        await self.bot.reply(ctx, "You are now an admin! Send !help to see the admin commands")
        await self.bot.notify_admins(f"{sender} is now an admin", exclude=(sender,))
        logger.info("New admin")
        logger.debug("New admin %s", sender)


class RemoveAdmin(Command):
    trigger = "!remove admin"
    args = "<password> <admin id>"
    description = "Remove an admin, see their ids with !list admins"
    for_admins = True

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        # The admin id is the last word, the password may contain spaces
        password, _, admin_id = args.rpartition(" ")
        if not password.strip() or not _is_uuid(admin_id):
            await self.bot.reply(ctx, "Usage: !remove admin <password> <admin id>, see the admin ids with !list admins")
            return

        if not await _check_password(self.bot, ctx, password, "remove an admin"):
            return

        if not self.bot.db.remove_admin(admin_id):
            await self.bot.reply(ctx, f"{admin_id} is not an admin")
            return

        await self.bot.reply(ctx, f"Removed admin {admin_id}")
        if admin_id != sender:
            await self.bot.send(admin_id, "You are no longer an admin")
        await self.bot.notify_admins(f"{admin_id} is no longer an admin", exclude=(sender,))
        logger.info("Removed an admin")
        logger.debug("Removed admin %s", admin_id)


class ListAdmins(Command):
    trigger = "!list admins"
    description = "Show the ids of the admins"
    for_admins = True
    admin_only = True

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        lines = [f"{admin} (you)" if admin == sender else admin for admin in self.bot.db.admins()]
        await self.bot.reply(ctx, "Admins:\n" + "\n".join(lines))


class ShowVersion(Command):
    trigger = "!version"
    description = "Show the versions of the bot"
    for_admins = True
    admin_only = True

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        signal_cli_rest_api_version = (await ctx.bot.general.about()).version
        await self.bot.reply(
            ctx,
            "Versions:\n"
            f"\tsignalblast: {signalblast_version}\n"
            f"\tsignalbot: {signalbot_version}\n"
            f"\tsignal-cli-rest-api: {signal_cli_rest_api_version}",
        )
