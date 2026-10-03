from __future__ import annotations

import contextlib
import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, ClassVar

from signalbot import DataMessage, DataMessageHandler, ReceiptType, SignalBotError

if TYPE_CHECKING:
    from signalbot import DataMessageContext, ReceivedMessage, SignalBot

    from signalblast.broadcastbot import BroadcastBot

logger = logging.getLogger(__name__)

# Exactly one handler runs for each message, the matching one with the highest priority
EDIT_BROADCAST_PRIORITY = 40
COMMAND_PRIORITY = 30
REPLY_PRIORITY = 20
UNKNOWN_COMMAND_PRIORITY = 10
BROADCAST_PRIORITY = 0


class SignalblastHandler(DataMessageHandler):
    """A handler for private messages. Every message is handled by exactly one of them (see the
    priorities above), which sends the read receipt, replies if handling fails, and deletes the
    message's attachments from signal-cli afterwards."""

    priority: ClassVar[int]

    def __init__(self, bot: BroadcastBot) -> None:
        super().__init__()
        self.bot = bot

    def register(self, signal_bot: SignalBot) -> None:
        signal_bot.register(self, groups=False, f=self._filter, priority=self.priority)

    @abstractmethod
    def matches(self, message: DataMessage) -> bool:
        """Whether this handler handles `message`, checked by signalbot before running any handler."""

    @abstractmethod
    async def handle(self, ctx: DataMessageContext, sender: str) -> None:
        """Handles the message from `sender`."""

    def _filter(self, message: ReceivedMessage) -> bool:
        # Messages without a sender, or stickers and similar without text or attachments, are ignored
        return (
            isinstance(message, DataMessage)
            and message.source_uuid is not None
            and (message.text is not None or bool(message.attachments))
            and self.matches(message)
        )

    async def handle_data_message(self, context: DataMessageContext) -> None:
        sender = context.message.source_uuid
        if sender is None:
            return

        try:
            with contextlib.suppress(SignalBotError):
                await context.send_receipt(ReceiptType.READ)
            await self.handle(context, sender)
        except Exception:
            logger.exception("%s failed to handle a message", type(self).__name__)
            await self.bot.reply(context, "Something went wrong, please try again")
        finally:
            await self._delete_attachments(context)

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


class Command(SignalblastHandler):
    """A `!command`, matched case insensitively and only when followed by whitespace or the end of
    the message."""

    priority = COMMAND_PRIORITY

    trigger: ClassVar[str]
    description: ClassVar[str]
    args: ClassVar[str] = ""
    # Shown in the admin section of the help
    for_admins: ClassVar[bool] = False
    # Only admins may run it, e.g. `!add admin` is for admins but is how a user becomes one
    admin_only: ClassVar[bool] = False

    @classmethod
    def parse(cls, text: str | None) -> str | None:
        """The arguments of the command in `text`, None if `text` isn't this command."""
        if not text:
            return None
        text = text.strip()
        n = len(cls.trigger)
        if text[:n].lower() != cls.trigger or (len(text) > n and not text[n].isspace()):
            return None
        return text[n:].strip()

    @classmethod
    def usage(cls) -> str:
        return f"{cls.trigger} {cls.args}".strip()

    def matches(self, message: DataMessage) -> bool:
        return self.parse(message.text) is not None

    async def handle(self, ctx: DataMessageContext, sender: str) -> None:
        if self.admin_only and not self.bot.db.is_admin(sender):
            await self.bot.reply(ctx, "I'm sorry but only admins can do that")
            await self.bot.notify_admins(f"Someone who is not an admin tried to use {self.trigger}")
            return
        await self.run(ctx, sender, self.parse(ctx.message.text) or "")

    @abstractmethod
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        """Runs the command, `args` is the text after the trigger."""
