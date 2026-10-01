"""Messages between users and the admins.

Admins never see who they are talking to: a user's `!admin` message reaches them as "User #7 wrote: …",
and an admin replies by quoting it. Every message the bot sends to an admin about a user starts with
`USER_PREFIX` and is recorded, so quoting any of them reaches that user.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from signalblast.utils import now_ms, snippet

if TYPE_CHECKING:
    from signalbot import DataMessageContext, Quote

    from signalblast.broadcastbot import BroadcastBot

logger = logging.getLogger(__name__)

USER_PREFIX = "User #"


@dataclass(frozen=True)
class QuoteTarget:
    """The user behind a quoted broadcast or message about a user."""

    uuid: str
    snippet: str | None
    pseudonym_id: int | None = None


def quotes_a_user_message(quote: Quote | None) -> bool:
    """Whether `quote` is a message that the bot sent to an admin about a user. Works without the database,
    so it is recognised even after the message has expired."""
    return quote is not None and quote.text is not None and quote.text.startswith(USER_PREFIX)


def resolve_quote(bot: BroadcastBot, ctx: DataMessageContext) -> QuoteTarget | None:
    """Who sent the broadcast or the `!admin` message that the sender quoted, None if it can't be known
    (no quote, the message has expired, or it is neither)."""
    sender = ctx.message.source_uuid
    quote = ctx.message.quote
    if sender is None or quote is None:
        return None

    author = bot.db.broadcast_author(sender, quote.id)
    if author is not None:
        return QuoteTarget(author, snippet(quote.text))

    user = bot.db.admin_message_sender(sender, quote.id)
    if user is not None and quote.text is not None:
        # Drop the "User #7 wrote:" line
        _, _, text = quote.text.partition("\n")
        return QuoteTarget(user.uuid, snippet(text), user.pseudonym_id)

    return None


def _attachments(ctx: DataMessageContext) -> list[str] | None:
    attachments = [a.base64_content for a in ctx.message.attachments or [] if a.base64_content is not None]
    return attachments or None


async def _send_about_user(
    bot: BroadcastBot,
    admin: str,
    pseudonym_id: int,
    text: str,
    attachments: list[str] | None = None,
) -> bool:
    """Sends a message starting with "User #<pseudonym_id>" to `admin` and records it, so it can be quoted."""
    timestamp = await bot.send(admin, f"{USER_PREFIX}{pseudonym_id} {text}", attachments)
    if timestamp is None:
        return False
    bot.db.save_admin_message(admin, timestamp, pseudonym_id, now_ms())
    return True


async def message_admins(bot: BroadcastBot, ctx: DataMessageContext, args: str) -> None:
    sender = ctx.message.source_uuid
    if sender is None:
        return

    if bot.db.is_banned(sender):
        await bot.reply(ctx, "You are not allowed to contact the admins")
        logger.info("A banned user tried to contact the admins")
        return

    attachments = _attachments(ctx)
    if not args and attachments is None:
        await bot.reply(ctx, "Write your message after !admin, e.g. !admin I have a question")
        return

    admins = [admin for admin in bot.db.admins() if admin != sender]
    if not admins:
        await bot.reply(ctx, "I'm sorry but there are no admins to contact")
        return

    pseudonym_id = bot.db.pseudonym_for(sender, now_ms())
    num_sent = 0
    for admin in admins:
        num_sent += await _send_about_user(bot, admin, pseudonym_id, f"wrote:\n{args}".rstrip(), attachments)

    if num_sent == 0:
        await bot.reply(ctx, "I couldn't reach the admins, please try again later")
        return

    await bot.reply(ctx, "Message sent to the admins")
    logger.info("Forwarded a message from user #%s to %s admins", pseudonym_id, num_sent)


async def reply_to_user(bot: BroadcastBot, ctx: DataMessageContext) -> None:
    """An admin quoted a message about a user and wrote a reply."""
    sender = ctx.message.source_uuid
    quote = ctx.message.quote
    if sender is None or quote is None:
        return

    if not bot.db.is_admin(sender):
        await bot.reply(ctx, "Not sent: only admins can reply to messages from users")
        return

    user = bot.db.admin_message_sender(sender, quote.id)
    if user is None:
        await bot.reply(ctx, "Not sent: this message is older than 7 days, so its sender can no longer be reached")
        return

    text = ctx.message.text or ""
    attachments = _attachments(ctx)
    if await bot.send(user.uuid, f"Admin: {text}".rstrip(), attachments) is None:
        await _send_about_user(bot, sender, user.pseudonym_id, "could not receive your reply, please try again")
        return

    await _send_about_user(bot, sender, user.pseudonym_id, "received your reply")
    for admin in bot.db.admins():
        if admin != sender:
            await _send_about_user(bot, admin, user.pseudonym_id, f"was answered by an admin:\n{text}".rstrip())
    logger.info("An admin replied to user #%s", user.pseudonym_id)
