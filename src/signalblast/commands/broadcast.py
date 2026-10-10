from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, override

from signalbot import EditMessage, LinkPreview, RemoteDeleteHandler, SendMessage, SentMessage, SignalBotError

from signalblast.commands.base import (
    BROADCAST_PRIORITY,
    EDIT_BROADCAST_PRIORITY,
    Command,
    SignalblastHandler,
)
from signalblast.utils import people

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine

    from signalbot import Context, DataMessage, DataMessageContext, RemoteDeleteContext, SignalBot

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
# Copies of a broadcast that could not be sent, edited or deleted are tried once more after a random
# delay, most failures are temporary
RETRY_DELAY_SECONDS = (10 * 60, 15 * 60)
RETRYING = "trying the rest again in a few minutes"
CONTACT_ADMINS = "please contact the admins with !admin if this keeps happening"


@dataclass
class BroadcastRetry:
    """A pending retry of the copies of a broadcast that failed, see `_schedule_retry`."""

    task: asyncio.Task[None] = field(init=False)
    # Whether the delay is over and the copies are being sent
    sending: bool = False


class BroadcastCommand(Command):
    trigger = "!broadcast"
    args = "<message>"
    description = "Send a message to every subscriber, anything that isn't a command is broadcast too"
    # Only needed for messages that start with "!", the help of unknown commands explains it
    in_help = False

    @override
    async def run(self, ctx: DataMessageContext, sender: str, args: str) -> None:
        await _broadcast(self.bot, ctx, args)


class Broadcast(SignalblastHandler):
    """Every message that no other handler handles is broadcast."""

    priority = BROADCAST_PRIORITY

    @override
    def matches(self, message: DataMessage) -> bool:
        return True

    @override
    async def handle(self, ctx: DataMessageContext, sender: str) -> None:
        await _broadcast(self.bot, ctx, ctx.message.text)


class EditBroadcast(SignalblastHandler):
    """The sender edited a broadcast, edit every copy of it. Subscribers who joined after it was sent
    receive the edit as a new message."""

    priority = EDIT_BROADCAST_PRIORITY

    @override
    def matches(self, message: DataMessage) -> bool:
        return (
            isinstance(message, EditMessage)
            and message.source_uuid is not None
            and bool(self.bot.db.deliveries(message.source_uuid, message.target_sent_timestamp))
        )

    @override
    async def handle(self, ctx: DataMessageContext, sender: str) -> None:
        text = BroadcastCommand.parse(ctx.message.text)
        await _broadcast(self.bot, ctx, ctx.message.text if text is None else text)


class DeleteBroadcast(RemoteDeleteHandler):
    """The sender deleted their message for everyone, delete every copy of it if it was a broadcast."""

    def __init__(self, bot: BroadcastBot) -> None:
        super().__init__()
        self.bot = bot

    def register(self, signal_bot: SignalBot) -> None:
        signal_bot.register(self, groups=False)

    @override
    async def handle_remote_delete(self, context: RemoteDeleteContext) -> None:
        try:
            await _delete_broadcast(self.bot, context)
        except Exception:
            logger.exception("Failed to delete a broadcast")


async def _broadcast(bot: BroadcastBot, ctx: DataMessageContext, text: str | None) -> None:
    """Sends the message in `ctx` to every subscriber, `text` is its text without the `!broadcast` command.
    If it edits a broadcast, the copies of that broadcast are edited. An edit of a message that wasn't
    broadcast is broadcast as new."""
    message = ctx.message
    sender = message.source_uuid
    if sender is None or not await _may_broadcast(bot, ctx, sender):
        return

    broadcast = _broadcast_message(ctx, text)
    if broadcast is None:
        await bot.reply(ctx, "There is nothing to broadcast, write your message after !broadcast")
        return

    # The copies of the version of the message that this one edits
    edited: dict[str, int] = {}
    if isinstance(message, EditMessage):
        # Who missed that version gets this one as a new message, there is no point in retrying it
        await _cancel_retry(bot, (sender, message.target_sent_timestamp))
        edited = bot.db.deliveries(sender, message.target_sent_timestamp)
    is_edit = bool(edited)
    recipients = bot.db.subscribers()
    random.shuffle(recipients)

    async with _typing(bot, ctx):
        delivered = await _send_to_each(
            recipients,
            lambda recipient: _send_copy(ctx, recipient, broadcast, edited.get(recipient), typing_for=sender),
        )

    bot.db.save_deliveries(sender, message.timestamp, delivered)
    # Failures only count once the retry fails too
    for recipient in delivered:
        bot.db.record_send_success(recipient)

    num_others = len(set(recipients) - {sender})
    num_delivered = len(delivered.keys() - {sender})
    action = "edited for" if is_edit else "sent to"
    failed = [recipient for recipient in recipients if recipient not in delivered]
    reply = await bot.reply(ctx, _broadcast_report(action, num_delivered, num_others, RETRYING))
    logger.info("Broadcast %s %s out of %s", action, num_delivered, people(num_others))
    logger.debug("Broadcast by %s", sender)
    if not failed:
        return

    async def finish(delivered_again: dict[str, int]) -> None:
        bot.db.save_deliveries(sender, message.timestamp, delivered_again)
        await _track_failures(bot, failed, delivered_again)
        if reply is not None:
            total = num_delivered + len(delivered_again.keys() - {sender})
            await bot.edit(reply, _broadcast_report(action, total, num_others, CONTACT_ADMINS))

    _schedule_retry(
        bot,
        (sender, message.timestamp),
        failed,
        lambda recipient: _send_copy(ctx, recipient, broadcast, edited.get(recipient), typing_for=None),
        finish,
    )


async def _delete_broadcast(bot: BroadcastBot, ctx: RemoteDeleteContext) -> None:
    sender = ctx.message.source_uuid
    if sender is None:
        return

    key = (sender, ctx.message.timestamp)
    # Whoever the retry is for doesn't have the message
    await _cancel_retry(bot, key)
    deliveries = bot.db.deliveries(*key)
    if not deliveries:
        logger.info("Ignoring the deletion of a message that is not a known broadcast")
        return
    if bot.db.is_banned(sender):
        logger.info("Ignoring the deletion of a broadcast by a banned user")
        return

    recipients = list(deliveries)
    random.shuffle(recipients)

    def delete(recipient: str) -> Coroutine[None, None, int]:
        return ctx.bot.messages.remote_delete(SentMessage(recipient=recipient, timestamp=deliveries[recipient]))

    deleted = await _send_to_each(recipients, delete)

    num_others = len(set(recipients) - {sender})
    num_deleted = len(deleted.keys() - {sender})
    failed = [recipient for recipient in recipients if recipient not in deleted]
    reply = None
    with contextlib.suppress(SignalBotError):
        reply = await ctx.send(SendMessage(text=_broadcast_report("deleted for", num_deleted, num_others, RETRYING)))
    logger.info("Broadcast deleted for %s out of %s", num_deleted, people(num_others))
    if not failed:
        return

    async def finish(deleted_again: dict[str, int]) -> None:
        if reply is not None:
            await bot.edit(reply, f"Message deleted for {people(num_deleted + len(deleted_again.keys() - {sender}))}")

    _schedule_retry(bot, key, failed, delete, finish)


def _broadcast_report(action: str, num_delivered: int, num_others: int, then: str) -> str:
    """What the sender is told about their broadcast, `then` is what happens about the failures."""
    if num_delivered == num_others:
        return f"Message {action} {people(num_delivered)}"
    return f"Message {action} {num_delivered} out of {people(num_others)}, {then}"


def _broadcast_message(ctx: DataMessageContext, text: str | None) -> SendMessage | None:
    """The message to send to every subscriber, `text` is the message without the `!broadcast` command.
    None if there is nothing to broadcast."""
    message = ctx.message
    attachments = [a.base64_content for a in message.attachments or [] if a.base64_content is not None]
    if not text and not attachments:
        return None

    link_preview = None
    if message.previews:
        preview = message.previews[0]
        # Signal rejects previews whose URL is not in the text
        if (
            preview.base64_thumbnail is not None
            and preview.title is not None
            and preview.url is not None
            and text is not None
            and preview.url in text
        ):
            link_preview = LinkPreview(
                description=preview.description or "",
                title=preview.title,
                url=preview.url,
                thumbnail=preview.base64_thumbnail,
            )

    return SendMessage(
        text=text or "",
        base64_attachments=attachments or None,
        link_preview=link_preview,
        view_once=message.view_once,
    )


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
    recipient: str,
    broadcast: SendMessage,
    edit_timestamp: int | None,
    typing_for: str | None,
) -> int:
    """Sends a copy of `broadcast` to `recipient`. The typing indicator is shown to `typing_for` while the
    broadcast is being sent, and receiving their copy stops it."""
    message = broadcast.model_copy(update={"edit_timestamp": edit_timestamp})
    sent = await ctx.bot.messages.send(message, recipient)
    if recipient == typing_for:
        await asyncio.sleep(RESUME_TYPING_DELAY_SECONDS)
        with contextlib.suppress(SignalBotError):
            await ctx.start_typing()
    return sent.timestamp


def _schedule_retry(
    bot: BroadcastBot,
    key: tuple[str, int],
    recipients: list[str],
    send: Callable[[str], Coroutine[None, None, int]],
    finish: Callable[[dict[str, int]], Awaitable[None]],
) -> None:
    """Runs `send` once more for `recipients` after a random delay, then `finish` with the timestamp of
    each successful send by recipient. `key` is the author and timestamp of the broadcast, see
    `_cancel_retry`."""
    retry = BroadcastRetry()

    async def run() -> None:
        try:
            await _wait_before_retry()
            retry.sending = True
            results = await _send_to_each(recipients, send)
            logger.info("Retried a broadcast for %s out of %s", len(results), people(len(recipients)))
            await finish(results)
        except Exception:
            logger.exception("Failed to retry a broadcast")
        finally:
            if bot.broadcast_retries.get(key) is retry:
                del bot.broadcast_retries[key]

    retry.task = asyncio.create_task(run())
    bot.broadcast_retries[key] = retry


async def _wait_before_retry() -> None:
    await asyncio.sleep(random.uniform(*RETRY_DELAY_SECONDS))  # noqa: S311 -- not for cryptography


async def _cancel_retry(bot: BroadcastBot, key: tuple[str, int]) -> None:
    """Cancels the retry of the broadcast that is being edited or deleted. If it is already sending, waits
    until it's done instead, so that the copies it sends are edited or deleted too."""
    retry = bot.broadcast_retries.pop(key, None)
    if retry is None:
        return
    if retry.sending:
        await asyncio.wait([retry.task])
    else:
        retry.task.cancel()


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
