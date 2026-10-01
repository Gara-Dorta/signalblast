from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from signalbot import __version__ as signalbot_version

from signalblast import __version__ as signalblast_version
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


async def add_admin(bot: BroadcastBot, ctx: DataMessageContext, args: str) -> None:
    sender = ctx.message.source_uuid
    if sender is None:
        return

    if not args:
        await bot.reply(ctx, "Missing the password, usage: !add admin <password>")
        return

    if not await _check_password(bot, ctx, args, "become an admin"):
        return

    if not bot.db.add_admin(sender):
        await bot.reply(ctx, "You are already an admin")
        return

    await bot.reply(ctx, "You are now an admin! Send !help to see the admin commands")
    await bot.notify_admins(f"{sender} is now an admin", exclude=(sender,))
    logger.info("New admin")
    logger.debug("New admin %s", sender)


async def remove_admin(bot: BroadcastBot, ctx: DataMessageContext, args: str) -> None:
    sender = ctx.message.source_uuid
    if sender is None:
        return

    # The admin id is the last word, the password may contain spaces
    password, _, admin_id = args.rpartition(" ")
    if not password.strip() or not _is_uuid(admin_id):
        await bot.reply(ctx, "Usage: !remove admin <password> <admin id>, see the admin ids with !list admins")
        return

    if not await _check_password(bot, ctx, password, "remove an admin"):
        return

    if not bot.db.remove_admin(admin_id):
        await bot.reply(ctx, f"{admin_id} is not an admin")
        return

    await bot.reply(ctx, f"Removed admin {admin_id}")
    if admin_id != sender:
        await bot.send(admin_id, "You are no longer an admin")
    await bot.notify_admins(f"{admin_id} is no longer an admin", exclude=(sender,))
    logger.info("Removed an admin")
    logger.debug("Removed admin %s", admin_id)


async def list_admins(bot: BroadcastBot, ctx: DataMessageContext, _args: str) -> None:
    sender = ctx.message.source_uuid
    lines = [f"{admin} (you)" if admin == sender else admin for admin in bot.db.admins()]
    await bot.reply(ctx, "Admins:\n" + "\n".join(lines))


async def show_version(bot: BroadcastBot, ctx: DataMessageContext, _args: str) -> None:
    signal_cli_rest_api_version = (await ctx.bot.general.about()).version
    await bot.reply(
        ctx,
        "Versions:\n"
        f"\tsignalblast: {signalblast_version}\n"
        f"\tsignalbot: {signalbot_version}\n"
        f"\tsignal-cli-rest-api: {signal_cli_rest_api_version}",
    )
