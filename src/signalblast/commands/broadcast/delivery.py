from __future__ import annotations

import contextlib
from collections import defaultdict
from typing import TYPE_CHECKING

from signalbot import SendMessage

if TYPE_CHECKING:
    import asyncio

    from signalbot import Context

    from signalblast.broadcastbot import BroadcasBot


class DeliveryTracker:
    MAX_FAILED_MSGS = 10

    def __init__(self, bot: BroadcasBot) -> None:
        self.broadcastbot = bot
        self.subscribers_num_fails: dict[str, int] = defaultdict(lambda: 0)

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
            if num_fails >= self.MAX_FAILED_MSGS:
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
