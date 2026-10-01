from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING

from signalbot import DataMessageHandler, EditMessage, ReceiptType, RemoteDeleteHandler, SignalBotError

from signalblast.commands import broadcast, messaging
from signalblast.commands.registry import help_message, parse

if TYPE_CHECKING:
    from signalbot import DataMessageContext, RemoteDeleteContext

    from signalblast.broadcastbot import BroadcastBot

logger = logging.getLogger(__name__)


class CommandRouter(DataMessageHandler, RemoteDeleteHandler):
    """Handles every private message the bot receives, in this order:

    1. Edits of a broadcast edit every copy of it.
    2. Commands run, admin only commands only for admins.
    3. Replies to a message about a user (see `messaging`) go to that user, they are never broadcast.
    4. Anything else starting with "!" gets the help, so mistyped commands are not broadcast.
    5. Everything else is broadcast.
    """

    def __init__(self, bot: BroadcastBot) -> None:
        super().__init__()
        self.bot = bot

    async def handle_data_message(self, context: DataMessageContext) -> None:
        message = context.message
        if message.source_uuid is None:
            logger.warning("Ignoring a message without a sender")
            return
        if message.text is None and not message.attachments:
            # Stickers and similar
            return

        try:
            with contextlib.suppress(SignalBotError):
                await context.send_receipt(ReceiptType.READ)
            await self._route(context, message.source_uuid)
        except Exception:
            logger.exception("Failed to handle a message")
            await self.bot.reply(context, "Something went wrong, please try again")
        finally:
            await self._delete_attachments(context)

    async def handle_remote_delete(self, context: RemoteDeleteContext) -> None:
        try:
            await broadcast.delete_broadcast(self.bot, context)
        except Exception:
            logger.exception("Failed to delete a broadcast")

    async def _route(self, ctx: DataMessageContext, sender: str) -> None:
        message = ctx.message
        command = parse(message.text)

        if isinstance(message, EditMessage):
            first_deliveries = self.bot.db.first_deliveries(sender, message.target_sent_timestamp)
            if first_deliveries:
                is_broadcast_command = command is not None and command[0].trigger == "!broadcast"
                text = command[1] if command is not None and is_broadcast_command else message.text
                await broadcast.edit_broadcast(self.bot, ctx, text, message.target_sent_timestamp, first_deliveries)
                return
            # Not an edit of a broadcast, handle it as a new message

        if command is not None:
            cmd, args = command
            if cmd.admin_only and not self.bot.db.is_admin(sender):
                await self.bot.reply(ctx, "I'm sorry but only admins can do that")
                await self.bot.notify_admins(f"Someone who is not an admin tried to use {cmd.trigger}")
                return
            await cmd.handler(self.bot, ctx, args)
            return

        if messaging.quotes_a_user_message(message.quote):
            await messaging.reply_to_user(self.bot, ctx)
            return

        if message.text is not None and message.text.lstrip().startswith("!"):
            await self.bot.reply(ctx, help_message(self.bot, is_admin=self.bot.db.is_admin(sender), understood=False))
            return

        await broadcast.send_broadcast(self.bot, ctx, message.text)

    @staticmethod
    async def _delete_attachments(ctx: DataMessageContext) -> None:
        """signal-cli keeps every received attachment, delete them once they've been handled."""
        attachments = list(ctx.message.attachments or [])
        attachments += [preview.image for preview in ctx.message.previews or [] if preview.image is not None]
        for attachment in attachments:
            try:
                await ctx.bot.attachments.delete(attachment)
            except SignalBotError:
                logger.warning("Could not delete an attachment", exc_info=True)
