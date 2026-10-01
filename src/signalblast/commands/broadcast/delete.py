from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING

from signalbot import SentMessage

if TYPE_CHECKING:
    from signalbot import RemoteDeleteContext

    from signalblast.broadcastbot import BroadcasBot
    from signalblast.commands.broadcast.delivery import DeliveryTracker


class BroadcastDeleter:
    def __init__(self, bot: BroadcasBot, tracker: DeliveryTracker) -> None:
        self.broadcastbot = bot
        self.tracker = tracker

    async def delete(self, context: RemoteDeleteContext) -> None:
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
            prev_timestamps = self.broadcastbot.db.read_broadcast_timestamps(subscriber_uuid, context.message.timestamp)
            self.broadcastbot.storage_lock.release()
            to_modify_timestamps = prev_timestamps.broadcast_timestamps

            subscribers = list(self.broadcastbot.subscribers)
            random.shuffle(subscribers)
            for subscriber in subscribers:
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

            broadcast_timestamps = await self.tracker.check_send_tasks_results(context, send_tasks, action_str)

            await self.broadcastbot.send_with_warn_on_failure(
                context,
                f"Message {action_str} {len(broadcast_timestamps) - 1} people",
            )

            self.broadcastbot.last_msg_user_uuid = subscriber_uuid
        except Exception:
            self.broadcastbot.logger.exception("")
            try:
                broadcast_timestamps = await self.tracker.check_send_tasks_results(context, send_tasks, action_str)

                error_str = f"Something went wrong when {acting_str} the message"
                error_str += (
                    f", it was only {action_str} {len(broadcast_timestamps) - 1} out of {num_subscribers - 1} people"
                )
                error_str += ", please contact the admin if the problem persists"
                await self.broadcastbot.send_with_warn_on_failure(context, error_str)
            except Exception:
                self.broadcastbot.logger.exception("")
