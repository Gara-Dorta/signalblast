import asyncio
import contextlib
import random
from collections import defaultdict
from collections.abc import Awaitable
from re import Pattern

from signalbot import (
    Context,
    DataMessageContext,
    DataMessageHandler,
    EditMessage,
    ReceiptType,
    RemoteDeleteContext,
    RemoteDeleteHandler,
    SendMessage,
    SentMessage,
)

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import CommandRegex, PublicCommandStrings
from signalblast.utils import TimestampData


class Broadcast(DataMessageHandler, RemoteDeleteHandler):
    MAX_FAILED_MSGS = 10

    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot
        self.subscribers_num_fails: dict[str, int] = defaultdict(lambda: 0)

    def is_valid_command(self, message: str, invalid_command: Pattern) -> bool:
        return any(regex != invalid_command and regex.search(message) is not None for regex in CommandRegex)

    async def check_send_tasks_results(
        self,
        ctx: Context,
        send_tasks: list[asyncio.Task | None],
        action_str: str,
    ) -> dict[str, int]:
        timestamp_data = {}
        for send_task, subscriber in zip(send_tasks, self.broadcastbot.subscribers, strict=False):
            if send_task is not None:
                try:
                    timestamp_data[subscriber] = send_task.result()
                    self.subscribers_num_fails.pop(subscriber, None)
                    self.broadcastbot.logger.info("Message successfully %s %s", action_str, subscriber)
                except Exception:
                    self.subscribers_num_fails[subscriber] += 1
                    self.broadcastbot.logger.exception("Message not %s %s", action_str, subscriber)

        subscribers_to_remove = []
        for subscriber, num_fails in self.subscribers_num_fails.items():
            if num_fails >= Broadcast.MAX_FAILED_MSGS:
                subscribers_to_remove.append(subscriber)
                await self.broadcastbot.subscribers.remove(subscriber)

                remove_message = "The bot is having problems sending you messages. "
                remove_message += "You have been removed from the list. "
                remove_message += "Please update signal, remove old linked devices and try subscribing again."
                with contextlib.suppress(Exception):
                    # Most likely will fail to send the message but try anyway
                    await ctx.bot.messages.send(SendMessage(text=remove_message), subscriber)

        for subscriber in subscribers_to_remove:
            del self.subscribers_num_fails[subscriber]

        return timestamp_data

    async def _send_and_get_timestamp(
        self,
        context: DataMessageContext,
        send_message: SendMessage,
        recipient: str,
    ) -> int:
        sent_message = await context.bot.messages.send(send_message, recipient)
        return sent_message.timestamp

    async def _broadcast_send(self, context: DataMessageContext) -> None:  # noqa: C901, PLR0915, PLR0912 function is too complex
        broadcast_timestamps: dict[str, int] = {}
        num_subscribers = -1
        attachments_deleted = False
        send_tasks_checked = False
        timestamp_data_saved = False
        send_tasks: list[asyncio.Task | None] = []
        is_edit = isinstance(context.message, EditMessage)
        action_str, acting_str = ("edited for", "editing") if is_edit else ("sent to", "sending")

        try:
            subscriber_uuid = context.message.source_uuid
            if subscriber_uuid in self.broadcastbot.banned_users:
                await context.bot.messages.send(
                    SendMessage(text="This number is not allowed to send messages"),
                    subscriber_uuid,
                )
                self.broadcastbot.logger.info("%s tried to broadcast but they are banned", subscriber_uuid)
                return

            if subscriber_uuid not in self.broadcastbot.subscribers:
                await context.bot.messages.send(
                    SendMessage(text=self.broadcastbot.must_subscribe_message),
                    subscriber_uuid,
                )
                self.broadcastbot.logger.info("%s tried to broadcast but they are not subscribed", subscriber_uuid)
                return

            num_subscribers = len(self.broadcastbot.subscribers)

            message = self.broadcastbot.message_handler.remove_command_from_message(
                context.message.text,
                PublicCommandStrings.broadcast,
            )
            attachments = self.broadcastbot.message_handler.extract_base64_attachments(context.message.attachments)
            link_preview = self.broadcastbot.message_handler.extract_link_preview(context.message.previews)

            if message is None and attachments is None:
                return

            if message is None:
                message = ""

            await context.start_typing()

            # The typing indicator dissapears after 15 seconds. Restart it until the broadcast is done.
            typing_job = self.broadcastbot.scheduler.add_job(context.start_typing, "interval", seconds=15)

            # Broadcast message to all subscribers.
            send_tasks: list[asyncio.Task | None] = [None] * num_subscribers

            if is_edit:
                self.broadcastbot.storage_lock.acquire()
                prev_timestamps = context.bot.storage.read(
                    f"broadcast-uuid-{subscriber_uuid}-timestamp-{context.message.target_sent_timestamp}",
                )
                self.broadcastbot.storage_lock.release()
                to_modify_timestamps = TimestampData.model_validate(prev_timestamps).broadcast_timestamps
            else:
                to_modify_timestamps = {}

            for i, subscriber in enumerate(self.broadcastbot.subscribers):
                send_message = SendMessage(
                    text=message,
                    base64_attachments=attachments,
                    link_preview=link_preview,
                    edit_timestamp=to_modify_timestamps.get(subscriber),
                    view_once=context.message.view_once,
                )
                subscriber_fn = self._send_and_get_timestamp(context, send_message, subscriber)
                if subscriber == subscriber_uuid:
                    # Typing stops after sending/editing a message, so start typing right after
                    async def send_to_self(subscriber_fn: Awaitable[int]) -> int:
                        timestamp = await subscriber_fn
                        await asyncio.sleep(0.5)
                        await context.start_typing()
                        return timestamp

                    subscriber_fn = send_to_self(subscriber_fn)

                send_tasks[i] = asyncio.create_task(subscriber_fn)

                # Avoid rate limiting by waiting a random time between messages
                await asyncio.sleep(random.uniform(0.5, 1))  # noqa: S311

            await asyncio.wait(send_tasks)

            broadcast_timestamps = await self.check_send_tasks_results(context, send_tasks, action_str)
            send_tasks_checked = True

            broadcastdata = TimestampData(
                author=subscriber_uuid,
                timestamp=context.message.timestamp,
                broadcast_timestamps=broadcast_timestamps,
            )

            self.broadcastbot.storage_lock.acquire()
            context.bot.storage.save(
                f"broadcast-uuid-{subscriber_uuid}-timestamp-{context.message.timestamp}",
                broadcastdata.model_dump(),
            )
            self.broadcastbot.storage_lock.release()
            timestamp_data_saved = True

            await self.broadcastbot.message_handler.delete_attachments(context)
            attachments_deleted = True

            typing_job.remove()
            await context.stop_typing()
            await self.broadcastbot.reply_with_warn_on_failure(
                context,
                f"Message {action_str} {len(broadcast_timestamps) - 1} people",
            )

            self.broadcastbot.last_msg_user_uuid = subscriber_uuid
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                if send_tasks_checked is False:
                    broadcast_timestamps = await self.check_send_tasks_results(context, send_tasks, action_str)

                error_str = f"Something went wrong when {acting_str} the message"
                error_str += (
                    f", it was only {action_str} {len(broadcast_timestamps) - 1} out of {num_subscribers - 1} people"
                )
                error_str += ", please contact the admin if the problem persists"
                await self.broadcastbot.reply_with_warn_on_failure(context, error_str)

                if attachments_deleted is False:
                    await self.broadcastbot.message_handler.delete_attachments(context)

                if timestamp_data_saved is False:
                    broadcastdata = TimestampData(
                        author=subscriber_uuid,
                        timestamp=context.message.timestamp,
                        broadcast_timestamps=broadcast_timestamps,
                    )
                    self.broadcastbot.storage_lock.acquire()
                    context.bot.storage.save(
                        f"broadcast-uuid-{subscriber_uuid}-timestamp-{context.message.timestamp}",
                        broadcastdata.model_dump(),
                    )
                    self.broadcastbot.storage_lock.release()
            except Exception:
                self.broadcastbot.logger.exception("")

    async def _broadcast_delete(self, context: RemoteDeleteContext) -> None:
        broadcast_timestamps: dict[str, int] = {}
        num_subscribers = -1
        send_tasks: list[asyncio.Task | None] = []
        action_str, acting_str = "deleted for", "deleting"

        try:
            subscriber_uuid = context.message.source_uuid
            if subscriber_uuid in self.broadcastbot.banned_users:
                self.broadcastbot.logger.info("%s tried to broadcast but they are banned", subscriber_uuid)
                return

            if subscriber_uuid not in self.broadcastbot.subscribers:
                self.broadcastbot.logger.info("%s tried to broadcast but they are not subscribed", subscriber_uuid)
                return

            num_subscribers = len(self.broadcastbot.subscribers)

            self.broadcastbot.storage_lock.acquire()
            prev_timestamps = context.bot.storage.read(
                f"broadcast-uuid-{subscriber_uuid}-timestamp-{context.message.timestamp}",
            )
            self.broadcastbot.storage_lock.release()
            to_modify_timestamps = TimestampData.model_validate(prev_timestamps).broadcast_timestamps

            send_tasks = [None] * num_subscribers
            for i, subscriber in enumerate(self.broadcastbot.subscribers):
                sent_message = SentMessage(recipient=subscriber, timestamp=to_modify_timestamps.get(subscriber))
                subscriber_fn = context.bot.messages.remote_delete(sent_message)
                send_tasks[i] = asyncio.create_task(subscriber_fn)

                # Avoid rate limiting by waiting a random time between messages
                await asyncio.sleep(random.uniform(0.5, 1))  # noqa: S311

            await asyncio.wait(send_tasks)

            broadcast_timestamps = await self.check_send_tasks_results(context, send_tasks, action_str)

            await self.broadcastbot.send_with_warn_on_failure(
                context,
                f"Message {action_str} {len(broadcast_timestamps) - 1} people",
            )

            self.broadcastbot.last_msg_user_uuid = subscriber_uuid
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                broadcast_timestamps = await self.check_send_tasks_results(context, send_tasks, action_str)

                error_str = f"Something went wrong when {acting_str} the message"
                error_str += (
                    f", it was only {action_str} {len(broadcast_timestamps) - 1} out of {num_subscribers - 1} people"
                )
                error_str += ", please contact the admin if the problem persists"
                await self.broadcastbot.send_with_warn_on_failure(context, error_str)
            except Exception:
                self.broadcastbot.logger.exception("")

    async def handle_data_message(self, context: DataMessageContext) -> None:
        message = context.message.text
        subscriber_uuid = context.message.source_uuid

        if message is None:
            if not context.message.attachments:
                self.broadcastbot.logger.info("Received reaction, sticker or similar from %s", subscriber_uuid)
                return

            await context.send_receipt(ReceiptType.READ)

            # Only attachment, assume the user wants to forward that
            self.broadcastbot.logger.info("Received a file from %s, broadcasting!", subscriber_uuid)
            await self._broadcast_send(context)
            return

        if self.is_valid_command(message, invalid_command=CommandRegex.broadcast):
            return

        await context.send_receipt(ReceiptType.READ)

        # By default broadcast all the messages
        await self._broadcast_send(context)

    async def handle_remote_delete(self, context: RemoteDeleteContext) -> None:
        await self._broadcast_delete(context)
