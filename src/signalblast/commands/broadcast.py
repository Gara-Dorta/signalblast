from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from signalbot import EditMessage, LinkPreview, SendMessage, SentMessage, SignalBotError

from signalblast.utils import people

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable, Coroutine

    from signalbot import Context, DataMessageContext, RemoteDeleteContext

    from signalblast.broadcastbot import BroadcastBot

logger = logging.getLogger(__name__)

# Subscribers are removed after this many broadcasts in a row could not be sent to them
MAX_FAILED_SENDS = 10
# Signal stops showing the typing indicator after 15 seconds
TYPING_REFRESH_SECONDS = 15
# Random delay between the copies of a broadcast, to avoid Signal's rate limits
SEND_DELAY_SECONDS = (0.5, 1.0)
# Receiving a message stops the typing indicator, wait a bit before starting it again
RESUME_TYPING_DELAY_SECONDS = 0.5


@dataclass(frozen=True)
class BroadcastContent:
    text: str
    attachments: list[str] | None
    link_preview: LinkPreview | None
    view_once: bool | None

    @classmethod
    def from_message(cls, ctx: DataMessageContext, text: str | None) -> BroadcastContent | None:
        """`text` is the message without the `!broadcast` command. None if there is nothing to broadcast."""
        message = ctx.message
        attachments = [a.base64_content for a in message.attachments or [] if a.base64_content is not None]
        if not text and not attachments:
            return None

        link_preview = None
        if message.previews:
            preview = message.previews[0]
            if preview.base64_thumbnail is not None and preview.title is not None and preview.url is not None:
                link_preview = LinkPreview(
                    description=preview.description or "",
                    title=preview.title,
                    url=preview.url,
                    thumbnail=preview.base64_thumbnail,
                )

        return cls(text or "", attachments or None, link_preview, message.view_once)


async def broadcast_command(bot: BroadcastBot, ctx: DataMessageContext, args: str) -> None:
    await send_broadcast(bot, ctx, args)


async def send_broadcast(bot: BroadcastBot, ctx: DataMessageContext, text: str | None) -> None:
    """Sends the message in `ctx` to every subscriber, `text` is its text without the `!broadcast` command."""
    message = ctx.message
    # An edit of a message that wasn't broadcast is broadcast as new. Record it under the original message,
    # which is what later edits and deletes of it refer to
    broadcast_ts = message.target_sent_timestamp if isinstance(message, EditMessage) else message.timestamp
    await _broadcast(bot, ctx, text, broadcast_ts=broadcast_ts, first_deliveries={})


async def edit_broadcast(
    bot: BroadcastBot,
    ctx: DataMessageContext,
    text: str | None,
    broadcast_ts: int,
    first_deliveries: dict[str, int],
) -> None:
    """Edits the broadcast sent at `broadcast_ts`. Subscribers who joined later receive it as a new message."""
    await _broadcast(bot, ctx, text, broadcast_ts=broadcast_ts, first_deliveries=first_deliveries)


async def _broadcast(
    bot: BroadcastBot,
    ctx: DataMessageContext,
    text: str | None,
    *,
    broadcast_ts: int,
    first_deliveries: dict[str, int],
) -> None:
    sender = ctx.message.source_uuid
    if sender is None or not await _may_broadcast(bot, ctx, sender):
        return

    content = BroadcastContent.from_message(ctx, text)
    if content is None:
        await bot.reply(ctx, "There is nothing to broadcast, write your message after !broadcast")
        return

    is_edit = bool(first_deliveries)
    recipients = bot.db.subscribers()
    random.shuffle(recipients)

    async with _typing(bot, ctx):
        delivered = await _send_to_each(
            recipients,
            lambda recipient: _send_copy(ctx, sender, recipient, content, first_deliveries.get(recipient)),
        )

    bot.db.save_deliveries(
        sender,
        broadcast_ts,
        {recipient: ts for recipient, ts in delivered.items() if recipient not in first_deliveries},
        is_edit=False,
    )
    if is_edit:
        bot.db.save_deliveries(
            sender,
            broadcast_ts,
            {recipient: ts for recipient, ts in delivered.items() if recipient in first_deliveries},
            is_edit=True,
        )
    await _track_failures(bot, recipients, delivered)

    others = [recipient for recipient in recipients if recipient != sender]
    num_delivered = sum(recipient in delivered for recipient in others)
    action = "edited for" if is_edit else "sent to"
    if num_delivered == len(others):
        await bot.reply(ctx, f"Message {action} {people(num_delivered)}")
    else:
        await bot.reply(
            ctx,
            f"Message {action} {num_delivered} out of {people(len(others))}, "
            "please contact the admins with !admin if this keeps happening",
        )
    logger.info("Broadcast %s %s out of %s", action, num_delivered, people(len(others)))
    logger.debug("Broadcast by %s", sender)


async def delete_broadcast(bot: BroadcastBot, ctx: RemoteDeleteContext) -> None:
    """The sender deleted their message for everyone, delete every copy of it if it was a broadcast."""
    sender = ctx.message.source_uuid
    if sender is None:
        return

    first_deliveries = bot.db.first_deliveries(sender, ctx.message.timestamp)
    if not first_deliveries:
        logger.info("Ignoring the deletion of a message that is not a known broadcast")
        return
    if bot.db.is_banned(sender):
        logger.info("Ignoring the deletion of a broadcast by a banned user")
        return

    recipients = list(first_deliveries)
    random.shuffle(recipients)
    deleted = await _send_to_each(
        recipients,
        lambda recipient: ctx.bot.messages.remote_delete(
            SentMessage(recipient=recipient, timestamp=first_deliveries[recipient])
        ),
    )

    num_deleted = sum(recipient in deleted for recipient in recipients if recipient != sender)
    with contextlib.suppress(SignalBotError):
        await ctx.send(SendMessage(text=f"Message deleted for {people(num_deleted)}"))
    logger.info("Broadcast deleted for %s", people(num_deleted))


async def _may_broadcast(bot: BroadcastBot, ctx: DataMessageContext, sender: str) -> bool:
    if bot.db.is_banned(sender):
        await bot.reply(ctx, "This number is not allowed to send messages")
        logger.info("A banned user tried to broadcast")
        return False

    if not bot.db.is_subscriber(sender):
        message = "To be able to send messages you must sign up.\nPlease sign up by sending:\n\t!subscribe\n"
        message += "and try again after that."
        if bot.settings.instructions_url is not None:
            message += (
                f"\nPlease have a look at the instructions if you haven't already:\n{bot.settings.instructions_url}"
            )
        await bot.reply(ctx, message)
        logger.info("A non subscriber tried to broadcast")
        return False

    return True


async def _send_to_each(
    recipients: list[str],
    send: Callable[[str], Coroutine[None, None, int]],
) -> dict[str, int]:
    """Runs `send` for every recipient, spaced out by a random delay to avoid Signal's rate limits.
    Returns the timestamp of each successful send by recipient."""
    tasks: dict[str, asyncio.Task[int]] = {}
    try:
        for i, recipient in enumerate(recipients):
            if i > 0:
                await asyncio.sleep(random.uniform(*SEND_DELAY_SECONDS))  # noqa: S311 -- not for cryptography
            tasks[recipient] = asyncio.create_task(send(recipient))
    finally:
        # Also on errors or cancellation, so no send is left running without anyone looking at its result
        await asyncio.gather(*tasks.values(), return_exceptions=True)

    results = {}
    for recipient, task in tasks.items():
        if task.exception() is None:
            results[recipient] = task.result()
        else:
            logger.warning("Could not send to a subscriber: %r", task.exception())
            logger.debug("Could not send to %s", recipient, exc_info=task.exception())
    return results


async def _send_copy(
    ctx: DataMessageContext,
    sender: str,
    recipient: str,
    content: BroadcastContent,
    edit_timestamp: int | None,
) -> int:
    message = SendMessage(
        text=content.text,
        base64_attachments=content.attachments,
        link_preview=content.link_preview,
        view_once=content.view_once,
        edit_timestamp=edit_timestamp,
    )
    sent = await ctx.bot.messages.send(message, recipient)
    if recipient == sender:
        await asyncio.sleep(RESUME_TYPING_DELAY_SECONDS)
        with contextlib.suppress(SignalBotError):
            await ctx.start_typing()
    return sent.timestamp


async def _track_failures(bot: BroadcastBot, recipients: list[str], delivered: dict[str, int]) -> None:
    for recipient in recipients:
        if recipient in delivered:
            bot.db.record_send_success(recipient)
            continue

        if bot.db.record_send_failure(recipient) >= MAX_FAILED_SENDS:
            bot.db.remove_subscriber(recipient)
            logger.info("Unsubscribed a subscriber after %s failed broadcasts in a row", MAX_FAILED_SENDS)
            # Most likely this fails too, but try anyway
            await bot.send(
                recipient,
                "The bot is having problems sending you messages. You have been removed from the list. "
                "Please update Signal, remove old linked devices and subscribe again.",
            )


@contextlib.asynccontextmanager
async def _typing(bot: BroadcastBot, ctx: Context) -> AsyncGenerator[None]:
    """Shows the typing indicator to the sender while the broadcast is being sent."""

    async def start_typing() -> None:
        with contextlib.suppress(SignalBotError):
            await ctx.start_typing()

    await start_typing()
    job = bot.scheduler.add_job(start_typing, "interval", seconds=TYPING_REFRESH_SECONDS)
    try:
        yield
    finally:
        job.remove()
        with contextlib.suppress(SignalBotError):
            await ctx.stop_typing()
