"""Conversations between users and the admins.

Admins never see who they are talking to. A user's `!admin` message reaches every admin as "User wrote: …",
an admin replies by quoting it, the user receives the reply as "Admin: …" and answers by quoting it, and so on.

Every message of a conversation is recorded with its copy in each chat it reached: the sender's own message
(and the bot's confirmation to them) and the bot's copies for everyone else. So quoting any copy continues the
conversation and is never broadcast, and each copy that the bot sends quotes, in the same chat, the copy of the
message it answers. Every chat then shows the conversation as a thread, without repeating the messages. Only
which user each message is about and who wrote it are stored, never its content.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, override

from signalblast.commands.base import REPLY_PRIORITY, Command, SignalblastHandler
from signalblast.utils import now_ms, snippet

if TYPE_CHECKING:
    from signalbot import DataMessage, DataMessageContext

    from signalblast.broadcastbot import BroadcastBot
    from signalblast.database import ConversationMessage, MessageCopy

logger = logging.getLogger(__name__)

# Start the messages that the bot sends to the admins about a user
USER_WROTE = "User wrote:"
USER_REPLIED = "User replied:"
REPLY_SENT = "Reply sent to user"
REPLY_NOT_SENT = "Reply not sent to user, please try again"
ANSWERED_BY_ADMIN = "User was answered by an admin:"
# Start the messages that the bot sends to a user
FROM_ADMIN = "Admin:"
MESSAGE_SENT = "Message sent to the admins"
# Recognise the bot's copies even after they have expired from the database, so they are never broadcast
_CONVERSATION_PREFIXES = (
    USER_WROTE,
    USER_REPLIED,
    REPLY_SENT,
    REPLY_NOT_SENT,
    ANSWERED_BY_ADMIN,
    FROM_ADMIN,
    MESSAGE_SENT,
)


@dataclass(frozen=True)
class QuoteTarget:
    """The user behind a quoted broadcast or message to the admins."""

    uuid: str
    snippet: str | None


def resolve_quote(bot: BroadcastBot, ctx: DataMessageContext) -> QuoteTarget | None:
    """Who sent the broadcast or the message to the admins that the sender quoted, None if it can't be known
    (no quote, the message has expired, or it is neither, e.g. an admin's reply)."""
    sender = ctx.message.source_uuid
    quote = ctx.message.quote
    if sender is None or quote is None:
        return None

    author = bot.db.broadcast_author(sender, quote.id)
    if author is not None:
        return QuoteTarget(author, snippet(quote.text))

    message = bot.db.conversation_message(sender, quote.id)
    if message is not None and message.from_user:
        # Drop the "User wrote:" line
        _, _, text = (quote.text or "").partition("\n")
        return QuoteTarget(message.user, snippet(text))

    return None


def _attachments(ctx: DataMessageContext) -> list[str] | None:
    attachments = [a.base64_content for a in ctx.message.attachments or [] if a.base64_content is not None]
    return attachments or None


def _record_received(bot: BroadcastBot, ctx: DataMessageContext, sender: str, *, user: str) -> int:
    """Records the message in `ctx` as a new message of the conversation with `user`. Returns its id."""
    message_id = bot.db.add_conversation_message(user, author=sender, sent_at=now_ms())
    bot.db.add_copy(message_id, sender, ctx.message.timestamp)
    return message_id


async def _send_copy(  # noqa: PLR0913
    bot: BroadcastBot,
    chat: str,
    message_id: int,
    text: str,
    *,
    quote: MessageCopy | None,
    attachments: list[str] | None = None,
) -> bool:
    """Sends `text` to `chat` as its copy of the message `message_id`, quoting `quote`, and records it."""
    timestamp = await bot.send(
        chat,
        text.rstrip(),
        attachments,
        quote_timestamp=quote.timestamp if quote is not None else None,
        quote_author=(quote.author or bot.settings.phone_number) if quote is not None else None,
    )
    if timestamp is None:
        return False
    bot.db.add_copy(message_id, chat, timestamp)
    return True


async def _confirm(bot: BroadcastBot, ctx: DataMessageContext, sender: str, message_id: int, text: str) -> None:
    """Tells the sender of the message in `ctx`, recorded as `message_id`, what happened to it."""
    reply = await bot.reply(ctx, text)
    if reply is not None:
        bot.db.add_copy(message_id, sender, reply.timestamp)


async def _write_to_admins(
    bot: BroadcastBot,
    ctx: DataMessageContext,
    sender: str,
    text: str,
    replied_to: ConversationMessage | None,
) -> None:
    """Sends `text` and the attachments in `ctx` to every admin, as a new conversation or as an answer
    to `replied_to`."""
    if bot.db.is_banned(sender):
        await bot.reply(ctx, "You are not allowed to contact the admins")
        logger.info("A banned user tried to contact the admins")
        return

    admins = [admin for admin in bot.db.admins() if admin != sender]
    if not admins:
        await bot.reply(ctx, "I'm sorry but there are no admins to contact")
        return

    message_id = _record_received(bot, ctx, sender, user=sender)
    header = USER_WROTE if replied_to is None else USER_REPLIED
    attachments = _attachments(ctx)
    num_sent = 0
    for admin in admins:
        quote = bot.db.copy_in_chat(replied_to.id, admin) if replied_to is not None else None
        num_sent += await _send_copy(bot, admin, message_id, f"{header}\n{text}", quote=quote, attachments=attachments)

    if num_sent == 0:
        await bot.reply(ctx, "I couldn't reach the admins, please try again later")
        return

    await _confirm(bot, ctx, sender, message_id, MESSAGE_SENT)
    logger.info("Forwarded a message from a user to %s admins", num_sent)


async def _reply_to_user(
    bot: BroadcastBot, ctx: DataMessageContext, admin: str, replied_to: ConversationMessage
) -> None:
    text = ctx.message.text or ""
    user = replied_to.user
    message_id = _record_received(bot, ctx, admin, user=user)

    quote = bot.db.copy_in_chat(replied_to.id, user)
    if not await _send_copy(bot, user, message_id, f"{FROM_ADMIN} {text}", quote=quote, attachments=_attachments(ctx)):
        await _confirm(bot, ctx, admin, message_id, REPLY_NOT_SENT)
        return

    await _confirm(bot, ctx, admin, message_id, REPLY_SENT)
    for other in bot.db.admins():
        if other != admin:
            quote = bot.db.copy_in_chat(replied_to.id, other)
            await _send_copy(bot, other, message_id, f"{ANSWERED_BY_ADMIN}\n{text}", quote=quote)
    logger.info("An admin replied to a user")


class MessageAdmins(Command):
    trigger = "!admin"
    args = "<message>"
    description = "Send a message only to the admins"

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        if not args and _attachments(ctx) is None:
            await self.bot.reply(ctx, "Write your message after !admin, e.g. !admin I have a question")
            return

        await _write_to_admins(self.bot, ctx, sender, args, replied_to=None)


class Reply(SignalblastHandler):
    """The sender quoted a message of a conversation between a user and the admins: an admin replies to the
    user, or the user answers the admins. Never broadcast, even when it isn't sent (the sender is no longer
    an admin, or the conversation has expired)."""

    priority = REPLY_PRIORITY

    @override
    def matches(self, message: DataMessage) -> bool:
        quote = message.quote
        if quote is None or message.source_uuid is None:
            return False
        if quote.text is not None and quote.text.startswith(_CONVERSATION_PREFIXES):
            return True
        return self.bot.db.conversation_message(message.source_uuid, quote.id) is not None

    @override
    async def handle(self, ctx: DataMessageContext, sender: str) -> None:
        quote = ctx.message.quote
        if quote is None:
            return

        replied_to = self.bot.db.conversation_message(sender, quote.id)
        if replied_to is None:
            expired = (
                "Not sent: this message is older than 7 days, so its sender can no longer be reached"
                if self.bot.db.is_admin(sender)
                else "Not sent: this conversation is older than 7 days, write to the admins with !admin instead"
            )
            await self.bot.reply(ctx, expired)
        elif replied_to.user == sender:
            await _write_to_admins(self.bot, ctx, sender, ctx.message.text or "", replied_to)
        elif self.bot.db.is_admin(sender):
            await _reply_to_user(self.bot, ctx, sender, replied_to)
        else:
            await self.bot.reply(ctx, "Not sent: only admins can reply to messages from users")
