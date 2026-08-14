from __future__ import annotations

import asyncio
import contextlib
import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

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

from signalblast.commands_strings import CommandRegex, PublicCommandStrings
from signalblast.utils import TimestampData

if TYPE_CHECKING:
    from collections.abc import Awaitable
    from re import Pattern

    from signalbot import LinkPreview

    from signalblast.broadcastbot import BroadcasBot


@dataclass
class _BroadcastContent:
    message: str
    attachments: list[str] | None
    link_preview: LinkPreview | None
    view_once: bool | None


@dataclass
class _BroadcastState:
    subscriber_uuid: str
    action_str: str
    acting_str: str
    num_subscribers: int = -1
    broadcast_timestamps: dict[str, int] = field(default_factory=dict)
    send_tasks: list[tuple[str, asyncio.Task[int]]] = field(default_factory=list)
    send_tasks_checked: bool = False
    attachments_deleted: bool = False
    timestamp_data_saved: bool = False


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
        send_tasks: list[tuple[str, asyncio.Task[int]]],
        action_str: str,
    ) -> dict[str, int]:
        timestamp_data = {}
        for subscriber, send_task in send_tasks:
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

    @staticmethod
    async def _send_to_self_and_resume_typing(context: DataMessageContext, subscriber_fn: Awaitable[int]) -> int:
        # Typing stops after sending/editing a message, so start typing right after
        timestamp = await subscriber_fn
        await asyncio.sleep(0.5)
        await context.start_typing()
        return timestamp

    async def _reject_ineligible_sender(self, context: DataMessageContext, subscriber_uuid: str) -> bool:
        """Reply and log if the sender may not broadcast. Returns True if the sender was rejected."""
        if subscriber_uuid in self.broadcastbot.banned_users:
            await context.bot.messages.send(
                SendMessage(text="This number is not allowed to send messages"),
                subscriber_uuid,
            )
            self.broadcastbot.logger.info("%s tried to broadcast but they are banned", subscriber_uuid)
            return True

        if subscriber_uuid not in self.broadcastbot.subscribers:
            await context.bot.messages.send(
                SendMessage(text=self.broadcastbot.must_subscribe_message),
                subscriber_uuid,
            )
            self.broadcastbot.logger.info("%s tried to broadcast but they are not subscribed", subscriber_uuid)
            return True

        return False

    def _extract_broadcast_content(self, context: DataMessageContext) -> _BroadcastContent | None:
        """Returns None if there is nothing to broadcast (no text and no attachments)."""
        message = self.broadcastbot.message_handler.remove_command_from_message(
            context.message.text,
            PublicCommandStrings.broadcast,
        )
        attachments = self.broadcastbot.message_handler.extract_base64_attachments(context.message.attachments)
        link_preview = self.broadcastbot.message_handler.extract_link_preview(context.message.previews)

        if message is None and attachments is None:
            return None

        return _BroadcastContent(
            message=message or "",
            attachments=attachments,
            link_preview=link_preview,
            view_once=context.message.view_once,
        )

    async def _resolve_edit_timestamps(
        self,
        context: DataMessageContext,
        subscriber_uuid: str,
    ) -> dict[str, int]:
        if not isinstance(context.message, EditMessage):
            return {}

        self.broadcastbot.storage_lock.acquire()
        prev_timestamps = context.bot.storage.read(
            f"broadcast-uuid-{subscriber_uuid}-timestamp-{context.message.target_sent_timestamp}",
        )
        self.broadcastbot.storage_lock.release()
        return TimestampData.model_validate(prev_timestamps).broadcast_timestamps

    async def _dispatch_broadcast_tasks(
        self,
        context: DataMessageContext,
        subscriber_uuid: str,
        send_tasks: list[tuple[str, asyncio.Task[int]]],
        content: _BroadcastContent,
        to_modify_timestamps: dict[str, int],
    ) -> None:
        for subscriber in self.broadcastbot.subscribers:
            send_message = SendMessage(
                text=content.message,
                base64_attachments=content.attachments,
                link_preview=content.link_preview,
                edit_timestamp=to_modify_timestamps.get(subscriber),
                view_once=content.view_once,
            )
            subscriber_fn: Awaitable[int] = self._send_and_get_timestamp(context, send_message, subscriber)
            if subscriber == subscriber_uuid:
                subscriber_fn = self._send_to_self_and_resume_typing(context, subscriber_fn)

            send_tasks.append((subscriber, asyncio.create_task(subscriber_fn)))

            # Avoid rate limiting by waiting a random time between messages
            await asyncio.sleep(random.uniform(0.5, 1))  # noqa: S311

    def _save_broadcast_timestamps(
        self,
        context: DataMessageContext,
        subscriber_uuid: str,
        broadcast_timestamps: dict[str, int],
    ) -> None:
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

    async def _recover_from_broadcast_failure(self, context: DataMessageContext, state: _BroadcastState) -> None:
        try:
            if not state.send_tasks_checked:
                state.broadcast_timestamps = await self.check_send_tasks_results(
                    context,
                    state.send_tasks,
                    state.action_str,
                )

            error_str = f"Something went wrong when {state.acting_str} the message"
            error_str += (
                f", it was only {state.action_str} "
                f"{len(state.broadcast_timestamps) - 1} out of {state.num_subscribers - 1} people"
            )
            error_str += ", please contact the admin if the problem persists"
            await self.broadcastbot.reply_with_warn_on_failure(context, error_str)

            if not state.attachments_deleted:
                await self.broadcastbot.message_handler.delete_attachments(context)

            if not state.timestamp_data_saved:
                self._save_broadcast_timestamps(context, state.subscriber_uuid, state.broadcast_timestamps)
        except Exception:
            self.broadcastbot.logger.exception("")

    async def _broadcast_send(self, context: DataMessageContext) -> None:
        subscriber_uuid = context.message.source_uuid
        if subscriber_uuid is None:
            self.broadcastbot.logger.warning("Received a broadcast message with no source_uuid")
            return

        is_edit = isinstance(context.message, EditMessage)
        action_str, acting_str = ("edited for", "editing") if is_edit else ("sent to", "sending")
        state = _BroadcastState(subscriber_uuid=subscriber_uuid, action_str=action_str, acting_str=acting_str)

        try:
            if await self._reject_ineligible_sender(context, subscriber_uuid):
                return

            state.num_subscribers = len(self.broadcastbot.subscribers)

            content = self._extract_broadcast_content(context)
            if content is None:
                return

            await context.start_typing()

            # The typing indicator dissapears after 15 seconds. Restart it until the broadcast is done.
            typing_job = self.broadcastbot.scheduler.add_job(context.start_typing, "interval", seconds=15)

            to_modify_timestamps = await self._resolve_edit_timestamps(context, subscriber_uuid)

            await self._dispatch_broadcast_tasks(
                context,
                subscriber_uuid,
                state.send_tasks,
                content,
                to_modify_timestamps,
            )

            await asyncio.wait([task for _, task in state.send_tasks])

            state.broadcast_timestamps = await self.check_send_tasks_results(context, state.send_tasks, action_str)
            state.send_tasks_checked = True

            self._save_broadcast_timestamps(context, subscriber_uuid, state.broadcast_timestamps)
            state.timestamp_data_saved = True

            await self.broadcastbot.message_handler.delete_attachments(context)
            state.attachments_deleted = True

            typing_job.remove()
            await context.stop_typing()
            await self.broadcastbot.reply_with_warn_on_failure(
                context,
                f"Message {action_str} {len(state.broadcast_timestamps) - 1} people",
            )

            self.broadcastbot.last_msg_user_uuid = subscriber_uuid
        except Exception:
            self.broadcastbot.logger.exception("")
            await self._recover_from_broadcast_failure(context, state)

    async def _broadcast_delete(self, context: RemoteDeleteContext) -> None:
        subscriber_uuid = context.message.source_uuid
        if subscriber_uuid is None:
            self.broadcastbot.logger.warning("Received a remote-delete message with no source_uuid")
            return

        broadcast_timestamps: dict[str, int] = {}
        num_subscribers = -1
        send_tasks: list[tuple[str, asyncio.Task[int]]] = []
        action_str, acting_str = "deleted for", "deleting"

        try:
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

            for subscriber in self.broadcastbot.subscribers:
                timestamp = to_modify_timestamps.get(subscriber)
                if timestamp is None:
                    # Subscriber wasn't part of the original broadcast (e.g. subscribed
                    # afterwards), nothing to delete for them.
                    continue

                sent_message = SentMessage(recipient=subscriber, timestamp=timestamp)
                subscriber_fn = context.bot.messages.remote_delete(sent_message)
                send_tasks.append((subscriber, asyncio.create_task(subscriber_fn)))

                # Avoid rate limiting by waiting a random time between messages
                await asyncio.sleep(random.uniform(0.5, 1))  # noqa: S311

            if send_tasks:
                await asyncio.wait([task for _, task in send_tasks])

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
