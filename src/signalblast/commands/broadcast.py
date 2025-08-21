import asyncio
import contextlib
import random
from collections import defaultdict
from re import Pattern

from signalbot import Command, MessageType
from signalbot import Context as ChatContext

from signalblast.broadcastbot import BroadcasBot
from signalblast.commands_strings import CommandRegex, PublicCommandStrings
from signalblast.utils import TimestampData


class Broadcast(Command):
    MAX_FAILED_MSGS = 10

    def __init__(self, bot: BroadcasBot) -> None:
        super().__init__()
        self.broadcastbot = bot
        self.subscribers_num_fails: dict[str, int] = defaultdict(lambda: 0)

    def is_valid_command(self, message: str, invalid_command: Pattern) -> bool:
        return any(regex != invalid_command and regex.search(message) is not None for regex in CommandRegex)

    async def check_send_tasks_results(self, send_tasks: list[asyncio.Task | None], action_str: str) -> dict[str, int]:
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
                    await self.broadcastbot.send(subscriber, remove_message)

        for subscriber in subscribers_to_remove:
            del self.subscribers_num_fails[subscriber]

        return timestamp_data

    async def broadcast(self, ctx: ChatContext) -> None:  # noqa: C901, PLR0915 function is too complex
        broadcast_timestamps: dict[str, int] = {}
        num_subscribers = -1
        attachments_deleted = False
        send_tasks_checked = False
        timestamp_data_saved = False
        send_tasks: list[asyncio.Task | None] = []
        action_str, acting_str = "sent to", "sending"

        try:
            subscriber_uuid = ctx.message.source_uuid
            if subscriber_uuid in self.broadcastbot.banned_users:
                await self.broadcastbot.send(subscriber_uuid, "This number is not allowed to send messages")
                self.broadcastbot.logger.info("%s tried to broadcast but they are banned", subscriber_uuid)
                return

            if subscriber_uuid not in self.broadcastbot.subscribers:
                await self.broadcastbot.send(subscriber_uuid, self.broadcastbot.must_subscribe_message)
                self.broadcastbot.logger.info("%s tried to broadcast but they are not subscribed", subscriber_uuid)
                return

            num_subscribers = len(self.broadcastbot.subscribers)

            message = self.broadcastbot.message_handler.remove_command_from_message(
                ctx.message.text,
                PublicCommandStrings.broadcast,
            )
            attachments = self.broadcastbot.message_handler.empty_list_to_none(ctx.message.base64_attachments)
            link_preview = ctx.message.link_previews[0] if len(ctx.message.link_previews) > 0 else None

            if message is None and attachments is None:
                return

            if message is None:
                message = ""

            # Broadcast message to all subscribers.
            send_tasks: list[asyncio.Task | None] = [None] * num_subscribers

            if ctx.message.type == MessageType.EDIT_MESSAGE:
                self.broadcastbot.storage_lock.acquire()
                prev_timestamps = ctx.bot.storage.read(
                    f"broadcast-uuid-{subscriber_uuid}-timestamp-{ctx.message.target_sent_timestamp}",
                )
                self.broadcastbot.storage_lock.release()
                edit_timestamps = TimestampData.model_validate(prev_timestamps).broadcast_timestamps
                action_str, acting_str = "edited for", "editing"
            else:
                edit_timestamps = {}

            for i, subscriber in enumerate(self.broadcastbot.subscribers):
                send_tasks[i] = asyncio.create_task(
                    self.broadcastbot.send(
                        subscriber,
                        message,
                        base64_attachments=attachments,
                        link_preview=link_preview,
                        edit_timestamp=edit_timestamps.get(subscriber),
                    ),
                )

                # Avoid rate limiting by waiting a random time between messages
                await asyncio.sleep(random.uniform(0.5, 1))  # noqa: S311

            await asyncio.wait(send_tasks)

            broadcast_timestamps = await self.check_send_tasks_results(send_tasks, action_str)
            send_tasks_checked = True

            broadcastdata = TimestampData(
                author=subscriber_uuid,
                timestamp=ctx.message.timestamp,
                broadcast_timestamps=broadcast_timestamps,
            )
            self.broadcastbot.storage_lock.acquire()
            ctx.bot.storage.save(
                f"broadcast-uuid-{subscriber_uuid}-timestamp-{ctx.message.timestamp}",
                broadcastdata.model_dump(),
            )
            self.broadcastbot.storage_lock.release()
            timestamp_data_saved = True

            await self.broadcastbot.message_handler.delete_attachments(ctx)
            attachments_deleted = True

            await self.broadcastbot.reply_with_warn_on_failure(
                ctx,
                f"Message {action_str} {len(broadcast_timestamps) - 1} people",
            )

            self.broadcastbot.last_msg_user_uuid = subscriber_uuid
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                if send_tasks_checked is False:
                    broadcast_timestamps = await self.check_send_tasks_results(send_tasks)

                error_str = f"Something went wrong when {acting_str} the message"
                error_str += (
                    f", it was only {action_str} {len(broadcast_timestamps) - 1} out of {num_subscribers - 1} people"
                )
                error_str += ", please contact the admin if the problem persists"
                await self.broadcastbot.reply_with_warn_on_failure(ctx, error_str)

                if attachments_deleted is False:
                    await self.broadcastbot.message_handler.delete_attachments(ctx)

                if timestamp_data_saved is False:
                    broadcastdata = TimestampData(
                        author=subscriber_uuid,
                        timestamp=ctx.message.timestamp,
                        broadcast_timestamps=broadcast_timestamps,
                    )
                    self.broadcastbot.storage_lock.acquire()
                    ctx.bot.storage.save(
                        f"broadcast-uuid-{subscriber_uuid}-timestamp-{ctx.message.timestamp}",
                        broadcastdata.model_dump(),
                    )
                    self.broadcastbot.storage_lock.release()
            except Exception:
                self.broadcastbot.logger.exception("")

    async def handle(self, ctx: ChatContext) -> None:
        message = ctx.message.text
        subscriber_uuid = ctx.message.source_uuid
        if message is None:
            if ctx.message.base64_attachments == []:
                self.broadcastbot.logger.info("Received reaction, sticker or similar from %s", subscriber_uuid)
                return

            await ctx.receipt(receipt_type="read")

            # Only attachment, assume the user wants to forward that
            self.broadcastbot.logger.info("Received a file from %s, broadcasting!", subscriber_uuid)
            await self.broadcast(ctx)
            return

        if self.is_valid_command(message, invalid_command=CommandRegex.broadcast):
            return

        await ctx.receipt(receipt_type="read")

        # By default broadcast all the messages
        await self.broadcast(ctx)
